# End-to-end baseline comparison

Minimal prompts: `eye`, `heart`, `skin`. Fixed seed: 260902.

Raw baseline is the one-word prompt sent directly to FLUX.1-dev. Our full pipeline uses the Anatomy-workspace prefix, deployed Qwen prompt enhancement with system persona/SKILL/MEMENTO, FLUX.1-dev, Qwen-VL automatic name labeling, and the rendered frontend-style overlay. Metrics compare the raw PNG with the final labeled pipeline PNG against the same original one-word prompt.

| Score | Range | Measuring model | Raw FLUX.1-dev, mean +/- SD | Our full pipeline, mean +/- SD | Paired delta | Pairs |
|---|---:|---|---:|---:|---:|---:|
| CLIPScore | 0-100; higher is better | openai/clip-vit-base-patch16 | 27.36 +/- 1.67 | 23.71 +/- 2.47 | -3.65 | 3 |
| Prompt alignment / Visual score | 0-10 | Qwen2.5-VL-7B-Instruct | 6.00 +/- 3.46 | 8.67 +/- 0.58 | 2.67 | 3 |
| Educational usefulness / Pedagogical score | 0-10 | Qwen2.5-VL-7B-Instruct | 5.00 +/- 3.46 | 7.67 +/- 0.58 | 2.67 | 3 |
| VLM score | 0-10 | Mean of Qwen-VL visual and pedagogical scores | 5.50 +/- 3.46 | 8.17 +/- 0.58 | 2.67 | 3 |

## Per-prompt results

| Prompt | Condition | CLIPScore | Visual | Pedagogical | VLM average | Rendered labels |
|---|---|---:|---:|---:|---:|---:|
| eye | Raw FLUX.1-dev | 28.71 | 8.00 | 7.00 | 7.50 | 0 |
| eye | Our full pipeline | 24.30 | 9.00 | 8.00 | 8.50 | 8 |
| heart | Raw FLUX.1-dev | 27.87 | 8.00 | 7.00 | 7.50 | 0 |
| heart | Our full pipeline | 25.82 | 9.00 | 8.00 | 8.50 | 8 |
| skin | Raw FLUX.1-dev | 25.50 | 2.00 | 1.00 | 1.50 | 0 |
| skin | Our full pipeline | 21.00 | 8.00 | 7.00 | 7.50 | 8 |

CLIPScore is lower for the pipeline in this smoke run. The pipeline artifact includes large text-label boxes and callout lines, while CLIP is evaluated against a one-word prompt; the Qwen educational metrics directly capture the intended labeled-diagram benefit.

**Observed skin limitation:** the current general-anatomy route turns `skin` into a whole-body internal-anatomy image and Qwen accepts unrelated labels. Do not present that example as anatomically correct skin labeling without fixing the route and label validation.

This is a three-prompt, one-seed smoke comparison matching the supplied screenshots, not an inferential experiment. For a paper claim, repeat on a pre-registered held-out prompt set with multiple seeds and independent human scoring.
