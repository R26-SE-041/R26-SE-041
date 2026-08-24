# Heart evaluation protocol

The runner compares three conditions with the same prompts and fixed seeds:

1. `raw_base`: raw user prompt directly to base FLUX.
2. `agentic_pipeline`: prompt rules, memory, clean-image constraints, Qwen-VL localization, and SVG layout using base weights.
3. `finetuned_pipeline`: the same pipeline with the heart LoRA adapters.

This separation prevents claiming an orchestration gain as a fine-tuning gain. Use a held-out test suite that was not used for LoRA training or memory promotion.

From `backend/`, after all Modal agents and adapters are deployed:

```powershell
python -m evaluation.anatomy.run_component_eval `
  --prompt-url $env:PROMPT_AGENT_URL `
  --image-url $env:IMAGE_AGENT_URL `
  --interactive-url $env:INTERACTIVE_AGENT_URL `
  --eval-url $env:EVAL_AGENT_URL `
  --output evaluation/anatomy/results.json
```

Report structure recall, relation accuracy, orientation correctness, clean-image compliance, canonical-label recall, overlap/crossing rates, hard-failure rate, and mean/p50/p95 latency. Keep the generated images for blinded expert review; automated VLM scores are supporting evidence, not medical ground truth.
