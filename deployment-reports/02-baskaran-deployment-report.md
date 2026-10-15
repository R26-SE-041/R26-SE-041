# Deployment Report — Multilingual Audio Communication

**Project:** BioLearnX / R26-SE-041  
**Member:** Baskaran V  
**Student ID:** IT22172600  
**Component directory:** `baskaran-interactive-audio-communication/`  
**Prepared:** 14 October 2026

## 1. Purpose and deployment status

VoiceLearn supports voice questions about lecture documents, retrieval-grounded answers, multilingual speech processing, language-specific audio playback, and document-to-audio revision.

The repository contains a Next.js frontend, FastAPI backend, Dockerfiles, Docker Compose configuration, Modal endpoint definitions, Supabase integration, and tests. The Koji AWS guide identifies `voicelearn-audio` as an independent Vercel project; it does not establish this component's current backend host or live health. The root `.github/workflows/` contains a Koji workflow, not an audio release pipeline. Automated audio production deployment is therefore not evidenced by the inspected root workflows.

## 2. Deployment architecture

| Layer | Implementation | Hosting arrangement |
| --- | --- | --- |
| Browser interface | Next.js 14 / React 18 | Separate Vercel project documented; standalone Docker runner also supplied |
| API | FastAPI, `app.main:app` | CPU container or persistent Python service; production host to confirm |
| Retrieval index | ChromaDB, BGE embeddings/reranking | Compose ChromaDB service or configured local persistent store |
| User identity and files | Supabase Auth, database, private Storage | Credentials supplied through backend/frontend environments |
| Speech and generation | Independent Modal services | Language-specific ASR/TTS and answer-generation endpoints |
| Local state | Documents, history, optional actions | Persistent writable storage on backend host |

Current configuration and routing include Gemma base/fine-tuned answer endpoints and language-specific speech services. The older README model table is insufficient to identify all active production models. Endpoint selection must follow `app/core/config.py` and `app/services/modal_client.py` for the chosen release.

## 3. Prerequisites and configuration

The backend Dockerfile uses Python 3.11, installs ffmpeg and build tools, and caches BGE models during image construction. Its runtime enables offline Hugging Face access, so model-cache build success is essential. The frontend Dockerfile uses a Node 20 runner and expects an already-created `.next/standalone` output.

| Configuration | Purpose |
| --- | --- |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY` | Supabase connection and public identity configuration |
| `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET` | Backend-only privileged access and token validation |
| `ALLOWED_ORIGINS` | JSON list of permitted frontend origins |
| `NEXT_PUBLIC_API_URL` | Browser-reachable HTTPS API URL, configured before frontend build |
| `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Public frontend identity configuration |
| `CHROMA_HOST`, `CHROMA_PORT`, `CHROMA_COLLECTION` | Vector-store connection and collection |
| `MODAL_WHISPER_URL`, `MODAL_INDIC_STT_URL`, `MODAL_SINHALA_ASR_URL` | English/fallback, Tamil, and Sinhala ASR routing |
| `MODAL_TRANSCRIPT_CORRECTOR_URL` | Transcript correction service |
| `MODAL_BASE_GEMMA_URL`, `MODAL_FINETUNED_GEMMA_V2_URL` | Separate base and tuned answer-generation URLs |
| `MODAL_RAG_GENERATOR_URL`, `MODAL_LOCALIZER_URL` | Other configured generation/localization paths |
| `MODAL_ENGLISH_KOKORO_TTS_URL` | English audio generation |
| `MODAL_INDIC_PARLER_MIXED_TTS_URL` | Current Tamil TTS route |
| `MODAL_SINHALA_VITS_TTS_URL` | Sinhala audio generation |
| `USE_ENGLISH_TTS`, `USE_TAMIL_TTS` | Feature switches; defaults are false |
| `USE_DIRECT_MULTILINGUAL_GEMMA` | Current direct multilingual generation switch |
| `LOCAL_DOCUMENT_STORE_PATH`, `LOCAL_HISTORY_STORE_PATH` | Persistent local document/history directories |
| `DEBUG` | Set false for production; interactive API docs are disabled |

Optional retrieval endpoints use `USE_MODAL_RETRIEVAL_MODELS`, `MODAL_BGE_EMBED_URL`, and `MODAL_BGE_RERANK_URL`. Optional document actions use `ACTIONS_ENABLED`, the selected provider, and persistent `ACTIONS_STORE_PATH`. Configure the OpenClaw path only when that provider is intentionally selected.

## 4. Deployment procedure

1. Select and record the release commit. Configure private backend `.env` and frontend `.env.local` using the supplied examples.
2. Verify Supabase tables, row-level policies, and private `documents`/`audio` buckets. Startup attempts migration through an `exec_sql` RPC, but migration failures are non-fatal. A healthy API therefore does not prove schema/bucket provisioning succeeded. Review schema explicitly before acceptance.
3. Authenticate Modal and deploy the endpoint files used by the configured release. From the component root, examples are:

   ```bash
   modal deploy backend/modal_endpoints/whisper_stt.py
   modal deploy backend/modal_endpoints/tamil_asr_qwen3.py
   modal deploy backend/modal_endpoints/sinhala_whisper_asr.py
   modal deploy backend/modal_endpoints/gemma_answer_generator.py
   modal deploy backend/modal_endpoints/english_kokoro_tts.py
   modal deploy backend/modal_endpoints/indic_parler_mixed_tts.py
   modal deploy backend/modal_endpoints/sinhala_vits_tts.py
   ```

   Configure the printed URLs, including `/generate` URLs for Gemma classes. The Gemma deployment mounts `voicelearn-models` and expects base weights under `/models/gemma/base` and the V2 adapter under `/models/gemma/adapters/v2`, unless its base-path override is used. Provision these artifacts before inference; creating an empty volume does not install weights. Deploy other correction/localization endpoints only when the configured workflow requires them.

4. Build the frontend before using its Docker runner. From `frontend/`:

   ```bash
   npm ci
   npm run type-check
   npm run build
   ```

5. For the supplied local Compose arrangement, run `docker compose up --build -d` from the component root. It exposes frontend port 3000, API port 8000, and ChromaDB port 8001. Validate the configured health checks in the built images: both use `curl`, while the backend Dockerfile does not explicitly install it.
6. For production, prepare a reviewed Compose override or host configuration. Replace the Compose frontend's `http://localhost:8000` URL with the public API URL in the actual build, remove the development source bind mount, configure HTTPS, keep ChromaDB private, and persist writable state. Those adjustments are deployment work still required, not changes supplied by this report. Alternatively publish the Next.js build through its separate Vercel project while deploying the API/index independently.

Browser `localhost` refers to the learner's device. Setting a public frontend variable only at container runtime does not reliably replace values already embedded during `next build`.

## 5. Release verification and acceptance

From the backend environment, install the test dependencies required by the checked-out tests and run:

```bash
pytest tests/ -v
```

Check API `/health`, browser authentication, document upload/indexing, source-grounded retrieval, and an English/Tamil/Sinhala voice request. Test each enabled TTS route and the text fallback when a voice service is unavailable. Test revision playback/download and section navigation if enabled. Confirm history persists after API restart and one user's documents are inaccessible to another.

Check cold model startup separately from a warm request. The `/health` response only reports API liveness/version; it does not validate all Modal services, the BGE cache, Supabase schema, or retrieval index. Record endpoint identifiers, flags, image/build version, and actual acceptance results.

## 6. Operations and rollback

Persist the Chroma volume, local documents/history, optional local actions, and the model cache appropriate to the deployment. The supplied Compose file mounts documents/history but does not mount `local_actions`; add persistence when actions are enabled. Ensure the non-root runtime user can write to mounted directories. Back up source documents together with their corresponding index/metadata.

Monitor ingestion time, ASR/generation/TTS latency, missing model files, failed migrations, retrieval errors, disk usage, and private storage availability. Do not infer production capacity from model sizes or health checks; benchmark the chosen workload.

Keep previous backend images, frontend artifacts, Modal code/model versions, and environment configuration. Roll back to a compatible previous application release while retaining document/history volumes. Revert model routes separately where necessary and repeat the language-specific acceptance checks. Confirm schema compatibility before reverting code after a schema change.

## 7. Evidence and pending deployment items

Pending confirmation includes the CPU backend host, actual public API URL, release automation, model-volume contents, enabled language routes, persistent-directory permissions, and live acceptance results. The frontend build prerequisite, `curl` health-check dependency, localhost production URL, and development mount must be resolved before treating the supplied Compose setup as a production release.

Repository references: [component guide](../baskaran-interactive-audio-communication/README.md), [Compose configuration](../baskaran-interactive-audio-communication/docker-compose.yml), [frontend Dockerfile](../baskaran-interactive-audio-communication/frontend/Dockerfile), [backend Dockerfile](../baskaran-interactive-audio-communication/backend/Dockerfile), [settings](../baskaran-interactive-audio-communication/backend/app/core/config.py), [model routing](../baskaran-interactive-audio-communication/backend/app/services/modal_client.py), and [document actions](../baskaran-interactive-audio-communication/backend/ACTIONS.md).
