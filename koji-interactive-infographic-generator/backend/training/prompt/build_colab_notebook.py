"""Build the checked-in Colab notebook from readable, reviewable cell sources."""

from __future__ import annotations

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def markdown(source: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": source.splitlines(keepends=True)}


def code(source: str) -> dict:
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": source.splitlines(keepends=True)}


CELLS = [
    markdown("""# EduVision five-organ prompt-agent QLoRA

Fine-tunes `Qwen/Qwen2.5-3B-Instruct` on the frozen EduVision dataset for heart, brain, lungs, liver, and kidneys. The notebook validates dataset hashes before training, masks system/user tokens from the loss, evaluates only on validation during training, and leaves the held-out test split untouched for the paired evaluator.

Recommended runtime: Colab **A100** or **L4**. Do not enable a CPU runtime."""),
    code("""# Pinned together to avoid breaking Trainer/PEFT interfaces.
!pip -q install \
  "transformers==4.51.3" "peft==0.15.2" "accelerate==1.6.0" \
  "datasets==3.5.0" "bitsandbytes==0.45.5" "sentencepiece>=0.2.0"""),
    code("""import hashlib, json, os, shutil
from pathlib import Path
import torch

assert torch.cuda.is_available(), "Select Runtime > Change runtime type > GPU"
gpu_name = torch.cuda.get_device_name(0)
major, _ = torch.cuda.get_device_capability(0)
print("GPU:", gpu_name)
print("BF16 supported:", torch.cuda.is_bf16_supported())
assert torch.cuda.get_device_properties(0).total_memory >= 14 * 1024**3, "At least 14 GB VRAM is required"
"""),
    markdown("""## Upload the frozen dataset

Select these four files from `backend/training/prompt/data/`: `train.jsonl`, `validation.jsonl`, `test.jsonl`, and `manifest.json`. The test file is uploaded only so its hash can be locked; training never loads it."""),
    code("""from google.colab import files

uploaded = files.upload()
expected = {"train.jsonl", "validation.jsonl", "test.jsonl", "manifest.json"}
missing = expected - set(uploaded)
assert not missing, f"Missing files: {sorted(missing)}"
DATA_DIR = Path("/content/eduvision_prompt_data")
DATA_DIR.mkdir(exist_ok=True)
for name in expected:
    (DATA_DIR / name).write_bytes(uploaded[name])
print("Dataset uploaded to", DATA_DIR)"""),
    code("""manifest = json.loads((DATA_DIR / "manifest.json").read_text())
for name, expected_hash in manifest["sha256"].items():
    actual = hashlib.sha256((DATA_DIR / name).read_bytes()).hexdigest()
    assert actual == expected_hash, f"Hash mismatch: {name}"
assert manifest["counts"]["train"]["total"] == 3600
assert manifest["counts"]["validation"]["total"] == 450
assert manifest["counts"]["test"]["total"] == 450
print(json.dumps(manifest["counts"], indent=2))
print("Dataset hashes verified; held-out test hash locked.")"""),
    code("""from datasets import load_dataset
from transformers import AutoTokenizer

MODEL_ID = "Qwen/Qwen2.5-3B-Instruct"
MAX_LENGTH = 2048
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, use_fast=True)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

dataset = load_dataset("json", data_files={
    "train": str(DATA_DIR / "train.jsonl"),
    "validation": str(DATA_DIR / "validation.jsonl"),
})
print(dataset)"""),
    code("""def tokenize_with_assistant_only_loss(example):
    messages = example["messages"]
    prompt_messages = messages[:-1]
    full_text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
    prompt_text = tokenizer.apply_chat_template(prompt_messages, tokenize=False, add_generation_prompt=True)
    full = tokenizer(full_text, truncation=True, max_length=MAX_LENGTH, add_special_tokens=False)
    prefix = tokenizer(prompt_text, truncation=True, max_length=MAX_LENGTH, add_special_tokens=False)
    labels = list(full["input_ids"])
    prefix_length = min(len(prefix["input_ids"]), len(labels))
    labels[:prefix_length] = [-100] * prefix_length
    assert any(value != -100 for value in labels), "Assistant target was fully truncated"
    full["labels"] = labels
    return full

tokenized = dataset.map(
    tokenize_with_assistant_only_loss,
    remove_columns=dataset["train"].column_names,
    desc="Tokenizing and masking prompt tokens",
)
print(tokenized)"""),
    code("""from transformers import AutoModelForCausalLM, BitsAndBytesConfig, DataCollatorForSeq2Seq
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

compute_dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
quantization = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_use_double_quant=True,
    bnb_4bit_compute_dtype=compute_dtype,
)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID,
    quantization_config=quantization,
    device_map={"": 0},
    torch_dtype=compute_dtype,
)
model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
model.config.use_cache = False
lora_config = LoraConfig(
    r=16,
    lora_alpha=32,
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM",
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
)
model = get_peft_model(model, lora_config)
model.print_trainable_parameters()
collator = DataCollatorForSeq2Seq(tokenizer=tokenizer, padding=True, label_pad_token_id=-100)"""),
    code("""from transformers import Trainer, TrainingArguments, set_seed

set_seed(26041)
OUTPUT_DIR = "/content/eduvision-qwen25-3b-anatomy-lora"
args = TrainingArguments(
    output_dir=OUTPUT_DIR,
    num_train_epochs=2,
    per_device_train_batch_size=1,
    per_device_eval_batch_size=1,
    gradient_accumulation_steps=8,
    learning_rate=1e-4,
    warmup_ratio=0.05,
    lr_scheduler_type="cosine",
    weight_decay=0.01,
    max_grad_norm=1.0,
    logging_steps=10,
    eval_strategy="steps",
    eval_steps=100,
    save_strategy="steps",
    save_steps=100,
    save_total_limit=2,
    load_best_model_at_end=True,
    metric_for_best_model="eval_loss",
    greater_is_better=False,
    bf16=torch.cuda.is_bf16_supported(),
    fp16=not torch.cuda.is_bf16_supported(),
    gradient_checkpointing=True,
    optim="paged_adamw_8bit",
    report_to="none",
    remove_unused_columns=False,
    seed=26041,
    data_seed=26041,
)
trainer = Trainer(
    model=model,
    args=args,
    train_dataset=tokenized["train"],
    eval_dataset=tokenized["validation"],
    data_collator=collator,
)
print("Ready to train. Test split has not been loaded into Trainer.")"""),
    code("""train_result = trainer.train()
print(train_result)
print(trainer.evaluate())"""),
    code("""ADAPTER_DIR = Path("/content/prompt-anatomy-lora")
trainer.model.save_pretrained(ADAPTER_DIR, safe_serialization=True)
tokenizer.save_pretrained(ADAPTER_DIR)
provenance = {
    "base_model": MODEL_ID,
    "dataset": manifest["dataset"],
    "dataset_version": manifest["version"],
    "dataset_sha256": manifest["sha256"],
    "seed": 26041,
    "gpu": gpu_name,
    "training": {"epochs": 2, "learning_rate": 1e-4, "lora_rank": 16, "lora_alpha": 32},
}
(ADAPTER_DIR / "training_provenance.json").write_text(json.dumps(provenance, indent=2))
assert (ADAPTER_DIR / "adapter_config.json").is_file()
assert (ADAPTER_DIR / "adapter_model.safetensors").is_file()
archive = shutil.make_archive("/content/prompt-anatomy-lora", "zip", ADAPTER_DIR)
print("Adapter exported:", archive)"""),
    code("""# Download the adapter. Keep this ZIP private until evaluation is complete.
from google.colab import files
files.download("/content/prompt-anatomy-lora.zip")"""),
    markdown("""## Next

Do not evaluate on the training or validation files. Run the separate base-vs-LoRA evaluator on `test.jsonl`. It uses deterministic decoding, validates canonical IDs, records parse failures, and emits paired latency/accuracy rows."""),
]


def build() -> Path:
    notebook = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "colab": {"name": "EduVision_Qwen25_3B_Anatomy_QLoRA.ipynb", "provenance": []},
            "kernelspec": {"display_name": "Python 3", "name": "python3"},
            "language_info": {"name": "python"},
            "accelerator": "GPU",
        },
        "cells": CELLS,
    }
    output = HERE / "EduVision_Qwen25_3B_Anatomy_QLoRA.ipynb"
    output.write_text(json.dumps(notebook, indent=1), encoding="utf-8", newline="\n")
    return output


if __name__ == "__main__":
    print(build())
