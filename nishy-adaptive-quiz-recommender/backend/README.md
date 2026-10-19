# Adaptive Assessment Platform Backend

FastAPI backend for the adaptive assessment platform.

## Setup
1. Create a virtual environment: `python -m venv venv`
2. Activate it: `venv\Scripts\activate` (Windows)
3. Install dependencies: `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and fill in the values
5. Run the server: `uvicorn app.main:app --reload`

## Quiz latency and the viva demo

Keep the existing A10G for now. Measure a warm request before considering a GPU
upgrade. Local changes reuse session source chunks and a bounded cache of MiniLM
embeddings. Grounding embeds cache misses in a batch; its thresholds and question
quality checks are preserved. Adaptive questions still use the previous answer's
actual difficulty decision. Existing background continuation prepares the next
question while the learner reads feedback.

Restart the backend to apply the local changes. New optional environment settings
are documented in `.env.example`; existing `.env` files do not need new values.
Startup now loads and warms the local MiniLM model before accepting requests, so
wait for Uvicorn's `Application startup complete` message before opening the demo.
That moves model initialization out of the first quiz, rather than eliminating
its cost. The first installation still needs to download the model. Set
`PRELOAD_EMBEDDINGS=false` only if you deliberately want lazy loading again.
Do not increase `QUIZ_GENERATION_BUDGET_SEC` just to hide a slow model.

The Modal changes require a separate deployment from this backend directory:

```powershell
.\venv\Scripts\python.exe -m modal deploy modal_inference/qwen_endpoint.py
```

This configuration retains A10G, allows at most one GPU container, scales to zero,
and reduces the GPU idle window from 600 to 120 seconds. That reduces the configured
idle tail by 80%, not total inference costs. It also makes cold starts more likely
after a pause. `MODAL_GPU_IDLE_SECONDS` can be set in the deployment shell to change
this tradeoff; keep the demo window short instead of paying for an always-on GPU.
`MODAL_MAX_GENERATION_SECONDS` defaults to 20. Transformers checks that limit during
generation; it is not a hard limit on cold starts, queueing, or request duration.
Complete top-level JSON stops generation early, and requests are capped at 8192
output tokens. These are resource controls, not a monetary spending cap.

Immediately before presenting, explicitly warm the **deployed** GPU once:

```powershell
.\venv\Scripts\python.exe -m scripts.warm_modal
```

This makes one request with a 64-token output limit and a 120-second wait budget.
It consumes Modal credits; it does not run a periodic keep-alive. Start the actual
demo promptly afterwards. `/health` checks the web API only and does not load the
GPU. `modal run modal_inference/qwen_endpoint.py` uses a separate ephemeral app and
is not the deployed endpoint warm-up procedure.

For a local-only embedding benchmark (no Modal calls or model downloads):

```powershell
.\venv\Scripts\python.exe -m scripts.benchmark_embeddings
```

Backend logs now include `[Timing] ingestion_agent`, `[Timing] knowledge_agent`,
and `[Timing] quiz_generate`; the LLM service separately records inference duration.
Compare a newly started backend, a warm model request, and subsequent questions.
API health is cached for 30 seconds; an inference/network failure overrides it for
a 30-second cooldown so subsequent questions can use existing validated recovery.
The first failed request can still take its generation budget. Recovery depends on
the available material and requested difficulty; it is not guaranteed to succeed.
Embedding timings are not end-to-end quiz timings, and similarity-based grounding
is not proof of factual correctness.

References: [Modal cold starts and idle billing](https://modal.com/docs/guide/cold-start),
[Modal scaling controls](https://modal.com/docs/guide/scale), and
[Transformers generation limits](https://huggingface.co/docs/transformers/main/main_classes/text_generation).

Local verification on this Windows workspace: the offline MiniLM benchmark took
36.446 seconds to load the model, 0.263765 seconds for an uncached four-text batch,
and 0.000012 seconds per cached batch averaged over 100 runs. Cached vectors were
identical. These measurements made zero Modal requests and do not establish live
GPU latency or total quiz speed.

Validation:

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests
```
