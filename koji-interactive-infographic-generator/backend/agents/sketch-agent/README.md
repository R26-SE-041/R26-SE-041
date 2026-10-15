# Draw to image

Independent Modal app using Qwen2.5-VL-7B for recognition/inspection and SDXL Base
1.0 + Xinsir Scribble for rendering. Vision and rendering use separate A10G
workers; the CPU orchestrator waits for model calls without holding a GPU.
The existing prompt-only FLUX/anatomy routes are unchanged.

Run from `backend/`:

```powershell
modal run agents/sketch-agent/modal_app.py::setup_model_weights
modal deploy agents/sketch-agent/modal_app.py
```

For this upgrade, run weight setup again **before deploying**: the existing
volume needs the new `vision/` model as well as `sdxl/` and `scribble/`. Use the
intended Modal profile/environment for both commands. Redeploy the Studio backend
and rebuild the frontend to retain anatomy and quality metadata in cloud history.

Deployment: https://agal-koji--sketch-agent-api.modal.run

Standalone frontend: set `EXPO_PUBLIC_SKETCH_AGENT_URL` to this endpoint.
Shared frontend: set `SKETCH_API_URL` in `common-frontend/.env.local` for the
local proxy, or `EXPO_PUBLIC_SKETCH_AGENT_URL` for a direct endpoint. Restart
Expo/the proxy after changing environment variables.

`POST /generate/start` accepts normalized square-canvas strokes, optional
`instruction`, `control_strength` (0.3–1.3), and optional `seed`.
`GET /generate/result/{call_id}` returns 202 while working, then the PNG,
actual prompt, `anatomy_spec`, `quality_warning`, `retry_count` and model/settings metadata.
Ambiguous drawings return `error_code: "clarification_required"` and an actionable
`error` asking the user to name the subject in Additional instruction; no rendering
GPU is used. `/generate` is available for
synchronous clients. `/health` reports service configuration, not GPU readiness.

```json
{"strokes":[{"points":[[0.2,0.5],[0.8,0.5]],"width":0.006,"tool":"pen"}],"instruction":"","control_strength":0.85}
```

The vector sketch is rasterized to 1024×1024 and recognized with the optional
instruction. Every subject gets a finished full-colour render, plain white
background, full silhouette, soft dimensional shading, and no baked-in labels.
The control drawing is fitted into centered margins while preserving its aspect
ratio and pose. Scribble control ends before final denoising to let the renderer
paint surfaces rather than trace pen lines. Anatomy additionally caps control
strength so a rough drawing does not force malformed anatomy.

Human anatomy uses the existing catalog/compiler; uncatalogued parts such as
eyes and hands use its general anatomy path. Recognition preserves the external
or sectional view and reports only visible structures. Generated structures are
not promoted to curated facts. Both SDXL text encoders receive token-sized chunks
of long prompts, so anatomy and user details are not silently truncated.

Vision checks subject match, finished material colour, background, framing,
embedded text and visible anatomy. At most one targeted retry is allowed. The
best result is selected by compliance, then score. Inspection outages preserve
the image with `quality_status: "unverified"`; unresolved defects return
`needs_review` and a notice. A passing inspection is not clinical validation and
does not establish the correctness of unseen anatomy in a reconstructed mesh.
Blank/fully erased drawings, non-finite/out-of-range coordinates, and excessive
point counts fail CPU validation before GPU allocation.

History uses the existing cloud archive when connected and browser archive otherwise.
Each sketch version stores original strokes, optional instruction, actual prompt,
generated image, seed, models and settings. Continuing history restores the editable
sketch. Regenerations remain versions of the same chat. Existing interactive analysis
and Hunyuan3D conversion consume the generated PNG; 3D job status/GLB are attached
to the source image record. Shared frontend archives remain scoped to the signed-in user.

CPU regression checks from `backend/` (no model calls):

```powershell
..\.venv\Scripts\python.exe -m pytest tests/test_sketch.py tests/test_sketch_agent.py tests/test_sketch_pipeline.py tests/test_studio.py
```

After deploying, visually inspect eye/heart/hand and fish/car drawings with no
instruction as well as explicit views. Check all adherence modes. Convert selected
passing images through Hunyuan3D and inspect GLB silhouette and texture. CPU tests
validate orchestration and policy, not generated-image fidelity or mesh anatomy.

Implementation references: [Qwen2.5-VL inference](https://huggingface.co/docs/transformers/v4.49.0/en/model_doc/qwen2_5_vl),
[Diffusers ControlNet settings](https://huggingface.co/docs/diffusers/v0.32.2/en/api/pipelines/controlnet_sdxl).

Xinsir weights use Apache-2.0; SDXL Base uses CreativeML Open RAIL++-M.
