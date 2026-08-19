import modal

image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "torch==2.3.1",
    "transformers==4.46.3",
    "sentencepiece==0.2.0",
    "pillow==10.3.0"
)

app = modal.App("test-trocr", image=image)

@app.function(gpu="T4")
def test_trocr():
    import torch
    import math
    from transformers import AutoTokenizer, VisionEncoderDecoderModel, ViTImageProcessor
    
    HF_MODEL = "hasindu-k/sinhala-handwritten-notes-v3"
    
    tokenizer = AutoTokenizer.from_pretrained(HF_MODEL)
    model = VisionEncoderDecoderModel.from_pretrained(HF_MODEL)
    processor = ViTImageProcessor.from_pretrained(HF_MODEL)
    
    print("=== Tokenizer Info ===")
    print("BOS:", tokenizer.bos_token_id)
    print("EOS:", tokenizer.eos_token_id)
    print("PAD:", tokenizer.pad_token_id)
    
    print("\n=== Model Config ===")
    print("decoder_start_token_id:", model.config.decoder_start_token_id)
    print("pad_token_id:", model.config.pad_token_id)
    print("eos_token_id:", model.config.eos_token_id)
    
    # Try generating a sequence from random noise to see if it produces valid text
    print("\n=== Test Generation (Random Noise) ===")
    # Create a dummy PIL image to test the processor
    from PIL import Image
    import numpy as np
    dummy_img = Image.fromarray(np.random.randint(0, 256, (100, 300, 3), dtype=np.uint8))
    
    pixel_values = processor(images=[dummy_img], return_tensors="pt").pixel_values
    
    out_default = model.generate(pixel_values, max_length=15, output_scores=True, return_dict_in_generate=True)
    generated_ids = out_default.sequences
    print("\nRaw Token IDs:", generated_ids.tolist()[0])
    print("Decoded Text:", tokenizer.batch_decode(generated_ids, skip_special_tokens=True))
    
    if out_default.scores:
        line_logits = [step_scores[0] for step_scores in out_default.scores]
        line_log_probs = [torch.nn.functional.log_softmax(logits, dim=-1).max().item() for logits in line_logits]
        avg_log_prob = sum(line_log_probs) / len(line_log_probs)
        confidence = math.exp(avg_log_prob)
        print("Average Log-Prob:", avg_log_prob)
        print("Calculated Probability (Confidence):", confidence)
