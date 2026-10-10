#!/usr/bin/env node

/**
 * Resumable, paired Modal evaluation for a research-paper component table.
 *
 * Conditions:
 *   - raw_flux1_dev: the original prompt goes directly to FLUX.1-dev.
 *   - our_pipeline: Qwen prompt agent + SKILL/persona + deterministic anatomy
 *     compiler + anatomy image policy + FLUX.1-dev.
 *
 * Qwen-VL automatic name labeling is run as the same measurement probe on both
 * generated images. Image metrics are computed before labels are overlaid so
 * OCR/text rendering cannot inflate CLIP or VLM scores.
 *
 * Run from backend/ (or any directory):
 *   node evaluation/paper_component_comparison.mjs
 *   node evaluation/paper_component_comparison.mjs --organs heart,brain --seeds 260901
 */

import { mkdir, readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const BACKEND = path.resolve(HERE, "..");
const DEFAULT_OUTPUT_DIR = path.join(HERE, "results", "paper-component-comparison");
const ALL_ORGANS = ["heart", "brain", "kidneys", "liver", "lungs"];
const CONDITIONS = ["raw_flux1_dev", "our_pipeline"];
const METRICS = [
  { key: "clip_score", label: "CLIPScore", range: "0–100; higher is better", model: "openai/clip-vit-base-patch16" },
  { key: "visual_score", label: "Prompt alignment / Visual score", range: "0–10", model: "Qwen2.5-VL-7B-Instruct" },
  { key: "pedagogical_score", label: "Educational usefulness / Pedagogical score", range: "0–10", model: "Qwen2.5-VL-7B-Instruct" },
  { key: "vlm_score", label: "VLM score", range: "0–10", model: "Mean of the two Qwen-VL scores" },
];

const DEFAULT_BASE_URL = "https://agal-koji--{}-api.modal.run";
const URLS = {
  prompt: process.env.PROMPT_AGENT_URL || DEFAULT_BASE_URL.replace("{}", "prompt-agent"),
  image: process.env.IMAGE_AGENT_URL || DEFAULT_BASE_URL.replace("{}", "image-agent"),
  eval: process.env.EVAL_AGENT_URL || DEFAULT_BASE_URL.replace("{}", "eval-agent"),
  interactive: process.env.INTERACTIVE_AGENT_URL || DEFAULT_BASE_URL.replace("{}", "interactive-agent"),
};

function parseArgs(argv) {
  const options = {
    organs: ALL_ORGANS,
    seeds: [260901],
    outputDir: DEFAULT_OUTPUT_DIR,
    speedMode: "normal",
    reportOnly: false,
  };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    const value = argv[index + 1];
    if (arg === "--organs" && value) {
      options.organs = value.split(",").map((item) => item.trim()).filter(Boolean);
      index += 1;
    } else if (arg === "--seeds" && value) {
      options.seeds = value.split(",").map(Number);
      index += 1;
    } else if (arg === "--output-dir" && value) {
      options.outputDir = path.resolve(value);
      index += 1;
    } else if (arg === "--speed-mode" && value) {
      options.speedMode = value;
      index += 1;
    } else if (arg === "--report-only") {
      options.reportOnly = true;
    } else if (arg === "--help") {
      console.log("Usage: node evaluation/paper_component_comparison.mjs [--organs heart,brain] [--seeds 260901,260902] [--output-dir PATH] [--speed-mode normal|pro|promax] [--report-only]");
      process.exit(0);
    } else {
      throw new Error(`Unknown or incomplete argument: ${arg}`);
    }
  }
  const unsupported = options.organs.filter((organ) => !ALL_ORGANS.includes(organ));
  if (unsupported.length) throw new Error(`Unsupported organs: ${unsupported.join(", ")}`);
  if (!options.organs.length) throw new Error("At least one organ is required");
  if (!options.seeds.length || options.seeds.some((seed) => !Number.isInteger(seed) || seed < 0)) {
    throw new Error("Seeds must be comma-separated non-negative integers");
  }
  if (!["normal", "pro", "promax"].includes(options.speedMode)) {
    throw new Error("--speed-mode must be normal, pro, or promax");
  }
  return options;
}

function promptFor(organ) {
  return `Create a clear, scientifically accurate educational anatomy diagram of the human ${organ} for a secondary-school biology student. Show the important internal structures in a standard instructional view.`;
}

async function postJson(url, payload, timeoutMs = 900_000) {
  let lastError;
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    const started = performance.now();
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(timeoutMs),
      });
      const text = await response.text();
      let data;
      try {
        data = JSON.parse(text);
      } catch {
        throw new Error(`${url} returned non-JSON HTTP ${response.status}: ${text.slice(0, 300)}`);
      }
      if (!response.ok) {
        throw new Error(`${url} returned HTTP ${response.status}: ${JSON.stringify(data).slice(0, 500)}`);
      }
      return { data, latencyMs: Math.round((performance.now() - started) * 100) / 100 };
    } catch (error) {
      lastError = error;
      if (attempt === 3) break;
      await new Promise((resolve) => setTimeout(resolve, 1_000 * attempt));
    }
  }
  throw lastError;
}

async function loadOrganKnowledge(organ) {
  const organDir = path.join(BACKEND, "anatomy", organ);
  const [structures, views] = await Promise.all([
    readFile(path.join(organDir, "structures.json"), "utf8").then(JSON.parse),
    readFile(path.join(organDir, "views.json"), "utf8").then(JSON.parse),
  ]);
  return { structures, views };
}

function normalize(value) {
  return String(value || "").toLocaleLowerCase("en-US").replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
}

function canonicalizer(structures) {
  const lookup = new Map();
  for (const structure of structures.structures || []) {
    for (const candidate of [structure.id, structure.label, ...(structure.aliases || [])]) {
      lookup.set(normalize(candidate), structure.id);
    }
  }
  return (value) => lookup.get(normalize(value)) || null;
}

export function scoreLabels(annotations, expectedIds, structures) {
  const canonicalize = canonicalizer(structures);
  const labels = (annotations || []).map((item) => String(item.label || "").trim()).filter(Boolean);
  const canonical = labels.map(canonicalize);
  const uniqueCanonical = [...new Set(canonical.filter(Boolean))];
  const expected = new Set(expectedIds || []);
  const requiredHits = uniqueCanonical.filter((id) => expected.has(id));
  const catalogMatches = canonical.filter(Boolean).length;
  const precision = uniqueCanonical.length ? requiredHits.length / uniqueCanonical.length : 0;
  const recall = expected.size ? requiredHits.length / expected.size : 0;
  return {
    accepted_label_count: labels.length,
    unique_catalog_label_count: uniqueCanonical.length,
    catalog_match_rate: labels.length ? catalogMatches / labels.length : 0,
    required_label_precision: precision,
    required_label_recall: recall,
    required_label_f1: precision + recall ? (2 * precision * recall) / (precision + recall) : 0,
    canonical_labels: uniqueCanonical,
    unmatched_labels: labels.filter((_, index) => !canonical[index]),
  };
}

function defaultView(knowledge) {
  const viewId = knowledge.views.default_view;
  const view = (knowledge.views.views || []).find((item) => item.id === viewId);
  if (!view) throw new Error(`Default view ${viewId} was not found`);
  return view;
}

function minimalEnhancedPayload(response) {
  const source = response.enhanced_prompt_json || {};
  const finalPrompt = source.final_prompt || response.enhanced_prompt;
  const anatomySpec = source.anatomy_spec || response.anatomy_spec;
  if (!finalPrompt || !anatomySpec?.is_anatomy) {
    throw new Error(`Prompt agent did not return a valid anatomy payload: ${JSON.stringify(response).slice(0, 800)}`);
  }
  return { schema_version: "1.0", final_prompt: finalPrompt, anatomy_spec: anatomySpec };
}

function conditionLabel(condition) {
  return condition === "raw_flux1_dev" ? "Raw FLUX.1-dev" : "Our pipeline";
}

async function runCondition({ organ, condition, seed, speedMode, outputDir, knowledge, pipelineContext }) {
  const originalPrompt = promptFor(organ);
  const stageLatencyMs = {};
  let promptPayload = null;
  let anatomySpec = pipelineContext.anatomySpec;

  if (condition === "our_pipeline") {
    stageLatencyMs.prompt = pipelineContext.promptLatencyMs;
    promptPayload = pipelineContext.promptPayload;
    anatomySpec = promptPayload.anatomy_spec;
  }

  const generationBody = condition === "raw_flux1_dev"
    ? {
        prompt: originalPrompt,
        speed_mode: speedMode,
        seed,
        domain: "generic",
        use_skill_rules: false,
      }
    : {
        enhanced_prompt_json: promptPayload,
        speed_mode: speedMode,
        seed,
        domain: "anatomy",
        use_skill_rules: true,
      };
  const generated = await postJson(`${URLS.image}/generate`, generationBody);
  stageLatencyMs.generation = generated.latencyMs;
  if (generated.data.error || !generated.data.image_base64) {
    throw new Error(generated.data.error || "Image agent returned no image");
  }

  const imageName = `${organ}_seed-${seed}_${condition}.png`;
  await writeFile(path.join(outputDir, "images", imageName), Buffer.from(generated.data.image_base64, "base64"));

  // The identical original prompt and anatomy target are used for both judges.
  const evaluated = await postJson(`${URLS.eval}/evaluate`, {
    image_base64: generated.data.image_base64,
    enhanced_prompt: null,
    raw_prompt: originalPrompt,
    anatomy_spec: anatomySpec,
    enable_anatomy_critic: true,
  });
  stageLatencyMs.evaluation = evaluated.latencyMs;
  if (evaluated.data.error) throw new Error(`Evaluator error: ${evaluated.data.error}`);

  const labeled = await postJson(`${URLS.interactive}/auto-labels`, {
    image_base64: generated.data.image_base64,
    domain: "anatomy",
    organ,
    view: anatomySpec.view || defaultView(knowledge).id,
    speed_mode: speedMode === "normal" ? "normal" : "pro",
  });
  stageLatencyMs.autoLabeling = labeled.latencyMs;
  if (labeled.data.error) throw new Error(`Auto-labeling error: ${labeled.data.error}`);

  const expectedIds = anatomySpec.required_structures || defaultView(knowledge).required_structures || [];
  return {
    protocol_version: "paper-component-comparison-v1",
    generated_at: new Date().toISOString(),
    organ,
    condition,
    condition_label: conditionLabel(condition),
    seed,
    original_prompt: originalPrompt,
    generation_prompt: promptPayload?.final_prompt || originalPrompt,
    anatomy_spec: anatomySpec,
    model: "black-forest-labs/FLUX.1-dev",
    generation_metadata: generated.data.generation_metadata || {},
    image_file: path.join("images", imageName).replaceAll("\\", "/"),
    stage_latency_ms: stageLatencyMs,
    metrics: Object.fromEntries(METRICS.map(({ key }) => [key, evaluated.data[key]])),
    evaluator_feedback: evaluated.data.vlm_feedback,
    anatomy_metrics: evaluated.data.anatomy_metrics || {},
    anatomy_hard_failures: evaluated.data.anatomy_hard_failures || [],
    auto_label_diagnostics: labeled.data.diagnostics || {},
    auto_labels: labeled.data.annotations || [],
    label_metrics: scoreLabels(labeled.data.annotations || [], expectedIds, knowledge.structures),
  };
}

function mean(values) {
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function sampleStd(values) {
  if (values.length < 2) return 0;
  const average = mean(values);
  return Math.sqrt(values.reduce((sum, value) => sum + (value - average) ** 2, 0) / (values.length - 1));
}

function summarizeValues(values) {
  const clean = values.filter((value) => Number.isFinite(value)).map(Number);
  return { n: clean.length, mean: clean.length ? mean(clean) : null, sd: clean.length ? sampleStd(clean) : null };
}

export function summarize(rows) {
  const summary = { conditions: {}, paired_deltas_pipeline_minus_raw: {} };
  const labelMetricKeys = ["accepted_label_count", "catalog_match_rate", "required_label_precision", "required_label_recall", "required_label_f1"];
  for (const condition of CONDITIONS) {
    const selected = rows.filter((row) => row.condition === condition && !row.error);
    summary.conditions[condition] = {
      runs: selected.length,
      metrics: Object.fromEntries(METRICS.map(({ key }) => [key, summarizeValues(selected.map((row) => row.metrics?.[key]))])),
      label_metrics: Object.fromEntries(labelMetricKeys.map((key) => [key, summarizeValues(selected.map((row) => row.label_metrics?.[key]))])),
    };
  }
  const byKey = new Map(rows.filter((row) => !row.error).map((row) => [`${row.organ}:${row.seed}:${row.condition}`, row]));
  for (const { key } of METRICS) {
    const deltas = [];
    for (const row of rows.filter((item) => item.condition === "our_pipeline" && !item.error)) {
      const raw = byKey.get(`${row.organ}:${row.seed}:raw_flux1_dev`);
      if (raw && Number.isFinite(raw.metrics?.[key]) && Number.isFinite(row.metrics?.[key])) {
        deltas.push(Number(row.metrics[key]) - Number(raw.metrics[key]));
      }
    }
    summary.paired_deltas_pipeline_minus_raw[key] = summarizeValues(deltas);
  }
  return summary;
}

function fixed(value, digits = 2) {
  return Number.isFinite(value) ? Number(value).toFixed(digits) : "NA";
}

function meanSd(item) {
  return item?.mean == null ? "NA" : `${fixed(item.mean)} ± ${fixed(item.sd)}`;
}

function markdownReport(rows, summary, options) {
  const lines = [
    "# Raw FLUX.1-dev vs our pipeline: paired component evaluation",
    "",
    `Protocol: \`paper-component-comparison-v1\`. Organs: ${options.organs.join(", ")}. Seeds: ${options.seeds.join(", ")}.`,
    "",
    "Both conditions used the same original prompt, FLUX.1-dev weights, inference tier, and seed. The evaluator received the same original prompt and anatomy target for each pair. The pipeline condition additionally used the prompt-agent persona/SKILL rules, deterministic anatomy prompt compiler, and anatomy image policy. Qwen-VL automatic labels were scored separately from the unannotated images.",
    "",
    "## Main metrics",
    "",
    "| Score | Range | Measuring model | Raw FLUX.1-dev, mean ± SD | Our pipeline, mean ± SD | Paired Δ | Pairs |",
    "|---|---:|---|---:|---:|---:|---:|",
  ];
  for (const metric of METRICS) {
    const raw = summary.conditions.raw_flux1_dev.metrics[metric.key];
    const pipeline = summary.conditions.our_pipeline.metrics[metric.key];
    const delta = summary.paired_deltas_pipeline_minus_raw[metric.key];
    lines.push(`| ${metric.label} | ${metric.range} | ${metric.model} | ${meanSd(raw)} | ${meanSd(pipeline)} | ${fixed(delta.mean)} | ${delta.n} |`);
  }
  lines.push(
    "",
    "## Qwen-VL name-labeling diagnostics",
    "",
    "These are ontology-matching diagnostics, not independent proof that every label is spatially correct.",
    "",
    "| Diagnostic | Raw FLUX.1-dev image, mean ± SD | Our pipeline image, mean ± SD |",
    "|---|---:|---:|",
  );
  const labelRows = [
    ["Accepted labels", "accepted_label_count"],
    ["Catalog match rate", "catalog_match_rate"],
    ["Required-label precision", "required_label_precision"],
    ["Required-label recall", "required_label_recall"],
    ["Required-label F1", "required_label_f1"],
  ];
  for (const [label, key] of labelRows) {
    lines.push(`| ${label} | ${meanSd(summary.conditions.raw_flux1_dev.label_metrics[key])} | ${meanSd(summary.conditions.our_pipeline.label_metrics[key])} |`);
  }
  lines.push(
    "",
    "## Publication note",
    "",
    "This run is a component smoke evaluation. Report its sample size and fixed-seed design. For inferential claims, run multiple pre-registered seeds on a held-out prompt set and add confidence intervals plus a paired significance test. Qwen-VL is used both for judging and labeling, so blinded human review should be reported as independent evidence.",
    "",
  );
  const qwenMetrics = ["visual_score", "pedagogical_score", "vlm_score"];
  const ceilingDetected = qwenMetrics.every((key) =>
    summary.conditions.raw_flux1_dev.metrics[key].sd === 0
    && summary.conditions.our_pipeline.metrics[key].sd === 0
  );
  if (ceilingDetected) {
    lines.push(
      "**Validity warning:** all Qwen image scores have zero variance in both conditions. This is a ceiling effect, so these scores do not establish equivalence or superiority. See `manual-visual-audit.md` for visible view/section mismatches that the automatic critic missed.",
      "",
    );
  }
  return lines.join("\n");
}

function csvReport(summary) {
  const escape = (value) => `"${String(value).replaceAll('"', '""')}"`;
  const lines = [["score", "range", "measuring_model", "raw_n", "raw_mean", "raw_sd", "pipeline_n", "pipeline_mean", "pipeline_sd", "paired_n", "paired_delta_mean", "paired_delta_sd"]];
  for (const metric of METRICS) {
    const raw = summary.conditions.raw_flux1_dev.metrics[metric.key];
    const pipeline = summary.conditions.our_pipeline.metrics[metric.key];
    const delta = summary.paired_deltas_pipeline_minus_raw[metric.key];
    lines.push([metric.label, metric.range, metric.model, raw.n, raw.mean, raw.sd, pipeline.n, pipeline.mean, pipeline.sd, delta.n, delta.mean, delta.sd]);
  }
  return lines.map((row) => row.map(escape).join(",")).join("\n") + "\n";
}

async function writeReports(outputDir, rows, options) {
  const summary = summarize(rows);
  const payload = {
    protocol: {
      id: "paper-component-comparison-v1",
      created_at: new Date().toISOString(),
      organs: options.organs,
      seeds: options.seeds,
      conditions: CONDITIONS,
      speed_mode: options.speedMode,
      endpoints: URLS,
      evaluator_system_context: ["config/global/PERSONA.md", "agents/eval-agent/SKILL.md", "agents/eval-agent/PERSONA.md", "agents/eval-agent/MEMENTO.md"],
      labeler_system_context: ["config/global/PERSONA.md", "agents/interactive-agent/SKILL.md", "agents/interactive-agent/PERSONA.md", "agents/interactive-agent/MEMENTO.md"],
    },
    summary,
    rows,
  };
  await Promise.all([
    writeFile(path.join(outputDir, "results.json"), JSON.stringify(payload, null, 2) + "\n"),
    writeFile(path.join(outputDir, "metrics-table.md"), markdownReport(rows, summary, options)),
    writeFile(path.join(outputDir, "metrics-table.csv"), csvReport(summary)),
  ]);
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  await mkdir(path.join(options.outputDir, "images"), { recursive: true });
  const resultsPath = path.join(options.outputDir, "results.json");
  let rows = [];
  try {
    rows = JSON.parse(await readFile(resultsPath, "utf8")).rows || [];
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
  }
  if (options.reportOnly) {
    if (!rows.length) throw new Error(`No existing rows found in ${resultsPath}`);
    await writeReports(options.outputDir, rows, options);
    console.log(`Wrote ${path.join(options.outputDir, "metrics-table.md")}`);
    return;
  }
  const completed = new Set(rows.filter((row) => !row.error).map((row) => `${row.organ}:${row.seed}:${row.condition}`));

  for (const organ of options.organs) {
    const knowledge = await loadOrganKnowledge(organ);
    for (const seed of options.seeds) {
      const originalPrompt = promptFor(organ);
      console.log(`\n[${organ}, seed ${seed}] preparing shared anatomy target`);
      const prepared = await postJson(`${URLS.prompt}/enhance`, {
        raw_prompt: originalPrompt,
        speed_mode: options.speedMode,
        use_memento: false,
        use_skill_rules: true,
        seed,
        route_override: "anatomy",
        model_variant: "base",
      });
      const sharedPayload = minimalEnhancedPayload(prepared.data);
      const pipelineContext = {
        anatomySpec: sharedPayload.anatomy_spec,
        promptPayload: sharedPayload,
        promptLatencyMs: prepared.latencyMs,
      };

      for (const condition of CONDITIONS) {
        const key = `${organ}:${seed}:${condition}`;
        if (completed.has(key)) {
          console.log(`[${organ}, seed ${seed}] ${condition}: reusing completed result`);
          continue;
        }
        console.log(`[${organ}, seed ${seed}] ${condition}: generating, evaluating, and labeling`);
        try {
          const row = await runCondition({ organ, condition, seed, speedMode: options.speedMode, outputDir: options.outputDir, knowledge, pipelineContext });
          rows = rows.filter((item) => `${item.organ}:${item.seed}:${item.condition}` !== key);
          rows.push(row);
          completed.add(key);
          console.log(`[${organ}, seed ${seed}] ${condition}: CLIP=${fixed(row.metrics.clip_score)}, visual=${fixed(row.metrics.visual_score)}, pedagogical=${fixed(row.metrics.pedagogical_score)}, VLM=${fixed(row.metrics.vlm_score)}, labels=${row.label_metrics.accepted_label_count}`);
        } catch (error) {
          console.error(`[${organ}, seed ${seed}] ${condition}: FAILED: ${error.message}`);
          rows = rows.filter((item) => `${item.organ}:${item.seed}:${item.condition}` !== key);
          rows.push({ protocol_version: "paper-component-comparison-v1", generated_at: new Date().toISOString(), organ, condition, seed, original_prompt: originalPrompt, error: error.message });
        }
        await writeReports(options.outputDir, rows, options);
      }
    }
  }
  await writeReports(options.outputDir, rows, options);
  console.log(`\nWrote ${path.join(options.outputDir, "metrics-table.md")}`);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    console.error(error.stack || error.message);
    process.exitCode = 1;
  });
}
