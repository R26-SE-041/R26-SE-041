# Raw FLUX.1-dev vs our pipeline: paired component evaluation

Protocol: `paper-component-comparison-v1`. Organs: heart, brain, kidneys, liver, lungs. Seeds: 260901.

Both conditions used the same original prompt, FLUX.1-dev weights, inference tier, and seed. The evaluator received the same original prompt and anatomy target for each pair. The pipeline condition additionally used the prompt-agent persona/SKILL rules, deterministic anatomy prompt compiler, and anatomy image policy. Qwen-VL automatic labels were scored separately from the unannotated images.

## Main metrics

| Score | Range | Measuring model | Raw FLUX.1-dev, mean ± SD | Our pipeline, mean ± SD | Paired Δ | Pairs |
|---|---:|---|---:|---:|---:|---:|
| CLIPScore | 0–100; higher is better | openai/clip-vit-base-patch16 | 31.82 ± 1.17 | 31.06 ± 1.28 | -0.77 | 5 |
| Prompt alignment / Visual score | 0–10 | Qwen2.5-VL-7B-Instruct | 9.00 ± 0.00 | 9.00 ± 0.00 | 0.00 | 5 |
| Educational usefulness / Pedagogical score | 0–10 | Qwen2.5-VL-7B-Instruct | 9.00 ± 0.00 | 9.00 ± 0.00 | 0.00 | 5 |
| VLM score | 0–10 | Mean of the two Qwen-VL scores | 9.00 ± 0.00 | 9.00 ± 0.00 | 0.00 | 5 |

## Qwen-VL name-labeling diagnostics

These are ontology-matching diagnostics, not independent proof that every label is spatially correct.

| Diagnostic | Raw FLUX.1-dev image, mean ± SD | Our pipeline image, mean ± SD |
|---|---:|---:|
| Accepted labels | 4.40 ± 2.30 | 4.00 ± 2.24 |
| Catalog match rate | 0.60 ± 0.28 | 0.49 ± 0.31 |
| Required-label precision | 0.73 ± 0.25 | 0.57 ± 0.43 |
| Required-label recall | 0.20 ± 0.07 | 0.10 ± 0.06 |
| Required-label F1 | 0.30 ± 0.09 | 0.17 ± 0.09 |

## Publication note

This run is a component smoke evaluation. Report its sample size and fixed-seed design. For inferential claims, run multiple pre-registered seeds on a held-out prompt set and add confidence intervals plus a paired significance test. Qwen-VL is used both for judging and labeling, so blinded human review should be reported as independent evidence.

**Validity warning:** all Qwen image scores have zero variance in both conditions. This is a ceiling effect, so these scores do not establish equivalence or superiority. See `manual-visual-audit.md` for visible view/section mismatches that the automatic critic missed.
