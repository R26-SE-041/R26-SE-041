import assert from "node:assert/strict";
import test from "node:test";

import { scoreLabels, summarize } from "./paper_component_comparison.mjs";

const structures = {
  structures: [
    { id: "right_atrium", label: "Right atrium", aliases: ["RA"] },
    { id: "aorta", label: "Aorta", aliases: ["aortic arch"] },
  ],
};

test("scoreLabels canonicalizes aliases and reports required coverage", () => {
  const result = scoreLabels(
    [{ label: "RA" }, { label: "Aortic arch" }, { label: "unknown" }],
    ["right_atrium", "aorta"],
    structures,
  );
  assert.equal(result.accepted_label_count, 3);
  assert.equal(result.unique_catalog_label_count, 2);
  assert.equal(result.catalog_match_rate, 2 / 3);
  assert.equal(result.required_label_precision, 1);
  assert.equal(result.required_label_recall, 1);
  assert.deepEqual(result.unmatched_labels, ["unknown"]);
});

test("summarize computes paired pipeline-minus-raw deltas", () => {
  const rows = [
    { organ: "heart", seed: 1, condition: "raw_flux1_dev", metrics: { clip_score: 20, visual_score: 4, pedagogical_score: 3, vlm_score: 3.5 }, label_metrics: {} },
    { organ: "heart", seed: 1, condition: "our_pipeline", metrics: { clip_score: 24, visual_score: 8, pedagogical_score: 7, vlm_score: 7.5 }, label_metrics: {} },
  ];
  const summary = summarize(rows);
  assert.equal(summary.paired_deltas_pipeline_minus_raw.clip_score.mean, 4);
  assert.equal(summary.paired_deltas_pipeline_minus_raw.visual_score.mean, 4);
  assert.equal(summary.paired_deltas_pipeline_minus_raw.pedagogical_score.mean, 4);
  assert.equal(summary.paired_deltas_pipeline_minus_raw.vlm_score.mean, 4);
});

