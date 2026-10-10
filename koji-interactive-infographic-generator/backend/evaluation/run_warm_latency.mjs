#!/usr/bin/env node

/**
 * Warm-state Modal latency for the visualization subsystem.
 *
 * Measures the serving latency of every Modal agent on the two conditions the
 * paper's Table III already compares:
 *
 *   raw_flux1_dev      one-word prompt -> FLUX.1-dev                 (1 call)
 *   our_full_pipeline  prompt agent -> FLUX.1-dev -> dual critic
 *                      -> Qwen2.5-VL auto-labeling                   (4 calls)
 *
 * Cold starts are excluded by design. Each prompt begins with a discarded
 * warm-up pass that boots and loads every GPU container; only the repetitions
 * that follow are reported. Requests are issued back-to-back so no container
 * falls outside its scaledown window between measurements.
 *
 * Client-side SVG label rendering is deliberately not timed: it runs in the
 * frontend, not on Modal.
 */

import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const OUTPUT_DIR = path.join(HERE, "results", "warm-latency");
const PROMPTS = ["eye", "heart", "skin"];
const SEED = 260902;
const REPS = 3;
const SPEED_MODE = "normal";
const BASE = "https://agal-koji--{}-api.modal.run";
const URLS = {
  prompt: process.env.PROMPT_AGENT_URL || BASE.replace("{}", "prompt-agent"),
  image: process.env.IMAGE_AGENT_URL || BASE.replace("{}", "image-agent"),
  eval: process.env.EVAL_AGENT_URL || BASE.replace("{}", "eval-agent"),
  interactive: process.env.INTERACTIVE_AGENT_URL || BASE.replace("{}", "interactive-agent"),
};

// stage key, printable label, condition it belongs to, serving hardware.
export const STAGES = [
  ["raw_generation_ms", "Image synthesis (raw baseline)", "raw_flux1_dev", "FLUX.1-dev, A10G"],
  ["enhancement_ms", "Prompt enhancement", "our_full_pipeline", "Qwen2.5-3B-Instruct, T4"],
  ["generation_ms", "Image synthesis", "our_full_pipeline", "FLUX.1-dev, A10G"],
  ["critic_ms", "Dual-critic evaluation", "our_full_pipeline", "CLIP + Qwen2.5-VL-7B, A10G"],
  ["labeling_ms", "Grounded auto-labeling", "our_full_pipeline", "Qwen2.5-VL-7B, A10G"],
];

function parseArgs(argv) {
  const options = { prompts: PROMPTS, seed: SEED, reps: REPS, reportOnly: false };
  for (let index = 0; index < argv.length; index += 1) {
    if (argv[index] === "--prompts" && argv[index + 1]) {
      options.prompts = argv[++index].split(",").map((value) => value.trim()).filter(Boolean);
    } else if (argv[index] === "--seed" && argv[index + 1]) {
      options.seed = Number(argv[++index]);
    } else if (argv[index] === "--reps" && argv[index + 1]) {
      options.reps = Number(argv[++index]);
    } else if (argv[index] === "--report-only") {
      options.reportOnly = true;
    } else {
      throw new Error(`Unknown or incomplete argument: ${argv[index]}`);
    }
  }
  if (!options.prompts.length) throw new Error("At least one prompt is required");
  if (!Number.isInteger(options.seed) || options.seed < 0) throw new Error("--seed must be a non-negative integer");
  if (!Number.isInteger(options.reps) || options.reps < 1) throw new Error("--reps must be a positive integer");
  return options;
}

async function postJson(url, body, timeoutMs = 900_000) {
  let lastError;
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    const started = performance.now();
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(timeoutMs),
      });
      const text = await response.text();
      const data = JSON.parse(text);
      if (!response.ok) throw new Error(`${url} returned HTTP ${response.status}: ${text.slice(0, 500)}`);
      // A retried call re-queues on Modal and can pay a fresh container start,
      // so the attempt index travels with the timing and is flagged later.
      return { data, latencyMs: Math.round((performance.now() - started) * 100) / 100, attempt };
    } catch (error) {
      lastError = error;
      if (attempt < 3) await new Promise((resolve) => setTimeout(resolve, attempt * 1_000));
    }
  }
  throw lastError;
}

function minimalEnhancedPayload(response) {
  const payload = response.enhanced_prompt_json || {};
  const finalPrompt = payload.final_prompt || response.enhanced_prompt;
  const anatomySpec = payload.anatomy_spec || response.anatomy_spec;
  if (!finalPrompt || !anatomySpec) throw new Error(`Invalid enhancement response: ${JSON.stringify(response).slice(0, 800)}`);
  return {
    schema_version: "1.0",
    final_prompt: finalPrompt,
    anatomy_spec: anatomySpec,
    route: payload.route || (anatomySpec.is_anatomy ? "anatomy" : "generic"),
  };
}

/** One full paired pass. Request payloads match run_end_to_end_baseline.mjs. */
async function timedPass(rawPrompt, seed) {
  const rawGeneration = await postJson(`${URLS.image}/generate`, {
    prompt: rawPrompt,
    speed_mode: SPEED_MODE,
    seed,
    domain: "generic",
    use_skill_rules: false,
    use_policy_rules: false,
  });
  if (rawGeneration.data.error) throw new Error(rawGeneration.data.error);

  const enhanced = await postJson(`${URLS.prompt}/enhance`, {
    raw_prompt: `Human anatomy educational illustration: ${rawPrompt}`,
    speed_mode: SPEED_MODE,
    use_memento: true,
    use_skill_rules: true,
    seed,
    model_variant: "base",
  });
  const enhancedPayload = minimalEnhancedPayload(enhanced.data);
  if (!enhancedPayload.anatomy_spec.is_anatomy) throw new Error(`Pipeline did not route '${rawPrompt}' as anatomy`);

  const pipelineGeneration = await postJson(`${URLS.image}/generate`, {
    enhanced_prompt_json: enhancedPayload,
    speed_mode: SPEED_MODE,
    seed,
    domain: "anatomy",
    organ: enhancedPayload.anatomy_spec.organ,
    view: enhancedPayload.anatomy_spec.view,
    use_skill_rules: true,
  });
  if (pipelineGeneration.data.error) throw new Error(pipelineGeneration.data.error);

  // The eval agent scores CLIP against `enhanced_prompt or raw_prompt`, and CLIP's
  // text encoder is capped at 77 tokens — the compiled anatomy prompt overflows it.
  // Sending the raw prompt keeps CLIP on the same text Table III scored against,
  // while anatomy_spec still drives the full anatomy critic.
  const critic = await postJson(`${URLS.eval}/evaluate`, {
    image_base64: pipelineGeneration.data.image_base64,
    enhanced_prompt: null,
    raw_prompt: rawPrompt,
    anatomy_spec: enhancedPayload.anatomy_spec,
    enable_anatomy_critic: true,
  });
  if (critic.data.error) throw new Error(`Evaluation failed: ${critic.data.error}`);

  const labeled = await postJson(`${URLS.interactive}/auto-labels`, {
    image_base64: pipelineGeneration.data.image_base64,
    domain: "anatomy",
    organ: enhancedPayload.anatomy_spec.organ || rawPrompt,
    view: enhancedPayload.anatomy_spec.view_description || enhancedPayload.anatomy_spec.view || "",
    speed_mode: SPEED_MODE,
  });
  if (labeled.data.error) throw new Error(labeled.data.error);

  return {
    prompt: rawPrompt,
    seed,
    raw_generation_ms: rawGeneration.latencyMs,
    enhancement_ms: enhanced.latencyMs,
    generation_ms: pipelineGeneration.latencyMs,
    critic_ms: critic.latencyMs,
    labeling_ms: labeled.latencyMs,
    retried_calls: [rawGeneration, enhanced, pipelineGeneration, critic, labeled].filter((call) => call.attempt > 1).length,
    labels_rendered: (labeled.data.annotations || []).filter((item) => item.verified === true).length,
  };
}

function mean(values) {
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function sd(values) {
  if (values.length < 2) return 0;
  const average = mean(values);
  return Math.sqrt(values.reduce((sum, value) => sum + (value - average) ** 2, 0) / (values.length - 1));
}

function percentile(values, fraction) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  // Nearest-rank percentile: reproducible and defensible at small n.
  const rank = Math.max(1, Math.ceil(fraction * sorted.length));
  return sorted[rank - 1];
}

/** Pipeline total is the sum of its own stages; the raw total is its single call. */
export function totalsFor(row) {
  return {
    raw_flux1_dev: row.raw_generation_ms,
    our_full_pipeline: row.enhancement_ms + row.generation_ms + row.critic_ms + row.labeling_ms,
  };
}

export function summarize(rows) {
  const measured = rows.filter((row) => !row.warmup && !row.error);
  const describe = (values) => ({
    n: values.length,
    mean: values.length ? mean(values) : null,
    sd: values.length ? sd(values) : null,
    p50: percentile(values, 0.5),
    p95: percentile(values, 0.95),
    min: values.length ? Math.min(...values) : null,
    max: values.length ? Math.max(...values) : null,
  });
  const stages = Object.fromEntries(STAGES.map(([key]) => [key, describe(measured.map((row) => row[key]))]));
  const totals = {
    raw_flux1_dev: describe(measured.map((row) => totalsFor(row).raw_flux1_dev)),
    our_full_pipeline: describe(measured.map((row) => totalsFor(row).our_full_pipeline)),
  };
  return {
    stages,
    totals,
    pipeline_overhead_ratio: totals.raw_flux1_dev.mean ? totals.our_full_pipeline.mean / totals.raw_flux1_dev.mean : null,
    pipeline_overhead_ms: totals.our_full_pipeline.mean !== null && totals.raw_flux1_dev.mean !== null
      ? totals.our_full_pipeline.mean - totals.raw_flux1_dev.mean
      : null,
  };
}

const seconds = (ms) => (Number.isFinite(ms) ? (ms / 1000).toFixed(1) : "NA");

function report(summary, options, rows) {
  const warmups = rows.filter((row) => row.warmup && !row.error);
  const measured = rows.filter((row) => !row.warmup && !row.error);
  const lines = [
    "# Warm-state Modal latency (visualization subsystem)",
    "",
    `Prompts: ${options.prompts.map((value) => `\`${value}\``).join(", ")}. Fixed seed: ${options.seed}. `
      + `Repetitions per prompt: ${options.reps}. Measured passes: ${measured.length}.`,
    "",
    `Speed mode \`${SPEED_MODE}\`, 512x512, 25 inference steps, guidance 3.5 - the same configuration as the `
      + "Table III quality comparison, so latency and quality describe one deployment.",
    "",
    `Cold starts are excluded: ${warmups.length} discarded warm-up pass(es) boot and load every GPU container `
      + "before timing begins, and all measured calls are issued back-to-back inside each container's scaledown window.",
    "",
    "| Stage | Condition | Serving model / GPU | Warm mean +/- SD (s) | p50 (s) | p95 (s) |",
    "|---|---|---|---:|---:|---:|",
  ];
  for (const [key, label, condition, hardware] of STAGES) {
    const stat = summary.stages[key];
    const conditionLabel = condition === "raw_flux1_dev" ? "Raw FLUX.1-dev" : "Our full pipeline";
    lines.push(`| ${label} | ${conditionLabel} | ${hardware} | ${seconds(stat.mean)} +/- ${seconds(stat.sd)} | ${seconds(stat.p50)} | ${seconds(stat.p95)} |`);
  }
  lines.push(
    "",
    "| End-to-end condition | Modal calls | Warm mean +/- SD (s) | p50 (s) | p95 (s) |",
    "|---|---:|---:|---:|---:|",
    `| Raw FLUX.1-dev | 1 | ${seconds(summary.totals.raw_flux1_dev.mean)} +/- ${seconds(summary.totals.raw_flux1_dev.sd)} | ${seconds(summary.totals.raw_flux1_dev.p50)} | ${seconds(summary.totals.raw_flux1_dev.p95)} |`,
    `| Our full pipeline | 4 | ${seconds(summary.totals.our_full_pipeline.mean)} +/- ${seconds(summary.totals.our_full_pipeline.sd)} | ${seconds(summary.totals.our_full_pipeline.p50)} | ${seconds(summary.totals.our_full_pipeline.p95)} |`,
    "",
    "Warm-state overhead of the agentic pipeline over a single raw diffusion pass: "
      + `+${seconds(summary.pipeline_overhead_ms)} s (${summary.pipeline_overhead_ratio ? summary.pipeline_overhead_ratio.toFixed(2) : "NA"}x).`,
    "",
    "## Per-pass measurements",
    "",
    "| Prompt | Rep | Raw gen (s) | Enhance (s) | Gen (s) | Critic (s) | Label (s) | Pipeline total (s) |",
    "|---|---:|---:|---:|---:|---:|---:|---:|",
  );
  for (const row of measured) {
    lines.push(`| ${row.prompt} | ${row.rep} | ${seconds(row.raw_generation_ms)} | ${seconds(row.enhancement_ms)} | ${seconds(row.generation_ms)} | ${seconds(row.critic_ms)} | ${seconds(row.labeling_ms)} | ${seconds(totalsFor(row).our_full_pipeline)} |`);
  }
  if (warmups.length) {
    lines.push(
      "",
      "## Discarded warm-up passes (cold start, not reported in the paper)",
      "",
      "| Prompt | Raw gen (s) | Enhance (s) | Gen (s) | Critic (s) | Label (s) |",
      "|---|---:|---:|---:|---:|---:|",
    );
    for (const row of warmups) {
      lines.push(`| ${row.prompt} | ${seconds(row.raw_generation_ms)} | ${seconds(row.enhancement_ms)} | ${seconds(row.generation_ms)} | ${seconds(row.critic_ms)} | ${seconds(row.labeling_ms)} |`);
    }
  }
  const failures = rows.filter((row) => row.error);
  if (failures.length) {
    lines.push("", "## Failed passes", "");
    for (const row of failures) lines.push(`- ${row.prompt} rep ${row.rep ?? "warmup"}: ${row.error}`);
  }
  const retried = measured.filter((row) => row.retried_calls > 0);
  if (retried.length) {
    lines.push(
      "",
      `**Caution:** ${retried.length} measured pass(es) contained an HTTP retry, which can re-queue onto a fresh `
        + "container and inflate that stage. Re-run before quoting these numbers.",
    );
  }
  lines.push("");
  return lines.join("\n");
}

async function writeResults(rows, options) {
  const summary = summarize(rows);
  await Promise.all([
    writeFile(path.join(OUTPUT_DIR, "results.json"), JSON.stringify({
      protocol: {
        id: "warm-state-modal-latency-v1",
        prompts: options.prompts,
        seed: options.seed,
        reps: options.reps,
        speed_mode: SPEED_MODE,
        cold_start_policy: "one discarded warm-up pass per prompt; measured calls issued back-to-back",
        excludes: "client-side SVG label rendering (frontend, not Modal)",
        image_config: { width: 512, height: 512, inference_steps: 25, guidance_scale: 3.5 },
        endpoints: URLS,
      },
      summary,
      rows,
    }, null, 2) + "\n"),
    writeFile(path.join(OUTPUT_DIR, "latency-table.md"), report(summary, options, rows)),
  ]);
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  await mkdir(OUTPUT_DIR, { recursive: true });
  const resultPath = path.join(OUTPUT_DIR, "results.json");
  if (options.reportOnly) {
    const existing = JSON.parse(await readFile(resultPath, "utf8")).rows || [];
    await writeResults(existing, options);
    return;
  }

  const rows = [];
  for (const prompt of options.prompts) {
    for (let rep = 0; rep <= options.reps; rep += 1) {
      const warmup = rep === 0;
      const tag = warmup ? "warm-up (discarded)" : `rep ${rep}/${options.reps}`;
      console.log(`\n[${prompt}] ${tag}`);
      try {
        const pass = await timedPass(prompt, options.seed);
        rows.push(warmup ? { ...pass, warmup: true } : { ...pass, rep });
        console.log(
          `[${prompt}] ${tag}: raw=${seconds(pass.raw_generation_ms)}s, `
          + `pipeline=${seconds(totalsFor(pass).our_full_pipeline)}s `
          + `(enhance ${seconds(pass.enhancement_ms)}s, gen ${seconds(pass.generation_ms)}s, `
          + `critic ${seconds(pass.critic_ms)}s, label ${seconds(pass.labeling_ms)}s)`,
        );
      } catch (error) {
        rows.push({ prompt, seed: options.seed, rep: warmup ? undefined : rep, warmup: warmup || undefined, error: error.message });
        console.error(`[${prompt}] ${tag} FAILED: ${error.message}`);
      }
      await writeResults(rows, options);
    }
  }
  await writeResults(rows, options);
  console.log(`\nWrote ${path.join(OUTPUT_DIR, "latency-table.md")}`);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    console.error(error.stack || error.message);
    process.exitCode = 1;
  });
}
