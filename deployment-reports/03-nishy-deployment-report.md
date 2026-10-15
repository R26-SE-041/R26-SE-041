# Deployment Report — Adaptive Quiz and Recommendation

**Project:** BioLearnX / R26-SE-041  
**Member:** Nishara T  
**Student ID:** IT22223876  
**Component directory:** `nishy-adaptive-quiz-recommender/`  
**Prepared:** 14 October 2026

## 1. Purpose and deployment status

The adaptive assessment component ingests learning material, generates grounded questions, evaluates answers, adjusts difficulty, and provides analytics and topic recommendations through a LangGraph workflow.

The repository supplies a FastAPI backend, Next.js frontend, a fine-tuned Qwen Modal endpoint, and backend tests. Its README documents a deployed Modal generation URL, but live availability was not checked. No component-specific production Dockerfile, hosting manifest, or root CI/CD workflow was found. The frontend and CPU hosting arrangement below is a proposed deployment procedure based on the supplied source.

The frontend imports `@/lib/api` from quiz/upload/result pages, but `frontend/lib/api` is absent from this checkout. Restore or implement that module and validate its contracts before claiming that the frontend can be built and released.

## 2. Deployment architecture

| Layer | Source implementation | Proposed deployment arrangement |
| --- | --- | --- |
| Interface | Next.js 15.3.3 / React 19 | Independently hosted Next.js production build |
| API | FastAPI, `app.main:app` | One persistent CPU service behind HTTPS |
| Assessment state | SQLite session database | Writable persistent disk |
| Workflow checkpointing | SQLite LangGraph checkpoints | Same persistent backend installation |
| Document retrieval | Local embeddings and Chroma PersistentClient | Persistent index directory; CPU model cache |
| Text generation | Qwen2.5-7B-Instruct with Nishy LoRA | Modal A10G endpoint |
| Source files | Uploaded learning documents | Persistent upload directory |

The code uses SQLite and local Chroma persistence, rather than the Supabase data architecture used by some other components. A single backend instance/process is the initial deployment choice because session work, checkpoints, and local files have not been demonstrated to support multiple independent replicas.

## 3. Prerequisites and configuration

Use an isolated Python environment and `backend/requirements.txt`. Python 3.11 matches the Modal inference image; validate the CPU requirements in a clean environment before selecting the host runtime. The frontend package metadata takes precedence over the README's older Next.js 14 description.

| Variable | Purpose |
| --- | --- |
| `MODAL_ENDPOINT_URL` | Generation endpoint; default documented in component README |
| `MODAL_API_KEY` | Optional authorization value sent by the backend client |
| `MODAL_REQUEST_TIMEOUT_SEC` | Model request timeout; source default 45 seconds |
| `MODAL_MAX_NEW_TOKENS` | Generation bound; source default 180 |
| `FRONTEND_URL` | Production origin added to backend CORS allowlist |
| `NEXT_PUBLIC_API_URL` | Public browser API URL, configured before frontend build |
| `SQLITE_DB_PATH` | Session database; default `./db/sessions.db` |
| `CHECKPOINT_DB_PATH` | Checkpoint database; default `./db/checkpoints.db` |
| `CHROMA_PERSIST_DIR` | Vector index; default `./db/chroma` |
| `UPLOAD_DIR` | Source uploads; default `./data/uploads` |
| `MAX_FILE_SIZE_MB` | Upload size bound; default 50 MB |
| `DEBUG` | Set false to avoid debug logging/reload through the script entry point |

Set persistent paths relative to a fixed backend working directory or use absolute persistent paths. The Modal endpoint requires the existing `huggingface-secret` containing `HF_TOKEN`. It caches `Qwen/Qwen2.5-7B-Instruct` and the adapter `Nishy11/nishy-qwen2.5-7b-v4` during image construction.

## 4. Deployment procedure

1. Record the release commit, restore the missing frontend API module, and review its request/response types against backend routers. Validate dependency compatibility, especially the installed LangGraph and checkpoint packages.
2. Authenticate Modal, provision its Hugging Face secret privately, and deploy from the component backend:

   ```bash
   modal deploy modal_inference/qwen_endpoint.py
   ```

   Record the returned endpoint and configure `MODAL_ENDPOINT_URL`. The model uses an A10G GPU, a 600-second function timeout, and a 600-second scaledown window in source. These are configuration values, not measured release latency.
3. Prepare the backend environment from `backend/`:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install -r requirements.txt
   ```

   Populate the private `.env` from `.env.example`. Create/persist the database parent directories, upload directory, and embedding cache. Set `FRONTEND_URL` to the exact hosted origin.
4. Configure a process manager to run the following from the backend working directory, behind an HTTPS reverse proxy:

   ```bash
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
   ```

   Use a single worker initially and no reload option. Startup compiles the graph; database service initialization creates tables and performs additive migrations. Back up existing state before introducing a version that changes its schema.
5. From `frontend/`, configure `NEXT_PUBLIC_API_URL` to the HTTPS API origin and run:

   ```bash
   npm ci
   npx tsc --noEmit
   npm run build
   npm run start
   ```

   The final command applies to a managed Node server. An independent Next.js hosting project can run the same build without a local persistent frontend process. The missing API module must be fixed first. Rebuild after public API URL changes; the configured default is localhost.
6. Expose only the intended HTTPS application endpoints. Keep database, vector index, and document files outside public web roots. Record the selected host, process-manager configuration, and persistent-volume mapping in the release record.

## 5. Release verification and acceptance

Install the backend test runner separately if it is not present; it is not listed in the runtime requirements. From the backend environment, run `python -m pytest tests/` using isolated test state. Run frontend TypeScript and production build checks after restoring its API module.

Check `/health` and then a full document-to-quiz flow: upload a supported document, create a session, generate questions with source grounding, submit MCQ/open-ended answers, request a hint where supported, advance, and view results/recommendations. Restart the service and verify persistence of sessions, source documents, vector index, and graph checkpoints.

Test unavailable model responses and timeout behavior. `/health` returns a static healthy response and does not check database or Modal availability. Successful deployment requires real workflow evidence in addition to liveness.

Record actual test results, release commit, model/adapter version, persistent paths, hosted frontend/API URLs, and acceptance date. No pass/fail runtime results were collected for this report.

## 6. Operations, scaling, and rollback

Back up SQLite using a consistent database backup mechanism or while writes are stopped; do not copy only a live `.db` file while ignoring journal/WAL state. Back up session data, checkpoints, uploads, and Chroma index as a compatible set. Verify restoration in an isolated environment.

Monitor model timeouts, queue/session processing, failed questions, disk usage, SQLite contention, and retrieval errors. Local embedding weights need cache space and initial download access. Measure concurrent sessions before increasing capacity. Multiple replicas require a deliberate redesign of shared state and background work; they are not established by the current setup.

Keep the previous frontend build, backend release/environment, and model adapter reference. Restore compatible application code and model routing independently. If additive database changes make the old release incompatible, use a reviewed migration plan or restore from a consistent backup while accounting for subsequent learner data. Repeat upload, answer, and persistence checks after rollback.

## 7. Evidence and pending deployment items

Pending items are the missing frontend API module, validated dependency installation/build, production CPU/frontend hosts, durable-disk provisioning, release automation, and live acceptance evidence. Authentication and learner-data access controls must be assessed for the intended hosting audience; this report does not establish an authenticated production deployment.

Repository references: [component guide](../nishy-adaptive-quiz-recommender/README.md), [API entry point](../nishy-adaptive-quiz-recommender/backend/app/main.py), [SQLite service](../nishy-adaptive-quiz-recommender/backend/app/services/db_service.py), [retrieval persistence](../nishy-adaptive-quiz-recommender/backend/app/services/rag_service.py), [checkpoint workflow](../nishy-adaptive-quiz-recommender/backend/app/graph/graph.py), [Modal endpoint](../nishy-adaptive-quiz-recommender/backend/modal_inference/qwen_endpoint.py), and [frontend configuration](../nishy-adaptive-quiz-recommender/frontend/next.config.mjs).
