# 3D conversion: timeout and performance fix

The reported error, `Model generation timed out. Retry from history.`, came from
the durable worker's polling deadline. It stopped retrieving results after
55 minutes even though the GPU function was allowed to execute for 60 minutes,
in addition to startup. This error does not establish that the GPU crashed.

The supplied logs show shape generation finishing in about 24 seconds, followed
by a long texture stage. The exact slow texture operation was not logged. The
old code passed the full generated mesh directly to paint and relied on Modal's
default CPU and RAM requests for CPU-heavy mesh/UV work.

## Changes

- Reduce dense meshes to at most 40,000 faces before texture generation, following
  [Hunyuan's application](https://github.com/Tencent-Hunyuan/Hunyuan3D-2/blob/f8db63096c8282cb27354314d896feba5ba6ff8a/gradio_app.py#L260).
  Reject meshes that cannot reach this budget rather than starting costly UV work.
- Set rendering and texture baking to 1024 px instead of the upstream 2048 px
  defaults. This trades fine texture detail for less pixel processing and a smaller
  output suitable for the web viewer. Shape generation remains at 30 steps and
  explicitly uses a 256 octree resolution.
- Reserve four CPU cores and 16 GiB of host RAM per GPU container. These
  reservations can increase resource billing; they support the CPU mesh work
  that a larger GPU alone does not accelerate.
- Pin the Hunyuan package and both native extensions to the same commit, and
  explicitly select the Turbo paint variant that upstream currently defaults to.
- Reuse a U2Net CPU session for background removal and preserve existing image
  transparency. Put Hugging Face and rembg caches on the model volume.
- Publish preparation, shape, simplification, texture and export stages, with
  stage timings and visible texture diffusion progress in container logs.
- Wait up to 70 minutes for a Modal 3D result, covering the 60-minute GPU limit
  and startup. The cloud browser waits up to 75 minutes. This is a safety margin,
  not an expected generation duration or a measured speed improvement.
- Retrieve an already completed result when a restarted durable worker resumes
  after its polling deadline. Retry transient result-poll connection failures.
- Report inference failures as failures and allow a failed request ID to start
  a fresh call, while retaining reuse of queued/running/successful calls.
- Validate images before spawning GPU work and reject empty meshes/invalid GLB
  headers. Texture failure never silently returns an untextured model.

## Validation and rollout

Local validation completed: backend CI (125 passed, 15 database tests skipped),
29 frontend unit tests, TypeScript check, production web export, and import/OpenAPI
validation using the real Modal SDK. GPU operations in the regression tests are
mocked. No live A100 generation or deployment was performed for this fix.

All three layers need deployment: the `threed-agent` Modal app, the CPU Studio
worker/API, and the frontend. Use the existing scoped CI/CD workflow to deploy
the tested changes. For a manual Modal-only deployment, run from `backend/`:

```powershell
..\.venv\Scripts\python.exe -m modal deploy agents/threed-agent/modal_app.py
```

Deploying only the frontend will not change the GPU processing or the durable
worker deadline. Other GPU agents do not need redeployment for these changes.

After deployment, submit one conversion and verify that:

1. The dense mesh is reduced before texture generation; the logs report both
   original and final face counts.
2. Stage transitions and per-stage timings appear. Texture diffusion progress
   bars are visible instead of a long unexplained silence.
3. The result is a textured GLB that opens in the viewer and downloads correctly.
4. Record cold-start and warm-run durations before promising a completion time.

If a stage still stalls, capture its last progress line and current CPU/GPU
metrics. The original low-utilization daily graph is not enough to identify a
specific stalled operation.
