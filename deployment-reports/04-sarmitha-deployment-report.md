# Deployment Report — Image Enhancement, OCR, and Translation

**Project:** BioLearnX / R26-SE-041  
**Member:** Sarmitha S  
**Student ID:** IT22637482  
**Component directory:** `sarmitha-image-text-extractor-study-gen/`  
**Prepared:** 14 October 2026

## 1. Purpose and deployment status

The component enhances handwritten document images, extracts Sinhala text, translates extracted content into Tamil and English, and collects corrected OCR crops for later training.

The repository contains a FastAPI CPU API, an Expo/React Native interface, Modal model definitions, and OCR cleanup tests. No component-specific Dockerfile, production hosting manifest, or root release workflow was found. The hosting procedure below is proposed from the supplied code; it does not certify an existing public deployment.

The interface imports `@/lib/api`, but `frontend-rn/lib/api` is absent from this checkout. Its API implementation and production URL configuration must be restored or implemented before frontend release. An `EXPO_PUBLIC_API_URL` mechanism cannot be assumed from the current source.

## 2. Deployment architecture and active pipeline

| Layer | Implementation | Proposed hosting arrangement |
| --- | --- | --- |
| Interface | Expo / React Native, web-capable | Independent static web deployment after validated export |
| CPU API | FastAPI, `main:app` | Persistent Python service behind HTTPS |
| Enhancement | Fine-tuned Swin2SR | Modal T4 endpoint in `srcnn_app.py` |
| Sinhala OCR | Fine-tuned TrOCR | Modal T4 text/line endpoints in `trocr_app.py` |
| Translation | NLLB-200 distilled 600M | Modal T4 endpoint in `translate_app.py` |
| Feedback dataset | Crop images and JSONL metadata | Persistent writable backend `dataset/` directory |

The source filename `srcnn_app.py` is historical: the current model implementation is Swin2SR. In the current `/api/process` route, enhancement is generated for comparison/download, while OCR receives the original image bytes to preserve handwriting characteristics. OCR output is cleaned and translated sequentially. SinhaLM/Qwen visual correction is skipped in this active route and the response sets `context_improved` to false. Additional agent files are optional deployments, not prerequisites for the current main processing path.

## 3. Prerequisites and configuration

Use an isolated Python environment and `backend/requirements.txt`. GPU dependencies are installed in Modal images rather than the CPU backend. Validate a clean frontend install against the checked-in package/lock files and Expo runtime before selecting a build image.

| Variable | Purpose |
| --- | --- |
| `SRCNN_MODAL_URL` | Swin2SR enhancement endpoint despite its historical variable name |
| `TROCR_MODAL_URL` | Text-only OCR endpoint when that client path is used |
| `TROCR_LINES_MODAL_URL` | Required line-extraction endpoint for `/api/process` |
| `TRANSLATE_MODAL_URL` | Tamil/English translation endpoint |
| `ALLOWED_ORIGINS` | Comma-separated frontend origins; default `http://localhost:3000` |
| `MAX_UPLOAD_BYTES` | Upload limit; default 10 MiB |
| `QWEN_MODAL_URL`, `SINHALM_MODAL_URL`, `VISUAL_OCR_MODAL_URL` | Optional agent configuration; not invoked by the current main pipeline |

The model definitions reference `sarmisarmitha/swin2sr-sinhala-image-enhancement`, `sarmisarmitha/trocr-sinhala-handwritten-ocr`, and `facebook/nllb-200-distilled-600M`. Confirm access to all referenced artifacts, including the TrOCR subfolder defined in source, before building the Modal images.

## 4. Deployment procedure

1. Record the release commit. Restore the frontend API module with upload/request handling, response types, and explicit configurable HTTPS backend origin. Match `/api/process` and error responses; do not hardcode a learner-device localhost address into the production client.
2. Authenticate Modal and deploy the active model services from `backend/`:

   ```bash
   modal deploy modal_functions/srcnn_app.py
   modal deploy modal_functions/trocr_app.py
   modal deploy modal_functions/translate_app.py
   ```

   Record the printed function URLs separately. Configure both TrOCR text and line URLs where required; `/api/process` specifically uses `TROCR_LINES_MODAL_URL`. Enhancement and TrOCR have 300-second scaledown windows in source. Cold-start acceptance must be measured separately from warm inference.
3. Prepare the CPU API environment from `backend/`:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install -r requirements.txt
   ```

   Populate `.env` from `.env.example`, using the deployed URLs and exact frontend origins. Mount a writable persistent directory at `backend/dataset` if feedback retention is required. The feedback module creates the image directory during import, so directory permissions are a startup requirement.
4. Configure a process manager to run the API behind an HTTPS reverse proxy:

   ```bash
   python -m uvicorn main:app --host 127.0.0.1 --port 8000 --workers 1
   ```

   A single worker is the initial choice because feedback appends to a local JSONL file and uses timestamp-derived crop names; concurrent multi-worker dataset writing has not been established as safe. Set proxy upload limits and request timeouts to accommodate the configured image limit and measured multi-model processing duration.
5. After restoring the frontend module and its public configuration, run from `frontend-rn/`:

   ```bash
   npm ci
   npx tsc --noEmit
   npx expo export --platform web
   ```

   Host the successfully exported web directory, normally `dist/`, with HTTPS and routing compatible with the generated Expo export. No web hosting manifest is supplied in this component. Validate web deployment first; native Android/iOS distribution requires separate build/signing configuration and is not evidenced by this repository's deployment setup.

## 5. Release verification and acceptance

From the backend, run the existing cleanup checks:

```bash
python -m unittest discover -s tests -p 'test_*.py'
```

Check `/` for API liveness and submit a representative Sinhala handwritten image to `/api/process`. Confirm original/enhanced images, cleaned Sinhala output, line crops/confidence, and Tamil/English fields are present. Translation failures are caught and can leave an empty translation field while processing otherwise succeeds; check translation content explicitly.

Test enhancement-only and OCR-only routes when included in the release. Test invalid media types, uploads above the configured limit, absent endpoint configuration, model errors, and CORS from the hosted client. The process route permits JPEG, PNG, WebP, and BMP content types; it does not establish support for arbitrary document/PDF uploads.

Submit a controlled correction to `/api/feedback/ocr`, verify its crop/metadata are saved, restart the API, and confirm persistence. Use an isolated dataset for acceptance so test corrections do not contaminate real training data. Check mobile/web upload behavior through the restored API client.

There is no dedicated `/health` or dependency-readiness endpoint in the inspected `main.py`. A successful `/` response only establishes that the API answers requests. Record end-to-end latency and OCR/translation behavior separately; no runtime pass results or quality metrics were collected for this report.

## 6. Operations and rollback

Monitor enhancement/OCR/translation errors, cold starts, request duration, dataset disk usage, missing URLs, and model build/download failures. Persist feedback images and `dataset/metadata.jsonl` together. Store dataset backups privately and confirm they can be restored.

The inspected routes do not enforce application authentication. Before deployment to an intended authenticated audience, implement or configure the required access control and test it. CORS alone does not prevent direct API calls. Configure upload/request protection according to that audience rather than assuming the Expo client provides backend access control.

Retain the previous API/client build, model source/revision references, and environment configuration. Roll back application code and compatible Modal endpoints independently, retaining the feedback dataset. Recheck a representative OCR request and translation pair after rollback. Model repositories are referenced by identifiers without an explicit immutable revision in the inspected definitions; record the resolved model revisions for reproducible releases.

## 7. Evidence and pending deployment items

Pending items include the missing frontend API module, validated Expo install/export, selected public hosts/URLs, persistent feedback storage, audience-specific access control, release automation, and live inference acceptance. SinhaLM/Qwen correction should only be described as active after the route is changed and validated.

Repository references: [API entry point](../sarmitha-image-text-extractor-study-gen/backend/main.py), [active processing route](../sarmitha-image-text-extractor-study-gen/backend/app/api/routes.py), [settings](../sarmitha-image-text-extractor-study-gen/backend/app/core/config.py), [feedback persistence](../sarmitha-image-text-extractor-study-gen/backend/app/api/feedback.py), [enhancement service](../sarmitha-image-text-extractor-study-gen/backend/modal_functions/srcnn_app.py), [OCR service](../sarmitha-image-text-extractor-study-gen/backend/modal_functions/trocr_app.py), [translation service](../sarmitha-image-text-extractor-study-gen/backend/modal_functions/translate_app.py), and [frontend](../sarmitha-image-text-extractor-study-gen/frontend-rn/app/index.tsx).
