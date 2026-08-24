"""One-time Modal script to pre-download AI4Bharat IndicF5 weights.

Run once:
    modal run backend/modal_endpoints/download_tts_model.py
"""

import modal

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("libsndfile1", "git")
    .pip_install(
        "git+https://github.com/AI4Bharat/IndicF5.git",
        "transformers<4.50",
        "huggingface_hub>=0.24.0",
    )
)

app = modal.App("voicelearn-tts-model-download", image=image)
model_volume = modal.Volume.from_name("voicelearn-models", create_if_missing=True)

MODEL_ID = "ai4bharat/IndicF5"
CACHE_DIR = "/models"


@app.function(
    volumes={CACHE_DIR: model_volume},
    secrets=[modal.Secret.from_name("huggingface-secret")],
    timeout=1800,
    memory=8192,
)
def download_model():
    import os
    from transformers import AutoModel

    token = os.environ.get("HF_TOKEN")
    print(f"Downloading {MODEL_ID} to {CACHE_DIR} ...")
    model = AutoModel.from_pretrained(
        MODEL_ID,
        cache_dir=CACHE_DIR,
        token=token,
        trust_remote_code=True,
    )
    print(f"Model downloaded: {type(model).__name__}")
    model_volume.commit()
    print(f"All IndicF5 weights committed to volume '{model_volume.name}'. Done!")


@app.local_entrypoint()
def main():
    print("Starting IndicF5 model download on Modal...")
    download_model.remote()
    print("Download complete. Volume is ready for TTS endpoint.")
