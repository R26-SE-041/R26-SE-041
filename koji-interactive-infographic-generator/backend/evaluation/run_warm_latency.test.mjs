import assert from "node:assert/strict";
import test from "node:test";

import { summarize, totalsFor } from "./run_warm_latency.mjs";

const pass = (overrides) => ({
  prompt: "heart",
  raw_generation_ms: 40_000,
  enhancement_ms: 4_000,
  generation_ms: 42_000,
  critic_ms: 8_000,
  labeling_ms: 26_000,
  ...overrides,
});

test("pipeline total sums only its own four Modal stages", () => {
  assert.equal(totalsFor(pass({})).our_full_pipeline, 80_000);
  assert.equal(totalsFor(pass({})).raw_flux1_dev, 40_000);
});

test("warm-up passes are excluded from every reported statistic", () => {
  const summary = summarize([
    pass({ warmup: true, raw_generation_ms: 400_000, generation_ms: 420_000 }),
    pass({ rep: 1 }),
    pass({ rep: 2, raw_generation_ms: 50_000 }),
  ]);
  assert.equal(summary.stages.raw_generation_ms.n, 2);
  assert.equal(summary.stages.raw_generation_ms.mean, 45_000);
  assert.equal(summary.totals.our_full_pipeline.mean, 80_000);
});

test("failed passes are excluded and overhead is reported against the raw call", () => {
  const summary = summarize([
    { prompt: "skin", rep: 1, error: "boom" },
    pass({ rep: 1 }),
  ]);
  assert.equal(summary.stages.critic_ms.n, 1);
  assert.equal(summary.pipeline_overhead_ms, 40_000);
  assert.equal(summary.pipeline_overhead_ratio, 2);
});

test("percentiles use nearest rank so they stay inside the observed sample", () => {
  const summary = summarize([
    pass({ rep: 1, generation_ms: 10_000 }),
    pass({ rep: 2, generation_ms: 20_000 }),
    pass({ rep: 3, generation_ms: 90_000 }),
  ]);
  assert.equal(summary.stages.generation_ms.p50, 20_000);
  assert.equal(summary.stages.generation_ms.p95, 90_000);
});
