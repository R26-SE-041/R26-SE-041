#!/usr/bin/env node

/**
 * End-to-end baseline requested for the paper screenshots.
 *
 * raw_flux1_dev:
 *   minimal one-word prompt -> unmodified FLUX.1-dev output
 *
 * our_full_pipeline:
 *   same one-word user input -> anatomy-workspace prefix -> Qwen prompt agent
 *   with deployed persona/SKILL/MEMENTO -> FLUX.1-dev -> Qwen-VL auto labels
 *   -> frontend-equivalent rendered label overlay
 *
 * The raw PNG and the final labeled pipeline PNG are evaluated against the
 * same original one-word prompt. This intentionally measures end products,
 * matching the user's baseline-comparison screenshots.
 */

import { execFile } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { promisify } from "node:util";
import { fileURLToPath } from "node:url";

const execFileAsync = promisify(execFile);
const HERE = path.dirname(fileURLToPath(import.meta.url));
const OUTPUT_DIR = path.join(HERE, "results", "end-to-end-baseline");
const PROMPTS = ["eye", "heart", "skin"];
const SEED = 260902;
const SPEED_MODE = "normal";
const BASE = "https://agal-koji--{}-api.modal.run";
const URLS = {
  prompt: process.env.PROMPT_AGENT_URL || BASE.replace("{}", "prompt-agent"),
  image: process.env.IMAGE_AGENT_URL || BASE.replace("{}", "image-agent"),
  eval: process.env.EVAL_AGENT_URL || BASE.replace("{}", "eval-agent"),
  interactive: process.env.INTERACTIVE_AGENT_URL || BASE.replace("{}", "interactive-agent"),
};
const METRICS = [
  ["clip_score", "CLIPScore", "0-100; higher is better", "openai/clip-vit-base-patch16"],
  ["visual_score", "Prompt alignment / Visual score", "0-10", "Qwen2.5-VL-7B-Instruct"],
  ["pedagogical_score", "Educational usefulness / Pedagogical score", "0-10", "Qwen2.5-VL-7B-Instruct"],
  ["vlm_score", "VLM score", "0-10", "Mean of Qwen-VL visual and pedagogical scores"],
];

function parseArgs(argv) {
  const options = { prompts: PROMPTS, seed: SEED, reportOnly: false };
  for (let index = 0; index < argv.length; index += 1) {
    if (argv[index] === "--prompts" && argv[index + 1]) {
      options.prompts = argv[++index].split(",").map((value) => value.trim()).filter(Boolean);
    } else if (argv[index] === "--seed" && argv[index + 1]) {
      options.seed = Number(argv[++index]);
    } else if (argv[index] === "--report-only") {
      options.reportOnly = true;
    } else {
      throw new Error(`Unknown or incomplete argument: ${argv[index]}`);
    }
  }
  if (!options.prompts.length) throw new Error("At least one prompt is required");
  if (!Number.isInteger(options.seed) || options.seed < 0) throw new Error("--seed must be a non-negative integer");
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
      return { data, latencyMs: Math.round((performance.now() - started) * 100) / 100 };
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

function bufferFromBase64(value) {
  if (!value) throw new Error("Missing image_base64");
  return Buffer.from(value, "base64");
}

async function renderLabeledPng(baseImagePath, annotations, outputPath) {
  const annotationPath = `${outputPath}.annotations.json`;
  await writeFile(annotationPath, JSON.stringify(annotations, null, 2));
  await execFileAsync("powershell.exe", [
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", path.join(HERE, "render_labeled_png.ps1"),
    "-ImagePath", baseImagePath,
    "-AnnotationsPath", annotationPath,
    "-OutputPath", outputPath,
  ], { windowsHide: true });
}

async function evaluateImage(imagePath, rawPrompt) {
  const imageBase64 = (await readFile(imagePath)).toString("base64");
  const result = await postJson(`${URLS.eval}/evaluate`, {
    image_base64: imageBase64,
    enhanced_prompt: null,
    raw_prompt: rawPrompt,
    anatomy_spec: { is_anatomy: false },
    enable_anatomy_critic: false,
  });
  if (result.data.error) throw new Error(`Evaluation failed: ${result.data.error}`);
  return { response: result.data, latencyMs: result.latencyMs };
}

async function runPrompt(rawPrompt, seed) {
  console.log(`\n[${rawPrompt}] raw FLUX.1-dev`);
  const rawGeneration = await postJson(`${URLS.image}/generate`, {
    prompt: rawPrompt,
    speed_mode: SPEED_MODE,
    seed,
    domain: "generic",
    use_skill_rules: false,
    use_policy_rules: false,
  });
  if (rawGeneration.data.error) throw new Error(rawGeneration.data.error);
  const rawPath = path.join(OUTPUT_DIR, "images", `${rawPrompt}_raw_flux1_dev.png`);
  await writeFile(rawPath, bufferFromBase64(rawGeneration.data.image_base64));

  console.log(`[${rawPrompt}] prompt enhancement + FLUX.1-dev`);
  // This reproduces App.tsx when the Anatomy workspace is selected.
  const routedPrompt = `Human anatomy educational illustration: ${rawPrompt}`;
  const enhanced = await postJson(`${URLS.prompt}/enhance`, {
    raw_prompt: routedPrompt,
    speed_mode: SPEED_MODE,
    use_memento: true,
    use_skill_rules: true,
    seed,
    model_variant: "base",
  });
  const enhancedPayload = minimalEnhancedPayload(enhanced.data);
  if (!enhancedPayload.anatomy_spec.is_anatomy) {
    throw new Error(`Pipeline did not route '${rawPrompt}' as anatomy`);
  }
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
  const pipelineBasePath = path.join(OUTPUT_DIR, "images", `${rawPrompt}_pipeline_base.png`);
  await writeFile(pipelineBasePath, bufferFromBase64(pipelineGeneration.data.image_base64));

  console.log(`[${rawPrompt}] Qwen-VL name labeling + final overlay`);
  const labeled = await postJson(`${URLS.interactive}/auto-labels`, {
    image_base64: pipelineGeneration.data.image_base64,
    domain: "anatomy",
    organ: enhancedPayload.anatomy_spec.organ || rawPrompt,
    view: enhancedPayload.anatomy_spec.view_description || enhancedPayload.anatomy_spec.view || "",
    speed_mode: SPEED_MODE,
  });
  if (labeled.data.error) throw new Error(labeled.data.error);
  const annotations = (labeled.data.annotations || []).filter((item) => item.verified === true);
  const finalPath = path.join(OUTPUT_DIR, "images", `${rawPrompt}_our_full_pipeline.png`);
  await renderLabeledPng(pipelineBasePath, annotations, finalPath);

  console.log(`[${rawPrompt}] scoring final end products`);
  const [rawEval, pipelineEval] = await Promise.all([
    evaluateImage(rawPath, rawPrompt),
    evaluateImage(finalPath, rawPrompt),
  ]);
  const row = (condition, imagePath, evaluated) => ({
    prompt: rawPrompt,
    seed,
    condition,
    image_file: path.relative(OUTPUT_DIR, imagePath).replaceAll("\\", "/"),
    metrics: Object.fromEntries(METRICS.map(([key]) => [key, evaluated.response[key]])),
    evaluator_feedback: evaluated.response.vlm_feedback,
    evaluation_latency_ms: evaluated.latencyMs,
  });
  return [
    {
      ...row("raw_flux1_dev", rawPath, rawEval),
      generation_prompt: rawPrompt,
      generation_latency_ms: rawGeneration.latencyMs,
      model: "black-forest-labs/FLUX.1-dev",
      labels_rendered: 0,
    },
    {
      ...row("our_full_pipeline", finalPath, pipelineEval),
      routed_prompt: routedPrompt,
      enhanced_prompt: enhancedPayload.final_prompt,
      anatomy_spec: enhancedPayload.anatomy_spec,
      generation_latency_ms: pipelineGeneration.latencyMs,
      enhancement_latency_ms: enhanced.latencyMs,
      labeling_latency_ms: labeled.latencyMs,
      model: "Qwen2.5 prompt agent + FLUX.1-dev + Qwen2.5-VL labeling",
      labels_rendered: annotations.length,
      labels: annotations.map((item) => ({ label: item.label, confidence: item.confidence })),
      auto_label_diagnostics: labeled.data.diagnostics || {},
    },
  ];
}

function mean(values) {
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function sd(values) {
  if (values.length < 2) return 0;
  const average = mean(values);
  return Math.sqrt(values.reduce((sum, value) => sum + (value - average) ** 2, 0) / (values.length - 1));
}

export function summarize(rows) {
  const conditions = {};
  for (const condition of ["raw_flux1_dev", "our_full_pipeline"]) {
    const selected = rows.filter((row) => row.condition === condition && !row.error);
    conditions[condition] = Object.fromEntries(METRICS.map(([key]) => {
      const values = selected.map((row) => row.metrics[key]).filter(Number.isFinite);
      return [key, { n: values.length, mean: mean(values), sd: sd(values) }];
    }));
  }
  const deltas = {};
  for (const [key] of METRICS) {
    const values = [];
    for (const prompt of [...new Set(rows.map((row) => row.prompt))]) {
      const raw = rows.find((row) => row.prompt === prompt && row.condition === "raw_flux1_dev" && !row.error);
      const pipeline = rows.find((row) => row.prompt === prompt && row.condition === "our_full_pipeline" && !row.error);
      if (raw && pipeline) values.push(pipeline.metrics[key] - raw.metrics[key]);
    }
    deltas[key] = { n: values.length, mean: values.length ? mean(values) : null, sd: values.length ? sd(values) : null };
  }
  return { conditions, paired_deltas_pipeline_minus_raw: deltas };
}

function fixed(value) {
  return Number.isFinite(value) ? value.toFixed(2) : "NA";
}

function report(summary, options, rows) {
  const lines = [
    "# End-to-end baseline comparison",
    "",
    `Minimal prompts: ${options.prompts.map((value) => `\`${value}\``).join(", ")}. Fixed seed: ${options.seed}.`,
    "",
    "Raw baseline is the one-word prompt sent directly to FLUX.1-dev. Our full pipeline uses the Anatomy-workspace prefix, deployed Qwen prompt enhancement with system persona/SKILL/MEMENTO, FLUX.1-dev, Qwen-VL automatic name labeling, and the rendered frontend-style overlay. Metrics compare the raw PNG with the final labeled pipeline PNG against the same original one-word prompt.",
    "",
    "| Score | Range | Measuring model | Raw FLUX.1-dev, mean +/- SD | Our full pipeline, mean +/- SD | Paired delta | Pairs |",
    "|---|---:|---|---:|---:|---:|---:|",
  ];
  for (const [key, label, range, model] of METRICS) {
    const raw = summary.conditions.raw_flux1_dev[key];
    const pipeline = summary.conditions.our_full_pipeline[key];
    const delta = summary.paired_deltas_pipeline_minus_raw[key];
    lines.push(`| ${label} | ${range} | ${model} | ${fixed(raw.mean)} +/- ${fixed(raw.sd)} | ${fixed(pipeline.mean)} +/- ${fixed(pipeline.sd)} | ${fixed(delta.mean)} | ${delta.n} |`);
  }
  lines.push(
    "",
    "## Per-prompt results",
    "",
    "| Prompt | Condition | CLIPScore | Visual | Pedagogical | VLM average | Rendered labels |",
    "|---|---|---:|---:|---:|---:|---:|",
  );
  for (const prompt of options.prompts) {
    for (const condition of ["raw_flux1_dev", "our_full_pipeline"]) {
      const row = rows.find((item) => item.prompt === prompt && item.condition === condition && !item.error);
      if (!row) continue;
      lines.push(`| ${prompt} | ${condition === "raw_flux1_dev" ? "Raw FLUX.1-dev" : "Our full pipeline"} | ${fixed(row.metrics.clip_score)} | ${fixed(row.metrics.visual_score)} | ${fixed(row.metrics.pedagogical_score)} | ${fixed(row.metrics.vlm_score)} | ${row.labels_rendered || 0} |`);
    }
  }
  lines.push(
    "",
    "CLIPScore is lower for the pipeline in this smoke run. The pipeline artifact includes large text-label boxes and callout lines, while CLIP is evaluated against a one-word prompt; the Qwen educational metrics directly capture the intended labeled-diagram benefit.",
    "",
    "**Observed skin limitation:** the current general-anatomy route turns `skin` into a whole-body internal-anatomy image and Qwen accepts unrelated labels. Do not present that example as anatomically correct skin labeling without fixing the route and label validation.",
    "",
    "This is a three-prompt, one-seed smoke comparison matching the supplied screenshots, not an inferential experiment. For a paper claim, repeat on a pre-registered held-out prompt set with multiple seeds and independent human scoring.",
    "",
  );
  return lines.join("\n");
}

async function writeResults(rows, options) {
  const summary = summarize(rows);
  await Promise.all([
    writeFile(path.join(OUTPUT_DIR, "results.json"), JSON.stringify({
      protocol: {
        id: "end-to-end-minimal-prompt-v1",
        prompts: options.prompts,
        seed: options.seed,
        raw_condition: "one-word prompt -> FLUX.1-dev",
        pipeline_condition: "one-word input -> Anatomy workspace -> Qwen prompt agent (persona/SKILL/MEMENTO) -> FLUX.1-dev -> Qwen-VL labels -> rendered overlay",
        image_config: { width: 512, height: 512, inference_steps: 25, guidance_scale: 3.5 },
        endpoints: URLS,
      },
      summary,
      rows,
    }, null, 2) + "\n"),
    writeFile(path.join(OUTPUT_DIR, "metrics-table.md"), report(summary, options, rows)),
  ]);
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  await mkdir(path.join(OUTPUT_DIR, "images"), { recursive: true });
  const resultPath = path.join(OUTPUT_DIR, "results.json");
  let rows = [];
  try {
    rows = JSON.parse(await readFile(resultPath, "utf8")).rows || [];
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
  }
  if (options.reportOnly) {
    await writeResults(rows, options);
    return;
  }
  const completed = new Set(rows.filter((row) => !row.error).map((row) => `${row.prompt}:${row.seed}:${row.condition}`));
  for (const prompt of options.prompts) {
    if (["raw_flux1_dev", "our_full_pipeline"].every((condition) => completed.has(`${prompt}:${options.seed}:${condition}`))) {
      console.log(`[${prompt}] reusing completed pair`);
      continue;
    }
    try {
      const pair = await runPrompt(prompt, options.seed);
      rows = rows.filter((row) => !(row.prompt === prompt && row.seed === options.seed));
      rows.push(...pair);
      console.log(`[${prompt}] raw VLM=${pair[0].metrics.vlm_score}, pipeline VLM=${pair[1].metrics.vlm_score}, labels=${pair[1].labels_rendered}`);
    } catch (error) {
      rows = rows.filter((row) => !(row.prompt === prompt && row.seed === options.seed));
      rows.push({ prompt, seed: options.seed, condition: "pair", error: error.message });
      console.error(`[${prompt}] FAILED: ${error.message}`);
    }
    await writeResults(rows, options);
  }
  await writeResults(rows, options);
  console.log(`Wrote ${path.join(OUTPUT_DIR, "metrics-table.md")}`);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    console.error(error.stack || error.message);
    process.exitCode = 1;
  });
}
