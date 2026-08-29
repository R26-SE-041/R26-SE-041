# Five-organ prompt-agent fine-tuning

This directory contains the reproducible workflow for the first trainable component of the anatomy pipeline.

## Scope

- Base model: `Qwen/Qwen2.5-3B-Instruct`
- Organs: brain, heart, kidneys, liver, lungs
- Adapter: one shared `anatomy_lora` adapter
- Training targets: anatomy requests produce canonical `anatomy_spec` JSON only; deterministic application code builds FLUX prompts
- Frozen split: 3,600 train / 450 validation / 450 test

## Files

- `generate_dataset.py`: deterministic dataset generator.
- `validate_dataset.py`: hashes, schema, canonical vocabulary, balance, and leakage checks.
- `data/`: generated JSONL and SHA-256 manifest.
- `EduVision_Qwen25_3B_Anatomy_QLoRA.ipynb`: Colab QLoRA training.
- `evaluate_models.py`: paired deterministic base-versus-LoRA evaluator.
- `EduVision_Prompt_Base_vs_LoRA.ipynb`: Colab evaluation runner.

## Reproduce locally

From `backend/`:

```powershell
python -m training.prompt.generate_dataset
python -m training.prompt.validate_dataset
python -m unittest discover -s tests -v
```

Dataset contract version 2.0.0 supersedes the earlier prompt-writing target. Do not modify or regenerate this test split after seeing model results. If the knowledge or generator changes again, increment the dataset version and report the new hashes.

## Train in Colab

1. Open `EduVision_Qwen25_3B_Anatomy_QLoRA.ipynb` in Colab.
2. Select an A100 or L4 GPU runtime.
3. Upload all four files from `data/` when requested.
4. Run cells in order.
5. Download `prompt-anatomy-lora.zip`.

The exported directory must contain:

```text
prompt-anatomy-lora/
├── adapter_config.json
├── adapter_model.safetensors
├── tokenizer.json
└── training_provenance.json
```

## Evaluate

Open `EduVision_Prompt_Base_vs_LoRA.ipynb` and upload:

- `data/test.jsonl`
- `data/manifest.json`
- `evaluate_models.py`
- `prompt-anatomy-lora.zip`

Run the balanced 60-example pilot first, then the complete 450-example paired evaluation. The full run produces raw outputs, per-organ summaries, latency percentiles, hard-failure rates, and a paired bootstrap confidence interval.

Automated prompt metrics measure contract adherence; they do not replace medical expert review of downstream images.
