# Draw to image

Independent Modal app using SDXL Base 1.0 and Xinsir Scribble ControlNet on A10G.
The FLUX image agent and existing prompt/anatomy routes are unchanged.

Run from `backend/`:

```powershell
modal run agents/sketch-agent/modal_app.py::setup_model_weights
modal deploy agents/sketch-agent/modal_app.py
```

Deployment: https://agal-koji--sketch-agent-api.modal.run

Standalone frontend: set `EXPO_PUBLIC_SKETCH_AGENT_URL` to this endpoint.
Shared frontend: set `SKETCH_API_URL` in `common-frontend/.env.local` for the
local proxy, or `EXPO_PUBLIC_SKETCH_AGENT_URL` for a direct endpoint. Restart
Expo/the proxy after changing environment variables.

`POST /generate/start` accepts normalized square-canvas strokes, optional
`instruction`, `control_strength` (0.3–1.3), and optional `seed`.
`GET /generate/result/{call_id}` returns 202 while working, then the PNG,
actual prompt and model/settings metadata. `/generate` is available for
synchronous clients. `/health` reports service configuration, not GPU readiness.

```json
{"strokes":[{"points":[[0.2,0.5],[0.8,0.5]],"width":0.006,"tool":"pen"}],"instruction":"","control_strength":0.85}
```

The vector sketch is rasterized to 1024×1024. White-on-black control lines guide
generation directly; no sketch-caption model is used. Empty instructions use
the default illustration prompt. Blank/fully erased drawings, non-finite/out-of-
range coordinates, and excessive point counts fail CPU validation before GPU allocation.

History uses the existing browser IndexedDB archive (50 versions, no cloud sync).
Each sketch version stores original strokes, optional instruction, actual prompt,
generated image, seed, models and settings. Continuing history restores the editable
sketch. Regenerations remain versions of the same chat. Existing interactive analysis
and Hunyuan3D conversion consume the generated PNG; 3D job status/GLB are attached
to the source image record. Shared frontend archives remain scoped to the signed-in user.

Xinsir weights use Apache-2.0; SDXL Base uses CreativeML Open RAIL++-M.
