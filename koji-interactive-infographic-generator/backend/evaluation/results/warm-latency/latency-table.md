# Warm-state Modal latency (visualization subsystem)

Prompts: `eye`, `heart`, `skin`. Fixed seed: 260902. Repetitions per prompt: 3. Measured passes: 1.

Speed mode `normal`, 512x512, 25 inference steps, guidance 3.5 - the same configuration as the Table III quality comparison, so latency and quality describe one deployment.

Cold starts are excluded: 1 discarded warm-up pass(es) boot and load every GPU container before timing begins, and all measured calls are issued back-to-back inside each container's scaledown window.

| Stage | Condition | Serving model / GPU | Warm mean +/- SD (s) | p50 (s) | p95 (s) |
|---|---|---|---:|---:|---:|
| Image synthesis (raw baseline) | Raw FLUX.1-dev | FLUX.1-dev, A10G | 97.0 +/- 0.0 | 97.0 | 97.0 |
| Prompt enhancement | Our full pipeline | Qwen2.5-3B-Instruct, T4 | 38.9 +/- 0.0 | 38.9 | 38.9 |
| Image synthesis | Our full pipeline | FLUX.1-dev, A10G | 87.9 +/- 0.0 | 87.9 | 87.9 |
| Dual-critic evaluation | Our full pipeline | CLIP + Qwen2.5-VL-7B, A10G | 13.3 +/- 0.0 | 13.3 | 13.3 |
| Grounded auto-labeling | Our full pipeline | Qwen2.5-VL-7B, A10G | 44.5 +/- 0.0 | 44.5 | 44.5 |

| End-to-end condition | Modal calls | Warm mean +/- SD (s) | p50 (s) | p95 (s) |
|---|---:|---:|---:|---:|
| Raw FLUX.1-dev | 1 | 97.0 +/- 0.0 | 97.0 | 97.0 |
| Our full pipeline | 4 | 184.7 +/- 0.0 | 184.7 | 184.7 |

Warm-state overhead of the agentic pipeline over a single raw diffusion pass: +87.7 s (1.90x).

## Per-pass measurements

| Prompt | Rep | Raw gen (s) | Enhance (s) | Gen (s) | Critic (s) | Label (s) | Pipeline total (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| eye | 1 | 97.0 | 38.9 | 87.9 | 13.3 | 44.5 | 184.7 |

## Discarded warm-up passes (cold start, not reported in the paper)

| Prompt | Raw gen (s) | Enhance (s) | Gen (s) | Critic (s) | Label (s) |
|---|---:|---:|---:|---:|---:|
| eye | 119.6 | 38.8 | 97.3 | 12.6 | 69.8 |
