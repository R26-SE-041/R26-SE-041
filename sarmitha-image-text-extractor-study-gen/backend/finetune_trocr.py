import modal

# Define the Modal image with all necessary training dependencies
image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "torch==2.3.1",
    "transformers==4.46.3",
    "datasets",
    "sentencepiece==0.2.0",
    "pillow==10.3.0",
    "accelerate",
    "evaluate",
    "jiwer", # For Word Error Rate (WER) and Character Error Rate (CER) calculation
)

app = modal.App("finetune-sinhala-trocr", image=image)

# Create a persistent volume to store your dataset and model checkpoints
volume = modal.Volume.from_name("sinhala-trocr-data", create_if_missing=True)

@app.function(
    gpu="A10G", # Use a powerful GPU with 24GB VRAM for training
    timeout=86400, # Allow running for up to 24 hours
    volumes={"/data": volume}
)
def train():
    import os
    import torch
    from transformers import (
        VisionEncoderDecoderModel, 
        AutoTokenizer, 
        Seq2SeqTrainer, 
        Seq2SeqTrainingArguments, 
        default_data_collator
    )
    from datasets import load_dataset
    from torchvision import transforms
    from PIL import Image
    import evaluate
    
    # ---------------------------------------------------------
    # 1. Setup & Configuration
    # ---------------------------------------------------------
    HF_MODEL = "hasindu-k/sinhala-handwritten-notes-v3"
    DATA_DIR = "/data/dataset" # Place your dataset here
    OUTPUT_DIR = "/data/model_output"
    
    # The TrOCR preprocessing uses squished 384x384 image dimensions for this specific checkpoint
    transform = transforms.Compose([
        transforms.Resize((384, 384), interpolation=transforms.InterpolationMode.BICUBIC),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5])
    ])
    
    print("Loading tokenizer and model...")
    tokenizer = AutoTokenizer.from_pretrained(HF_MODEL)
    model = VisionEncoderDecoderModel.from_pretrained(HF_MODEL)
    
    # Ensure generation tokens match the config
    model.config.decoder_start_token_id = 2
    model.config.pad_token_id = 0
    model.config.eos_token_id = 3
    model.config.vocab_size = model.config.decoder.vocab_size
    
    # ---------------------------------------------------------
    # 2. Dataset Preparation
    # ---------------------------------------------------------
    # Instructions: Upload your dataset to the Modal volume via `modal volume put sinhala-trocr-data ./local_dataset /dataset`
    # Your dataset should be in a HuggingFace friendly format (e.g., metadata.jsonl with {"file_name": "img1.png", "text": "..."})
    if not os.path.exists(DATA_DIR):
        print(f"Dataset directory not found at {DATA_DIR}!")
        print("Please upload your dataset to the Modal volume before running training.")
        print("Example command: modal volume put sinhala-trocr-data /path/to/local/dataset /dataset")
        return
        
    print("Loading dataset...")
    # Load the dataset (assuming you have a train split in the folder)
    dataset = load_dataset("imagefolder", data_dir=DATA_DIR)
    
    def preprocess_function(examples):
        pixel_values = []
        for img in examples["image"]:
            # Convert to RGB and apply transforms
            pixel_values.append(transform(img.convert("RGB")))
            
        # Tokenize text
        labels = tokenizer(
            examples["text"], 
            padding="max_length", 
            max_length=128, 
            truncation=True
        ).input_ids
        
        # Replace padding token id with -100 to ignore it in loss calculation
        labels = [[label if label != tokenizer.pad_token_id else -100 for label in l] for l in labels]
        
        return {"pixel_values": pixel_values, "labels": labels}
    
    print("Preprocessing dataset...")
    # Map the preprocessing function to the dataset
    processed_dataset = dataset.map(
        preprocess_function, 
        batched=True, 
        remove_columns=["image", "text"] # Remove original columns to save memory
    )
    
    # ---------------------------------------------------------
    # 3. Training Setup
    # ---------------------------------------------------------
    cer_metric = evaluate.load("cer")
    
    def compute_metrics(pred):
        labels_ids = pred.label_ids
        pred_ids = pred.predictions
        
        # Decode predictions and labels
        pred_str = tokenizer.batch_decode(pred_ids, skip_special_tokens=True)
        labels_ids[labels_ids == -100] = tokenizer.pad_token_id
        label_str = tokenizer.batch_decode(labels_ids, skip_special_tokens=True)
        
        cer = cer_metric.compute(predictions=pred_str, references=label_str)
        return {"cer": cer}
    
    training_args = Seq2SeqTrainingArguments(
        predict_with_generate=True,
        evaluation_strategy="steps" if "test" in dataset else "no",
        per_device_train_batch_size=8,
        per_device_eval_batch_size=8,
        fp16=True, # Use mixed precision for faster A10G training
        output_dir=OUTPUT_DIR,
        logging_steps=10,
        save_steps=1000,
        eval_steps=1000 if "test" in dataset else None,
        save_total_limit=2,
        num_train_epochs=5,
        learning_rate=5e-5,
    )
    
    trainer = Seq2SeqTrainer(
        model=model,
        tokenizer=tokenizer,
        args=training_args,
        compute_metrics=compute_metrics if "test" in dataset else None,
        train_dataset=processed_dataset["train"],
        eval_dataset=processed_dataset.get("test"),
        data_collator=default_data_collator,
    )
    
    # ---------------------------------------------------------
    # 4. Execute Training
    # ---------------------------------------------------------
    print("Starting training...")
    trainer.train()
    
    print(f"Training complete! Saving final model to {OUTPUT_DIR}/final_model")
    trainer.save_model(os.path.join(OUTPUT_DIR, "final_model"))
    tokenizer.save_pretrained(os.path.join(OUTPUT_DIR, "final_model"))
    
    print("Model saved to the Modal Volume! You can download it using:")
    print(f"modal volume get sinhala-trocr-data {OUTPUT_DIR}/final_model ./local_model_folder")

@app.local_entrypoint()
def main():
    print("Initiating TrOCR Finetuning Job on Modal...")
    train.remote()
