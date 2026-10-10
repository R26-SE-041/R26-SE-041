"""Independent SDXL + Xinsir Scribble service. Deploy from backend/."""
from __future__ import annotations

import base64
import io
import secrets
import modal
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from shared.sketch import BASE_MODEL, CONTROL_MODEL, SketchRequest, generation_prompt, render_sketch
from shared.safety import assess_prompt, blocked_error

weights = modal.Volume.from_name("sketch-model-weights-vol", create_if_missing=True)
image = (modal.Image.debian_slim(python_version="3.11")
    .pip_install("torch==2.6.0", "diffusers==0.32.2", "transformers==4.48.3",
                 "accelerate==1.3.0", "safetensors>=0.4.5", "huggingface_hub>=0.26.0,<1",
                 "fastapi[standard]>=0.115.0,<1", "pydantic>=2.9.0,<3", "Pillow>=10.4.0,<12")
    .add_local_python_source("shared"))
app = modal.App("sketch-agent", image=image)

@app.function(volumes={"/model-cache": weights}, timeout=3600)
def setup_model_weights():
    from huggingface_hub import snapshot_download
    for model, directory in ((BASE_MODEL, "sdxl"), (CONTROL_MODEL, "scribble")):
        snapshot_download(model, local_dir=f"/model-cache/{directory}",
                          ignore_patterns=["*.bin", "*.onnx", "*.msgpack", "*.h5"])
    weights.commit()

@app.cls(gpu="A10G", volumes={"/model-cache": weights}, timeout=600,
         scaledown_window=120, max_containers=2)
class SketchAgent:
    @modal.enter()
    def load(self):
        import torch
        from diffusers import ControlNetModel, StableDiffusionXLControlNetPipeline, EulerAncestralDiscreteScheduler
        controlnet = ControlNetModel.from_pretrained("/model-cache/scribble", torch_dtype=torch.float16)
        self.pipe = StableDiffusionXLControlNetPipeline.from_pretrained(
            "/model-cache/sdxl", controlnet=controlnet, torch_dtype=torch.float16,
            variant="fp16", use_safetensors=True)
        self.pipe.scheduler = EulerAncestralDiscreteScheduler.from_config(self.pipe.scheduler.config)
        self.pipe.enable_model_cpu_offload()
        self.pipe.enable_vae_slicing()

    @modal.method()
    def generate(self, payload: dict):
        import torch
        req = SketchRequest.model_validate(payload)
        prompt = generation_prompt(req.instruction)
        safety = assess_prompt(prompt)
        if not safety.allowed:
            raise ValueError(blocked_error(safety))
        seed = req.seed if req.seed is not None else secrets.randbelow(2_147_483_648)
        result = self.pipe(prompt=prompt, image=render_sketch(req.strokes, control=True),
            negative_prompt="text, watermark, blurry, low quality, distorted",
            width=1024, height=1024, num_inference_steps=30, guidance_scale=7.5,
            controlnet_conditioning_scale=req.control_strength,
            generator=torch.Generator(device="cuda").manual_seed(seed))
        output = io.BytesIO()
        result.images[0].save(output, format="PNG")
        return {"image_base64": base64.b64encode(output.getvalue()).decode(),
                "prompt": prompt, "generation_metadata": {
                    "base_model": BASE_MODEL, "control_model": CONTROL_MODEL,
                    "seed": seed, "control_strength": req.control_strength,
                    "steps": 30, "guidance_scale": 7.5, "width": 1024, "height": 1024},
                "error": None}

web_app = FastAPI(title="Sketch Generation Agent", version="1.0.0")
web_app.add_middleware(CORSMiddleware, allow_origins=["*"],
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type", "Authorization"])

@web_app.get("/health")
def health():
    return {"status": "ok", "model": BASE_MODEL, "control_model": CONTROL_MODEL}

@web_app.post("/generate")
def generate(req: SketchRequest):
    prompt = generation_prompt(req.instruction)
    safety = assess_prompt(prompt)
    if not safety.allowed:
        raise HTTPException(422, detail={"error": blocked_error(safety)})
    try:
        render_sketch(req.strokes)  # reject erased/blank drawings before allocating a GPU
    except ValueError as exc:
        raise HTTPException(422, detail={"error": str(exc)}) from exc
    try:
        return SketchAgent().generate.remote(req.model_dump())
    except Exception as exc:
        print(f"SketchGenerationFailed: {exc}")
        raise HTTPException(503, detail={"error": "Sketch generation unavailable. Please retry."}) from exc

@web_app.post("/generate/start")
def start(req: SketchRequest):
    safety = assess_prompt(generation_prompt(req.instruction))
    if not safety.allowed:
        raise HTTPException(422, detail={"error": blocked_error(safety)})
    try:
        render_sketch(req.strokes)
    except ValueError as exc:
        raise HTTPException(422, detail={"error": str(exc)}) from exc
    call = SketchAgent().generate.spawn(req.model_dump())
    return {"call_id": call.object_id}

@web_app.get("/generate/result/{call_id}")
def result(call_id: str):
    if not call_id.startswith("fc-") or len(call_id) > 100:
        raise HTTPException(422, detail={"error": "Invalid sketch job ID"})
    try:
        return modal.FunctionCall.from_id(call_id).get(timeout=0)
    except TimeoutError:
        return JSONResponse({"status": "generating"}, status_code=202)
    except Exception as exc:
        print(f"SketchJobFailed: {exc}")
        raise HTTPException(503, detail={"error": "Sketch generation failed. Please retry."}) from exc

@app.function(timeout=600)
@modal.asgi_app()
def api():
    return web_app
