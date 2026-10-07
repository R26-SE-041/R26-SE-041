import assert from "node:assert/strict";
import test from "node:test";

import { summarize } from "./run_end_to_end_baseline.mjs";

test("summarize calculates paired full-pipeline improvements", () => {
  const rows = [
    { prompt: "eye", condition: "raw_flux1_dev", metrics: { clip_score: 20, visual_score: 5, pedagogical_score: 4, vlm_score: 4.5 } },
    { prompt: "eye", condition: "our_full_pipeline", metrics: { clip_score: 18, visual_score: 9, pedagogical_score: 8, vlm_score: 8.5 } },
  ];
  const result = summarize(rows);
  assert.equal(result.paired_deltas_pipeline_minus_raw.clip_score.mean, -2);
  assert.equal(result.paired_deltas_pipeline_minus_raw.visual_score.mean, 4);
  assert.equal(result.paired_deltas_pipeline_minus_raw.pedagogical_score.mean, 4);
  assert.equal(result.paired_deltas_pipeline_minus_raw.vlm_score.mean, 4);
});

