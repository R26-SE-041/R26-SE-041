# BIOLEARNX

A Multimodal, Multi-Agent Framework for Personalized Biology Learning

Deployment Report

Group No: R26-SE-041

| Student ID | Student Name | Component |
| --- | --- | --- |
| IT22264220 | Kojithan P. Y | Interactive visualizations |
| IT22172600 | Baskaran V | Multilingual audio communication |
| IT22223876 | Nishara T | Adaptive assessment |
| IT22637482 | Sarmitha S | Image enhancement, OCR and translation |

## 1. DEPLOYMENT OVERVIEW

### 1.1 Overview

BioLearnX provides four complementary biology learning experiences: interactive visualizations, multilingual audio communication, adaptive assessment, and handwritten-image processing. Each component has its own application services and model endpoints. This separation allows a component to be updated without redeploying the entire platform, while retaining a common project structure and learner interface.

The deployment architecture separates browser interfaces, CPU application processing, model inference, and persistent data. All four components use Modal.com and Supabase. FastAPI applications coordinate requests and learning workflows, Modal.com hosts the model services, and Supabase provides managed identity and data services. Component-specific local databases, retrieval indexes and feedback files remain additional application resources where required.

Koji's interactive visualization and Baskaran's multilingual audio components host their backends on AWS EC2 and their frontends on Vercel. Both call Modal.com model services and use Supabase. Nishara's adaptive assessment and Sarmitha's image-processing components also use Modal.com and Supabase; they retain their own application and interface configuration.

The common frontend connects the four learning areas while preserving their separate workflows and storage. Specialist interfaces have separate builds and release requirements. Shared frontend authentication and backend authorization are configured separately: a successful frontend login does not grant access to a backend that has not been configured to accept that identity issuer.

### 1.2 Purpose of the Deployment

The deployment supports the evaluation of BioLearnX as an integrated learning platform. It establishes how interfaces, application services, model inference and persistent data operate together, including long-running requests, uploaded learning material, saved results and service recovery.

The principal objectives are to make the four learning workflows accessible through their intended interfaces, maintain consistent endpoint and identity configuration, retain learner data after service restarts, and provide repeatable release and rollback procedures. Functional evaluation covers both successful requests and controlled failures, including unavailable model endpoints, rejected uploads and incomplete intermediate results.

Deployment acceptance also requires correct data boundaries. Visualization and audio content must remain associated with the appropriate account. Quiz session identity and document access need server-side enforcement for an authenticated deployment. OCR feedback storage requires controlled access and durable retention.

### 1.3 Scope of the Deployment

The deployment covers the application services, frontend builds, model endpoints, persistent stores and operational configuration of all four research components. Environment preparation, schema initialization, model provisioning, HTTPS access, component testing, monitoring and recovery are included.

The initial client target is web. Android and iOS distribution require additional build, signing and device validation. The research website is a separate publication service and does not form part of the runtime learning workflow.

| Component | Application services | Persistent data |
| --- | --- | --- |
| Interactive visualizations | Studio API, durable worker and Modal agents | Supabase jobs, conversations, document index and private assets |
| Multilingual audio | FastAPI, retrieval index and speech/language endpoints | Supabase files, Chroma index, local documents and history |
| Adaptive assessment | FastAPI, LangGraph and Modal Qwen generation | Supabase integration; SQLite session/checkpoint files, Chroma index and uploads where used |
| Image-to-text processing | FastAPI and Modal Swin2SR, TrOCR and translation | Supabase integration; corrected crop images and JSONL dataset files where used |

### 1.4 Key Metrics Monitored

Operational monitoring covers service availability, request duration, model failures and persistence. Cold-start and warm-request observations are recorded separately because model initialization can dominate the first request without indicating an application fault.

| Metric | Measurement and purpose |
| --- | --- |
| Service availability | API liveness, database/index connectivity and required process status |
| Workflow completion | Completed and failed generation, audio, assessment and OCR requests |
| Processing latency | Queue waiting time, model duration and total learner request duration |
| Retrieval integrity | Relevant source passages, selected-document filtering and account isolation |
| Output completeness | Generated assets, supported audio, assessment feedback and translation fields |
| Resource consumption | CPU, memory, cache space, database/storage usage and dataset growth |
| Recovery behavior | Retained state, resumed work and compatible application rollback |

### 1.5 Deployment Success Metrics

Deployment success depends on correct initialization and complete learning workflows. A responsive API is one acceptance condition; database, storage and model integration require additional checks.

| Indicator | Acceptance criterion |
| --- | --- |
| Service initialization | Required processes start with the intended environment and dependencies |
| Configuration consistency | Client API origins, allowed frontend origins and model URLs match |
| Functional completion | Mandatory scenarios for each component produce the required outputs |
| Persistence | Learner state, uploaded sources and corrections survive controlled restarts |
| Access control | Private data is inaccessible to an unrelated account or unauthorized request |
| Recovery readiness | A compatible previous release and consistent backup can be restored |

Deployment success rate is calculated as successfully verified required services divided by the total number of required services, multiplied by 100. Workflow error rate is calculated from failed requests divided by observed requests within a defined test interval. Expected input-validation rejections are recorded separately from application and infrastructure failures.

### 1.6 Success Rate and Error Monitoring

Release records include the commit, frontend build, backend environment, model revision, test period and request count. Errors are grouped by startup, configuration, inference, retrieval, storage and input validation. This classification identifies whether a failure originates in the application or an external dependency.

Visualization monitoring includes worker leases, queued jobs and failed model calls. Audio monitoring separates transcription, retrieval, answer generation and speech synthesis. Assessment monitoring follows ingestion, question generation, evaluation and checkpoint state. Image processing monitoring distinguishes enhancement, line extraction and translation, including partial responses with an empty translation field.

### 1.7 Key Outcomes of the Deployment

The architecture supports independent deployment of the four learning components, separate GPU inference, and component-specific persistence. Visualization includes a tested-artifact release mechanism with backend activation rollback. The remaining components use their own installation and model deployment procedures.

The visualization installation record dated 14 October 2026 includes successful EC2 readiness, production frontend proxy checks, authenticated Modal account switching and real sketch inference across three Modal accounts. Group acceptance additionally requires the audio, assessment, OCR and common-interface workflows to pass together.

## 2. DEPLOYMENT PROCESS

### 2.1 Deployment Environment Preparation

Each component uses its own dependency environment and configuration. Python application dependencies are installed in isolated environments; model dependencies remain in Modal images. Frontend dependencies are installed from the relevant package and lock files before production builds.

#### 2.1.1 Cloud Hosting Platforms

| Platform | Hosting responsibility | Component coverage |
| --- | --- | --- |
| AWS EC2 | Application backends; visualization additionally uses a durable worker and HTTPS release receiver | Koji and Baskaran |
| Modal.com | Independent inference services and model containers | All four components |
| Vercel | Published web interfaces | Koji and Baskaran |
| Supabase | Managed identity and data services with component-specific integration | All four components |

AWS EC2 hosts the Koji and Baskaran application backends. Modal.com supplies model services for all four components, while Vercel serves the Koji and Baskaran web clients. Supabase is used across all four component deployments. The durable visualization worker runs on EC2 alongside its API.

Assessment and OCR maintain separate application and interface hosting entries in the deployment inventory. Their use of Modal.com and Supabase does not assign their CPU wrappers or frontends to EC2 or Vercel.

#### 2.1.2 Application Runtime Allocation

| Component | CPU application arrangement | Interface arrangement |
| --- | --- | --- |
| Interactive visualizations | Ubuntu EC2 API and worker managed by systemd | Expo web export published to the Koji Vercel project |
| Multilingual audio | FastAPI backend on AWS EC2, with its configured retrieval services | Next.js frontend on Vercel |
| Adaptive assessment | FastAPI/LangGraph application with Modal.com and Supabase integration | Next.js interface; independent hosting configuration |
| Image-to-text processing | FastAPI application with Modal.com and Supabase integration | Expo interface; independent hosting configuration |

CPU allocation, memory and persistent disk capacity are selected using the actual workload. Audio retrieval model caches, document indexes and uploaded material require storage beyond the application source. GPU model requirements are defined by each Modal endpoint rather than by the CPU API host.

On a shared development host, API ports must be distinct because several component guides use port 8000. Production deployments use separate service origins or deliberate reverse-proxy routes. Browser configuration must point to a reachable API origin; localhost in a production browser refers to the learner's device.

The common frontend targets the configured visual, quiz, notes and audio services. Its authentication project must be accepted by the corresponding authenticated backends. Component data projects remain separate from the common identity configuration. The common frontend uses a Node relay for its configured service connections; hosting must provide that relay as well as the exported web assets.

#### 2.1.3 Modal.com Model Deployment

Each Modal application defines its container image, model-loading process, compute allocation and exposed inference functions. Model artifacts and required secrets are prepared in the destination workspace before a dependent API release. The returned inference URLs are stored in the backend environment, and a representative model request verifies that deployment can produce the expected output.

| Component | Modal services | Compute configuration |
| --- | --- | --- |
| Interactive visualizations | Prompt, image, sketch, interactive, evaluation and 3D agents | Per-agent GPU allocation; sketch uses A10G and other services have their own variants |
| Multilingual audio | Whisper/language ASR, Gemma answers, localization and language TTS | Gemma uses A100-80GB; English Kokoro uses CPU; other speech services use their configured GPUs |
| Adaptive assessment | Qwen generation with the Nishy LoRA adapter | A10G |
| Image-to-text processing | Swin2SR, TrOCR and NLLB translation | T4 for the active enhancement, OCR and translation services |

The standard deployment command is `modal deploy` followed by the selected endpoint file. Examples include `modal deploy modal_inference/qwen_endpoint.py` from the assessment backend and `modal deploy modal_functions/trocr_app.py` from the OCR backend. Audio endpoint files are deployed from its component root using the `backend/modal_endpoints/` path.

Visualization supports the registered Modal workspaces `kojithan-y`, `ikojikn` and `agal-koji`. Its six model agents switch together while the EC2 data API and existing memory/orchestrator service remain shared. The recorded installation left `agal-koji` active on 14 October 2026. Routine routing changes use the authenticated HTTPS controller; model provisioning and deployment remain separate operations.

### 2.2 Service and Data Initialization

#### Interactive Visualization

The Studio API and worker share the existing Supabase configuration. PostgreSQL connection settings, identity keys, private storage and model URLs must refer to the intended project and services. Required migrations are applied before releasing dependent application code.

From the visualization backend, `python -m studio.migrate` initializes the component schema. PDF retrieval requires the document/library migrations, pgvector support and an interactive agent that accepts the relevant PDF context fields. Database migration is separate from automatic EC2 activation.

#### Multilingual Audio

Supabase tables, row-level policies and private document/audio buckets must be available before document and history workflows are accepted. Startup attempts schema initialization through an `exec_sql` RPC. Because migration failures are non-fatal, schema and bucket checks are performed separately from API liveness.

ChromaDB retains document embeddings, while local document/history stores retain application material where those paths are used. The backend image caches BGE models during construction and enables offline model access at runtime. A successful model-cache build is therefore required for the selected local retrieval path.

#### Adaptive Assessment

Adaptive assessment uses Supabase together with its Modal.com generation service. Supabase project configuration and access policies remain part of the component deployment. The session/checkpoint files, upload directory and Chroma index used by the application require persistent writable locations. Graph compilation occurs during application startup; local database initialization creates tables and applies additive migrations. Existing state is backed up before schema-changing releases.

The initial deployment uses one backend worker to preserve the local session and checkpoint arrangement. Independent replicas require shared-state and background-work coordination before scaling.

#### Image-to-Text Processing

Image-to-text processing uses Supabase together with its Modal.com enhancement, OCR and translation services. Supabase configuration is maintained separately from model endpoint URLs and permitted interface origins. The local feedback service creates its image directory during import, so filesystem permissions must allow initialization and subsequent writes. Crop images and JSONL training metadata require persistent storage when that feedback path is enabled.

The processing route generates enhancement output for image comparison, performs line-level OCR on the original image bytes, cleans the Sinhala output, and translates it sequentially. SinhaLM and Qwen visual correction are outside the active main processing route.

### 2.3 Deployment of System Components

#### 2.3.1 Interactive Visualization

The web client calls the authenticated Studio API. Requests create durable jobs in PostgreSQL, and the worker invokes the configured Modal endpoints. Results, conversations and private assets remain available after the browser closes.

The Ubuntu installation uses `/home/ubuntu/koji/backend`, a private environment file and the services `koji-api.service` and `koji-worker.service`. The API runs `studio.main:app`; the worker runs `python -m studio.worker`.

| Configuration | Deployment function |
| --- | --- |
| `DATABASE_URL` | PostgreSQL connection with TLS |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY` | Identity configuration |
| `SUPABASE_SERVICE_ROLE_KEY` | Backend-only storage/service access |
| `CORS_ORIGINS` | Permitted interface origins |
| `EXPO_PUBLIC_STUDIO_API_URL` | Public API origin embedded in the client |
| `EXPO_PUBLIC_STUDIO_PROXY_PATH` | Production same-origin proxy prefix |
| `KOJI_DEPLOY_ENABLED`, `KOJI_EC2_DEPLOY_ENABLED` | Production and EC2 release switches |
| `KOJI_MODEL_DEPLOY_ENABLED` | Optional automatic model deployment |

GitHub Actions runs the component checks and packages the tested frontend and CPU backend. Enabled model deployment precedes dependent application changes. The HTTPS receiver verifies the release identity, commit and artifact contents before activation. When both backend and frontend change, frontend publication waits for backend deployment success. Application releases are permitted from `main` and allowed `koji-release-*` tags; the model-deployment job runs from `main` when its automatic switch or manual option is enabled.

The receiver runs on `127.0.0.1:8766`; the API runs on `127.0.0.1:8000`. Caddy routes the internal release path to the receiver and application traffic to the API. Private deployment tokens are stored in the protected release environment and server configuration.

Frontend packaging uses `npm ci`, `npm run build:web` and `python ../ci/pack_vercel.py` from the frontend directory. Public configuration changes require a rebuild. Backend environment changes require restarting both services. Previously queued jobs retain the model URLs captured at creation.

#### 2.3.2 Multilingual Audio Communication

The audio FastAPI backend runs on AWS EC2, and its Next.js frontend is hosted on Vercel. Supabase provides its configured identity and data services, while Modal.com runs the speech and language models. The API coordinates document ingestion, transcription, retrieval-grounded answers and speech synthesis, including separate Gemma base/fine-tuned answer URLs and language-specific ASR/TTS URLs.

| Configuration | Deployment function |
| --- | --- |
| Supabase URL, public key, service-role key and JWT secret | Identity, storage and backend verification |
| `NEXT_PUBLIC_API_URL` | Public browser API origin configured before build |
| `ALLOWED_ORIGINS` | JSON list of permitted frontend origins |
| `CHROMA_HOST`, `CHROMA_PORT`, `CHROMA_COLLECTION` | Retrieval index connection |
| Whisper, Tamil and Sinhala ASR URLs | Language-specific speech input |
| Gemma and localization URLs | Answer generation and language routing |
| English Kokoro, Indic Parler and Sinhala VITS URLs | Language-specific speech output |
| Local document/history/action paths | Persistent application directories |

Deploy the Modal endpoint files required by the enabled language routes. Configure the returned URLs and ensure the `voicelearn-models` volume contains the expected Gemma base weights and V2 adapter. Creating a volume alone does not install the model artifacts.

The Vercel frontend build uses the public EC2 API origin and public Supabase configuration. From the frontend directory, run `npm ci`, `npm run type-check` and `npm run build` to validate the release. The optional standalone Docker runner additionally expects `.next/standalone` and `.next/static` to exist before image construction.

On EC2, the backend and retrieval services use persistent storage and HTTPS routing, with the index restricted to the application network. The supplied Compose configuration is also available for running the API, index and an optional frontend container together. Its localhost URL and development bind mount must be adjusted when used outside development. The hosted frontend remains on Vercel, and its public variables are set during the Vercel build.

Enable English and Tamil TTS only when the corresponding feature flags and endpoints are configured. Sinhala audio uses its dedicated endpoint. Optional document actions need persistent action storage when enabled.

#### 2.3.3 Adaptive Assessment

The assessment component uses Modal.com and Supabase. Its API coordinates ingestion, source retrieval, quiz generation, answer evaluation, adaptation and recommendations. Qwen generation is hosted on Modal using `Qwen/Qwen2.5-7B-Instruct` and the adapter `Nishy11/nishy-qwen2.5-7b-v4`. The endpoint requires a Hugging Face token supplied through `huggingface-secret`.

From the assessment backend, deploy `modal_inference/qwen_endpoint.py` and configure the returned generation URL. The endpoint uses an A10G GPU, with a 600-second function timeout and scaledown window.

| Configuration | Deployment function |
| --- | --- |
| `MODAL_ENDPOINT_URL` | Generation service URL |
| `MODAL_REQUEST_TIMEOUT_SEC`, `MODAL_MAX_NEW_TOKENS` | Request and generation limits |
| `FRONTEND_URL`, `NEXT_PUBLIC_API_URL` | Backend CORS and public client API origin |
| `SQLITE_DB_PATH`, `CHECKPOINT_DB_PATH` | Persistent session and checkpoint databases |
| `CHROMA_PERSIST_DIR`, `UPLOAD_DIR` | Persistent retrieval index and source files |

Install backend dependencies in an isolated environment and configure the service working directory. Run `app.main:app` through Uvicorn with one worker and no reload option. A process manager retains the service across host restarts, and an HTTPS reverse proxy exposes the intended API.

The specialist frontend requires its imported API module before release. After restoring the module, run `npm ci`, `npx tsc --noEmit` and `npm run build`. A managed Node deployment uses `npm run start`; a Next.js hosting project can publish the corresponding build. Session persistence and backend authorization remain acceptance requirements regardless of the selected interface.

#### 2.3.4 Image Enhancement, OCR and Translation

The image-processing component uses Modal.com and Supabase. Its image API calls Swin2SR enhancement, fine-tuned Sinhala TrOCR and NLLB translation endpoints. The enhancement implementation remains in the historical filename `srcnn_app.py`.

From the OCR backend, deploy `modal_functions/srcnn_app.py`, `modal_functions/trocr_app.py` and `modal_functions/translate_app.py`. The main processing route specifically requires the line-extraction endpoint rather than only the text-only OCR URL.

| Configuration | Deployment function |
| --- | --- |
| `SRCNN_MODAL_URL` | Swin2SR enhancement endpoint |
| `TROCR_MODAL_URL`, `TROCR_LINES_MODAL_URL` | Text and line-level OCR endpoints |
| `TRANSLATE_MODAL_URL` | Tamil and English translation |
| `ALLOWED_ORIGINS` | Comma-separated frontend origins |
| `MAX_UPLOAD_BYTES` | Input limit, default 10 MiB |
| Persistent `backend/dataset/` directory | Feedback crop images and JSONL metadata |

Run `main:app` through a persistent Uvicorn service behind HTTPS. One worker is the initial arrangement for local feedback writing. Configure proxy limits and timeouts to accommodate accepted uploads and sequential model processing.

The Expo interface requires its imported API module, response types and configurable HTTPS origin. After restoring that module, run `npm ci`, `npx tsc --noEmit` and `npx expo export --platform web`. Publish the generated web output using routing compatible with the export.

### 2.4 Secure Access Configuration

Browser interfaces and public APIs use HTTPS. Permitted origins are explicit, and private database, storage, deployment and model credentials remain outside browser builds. Only public identity keys and reachable service origins are embedded in frontend assets.

Visualization validates the authenticated user and scopes jobs, sources and private assets by owner. Audio token verification must accept the configured identity project's tokens. Common frontend sign-in requires compatible backend issuer configuration rather than a change to frontend variables alone.

Assessment document/session APIs and OCR routes require additional server-side access control for authenticated use. A learner-supplied identifier is not proof of ownership, and CORS does not prevent direct requests to an API. Private stores, model administration and deployment receivers are restricted to the services and administrators that require them.

### 2.5 Execution of Testing Scenarios

#### 2.5.1 Scenario 1 - Interactive Visualizations

Sign in, submit a biology prompt and a sketch, and verify that each request creates a durable job. Inspect the generated output, automatic labels and saved conversation. Edit labels, refresh the interface and reopen the conversation to verify retention of the edited result.

Upload a representative text PDF and ask a question about a selected image region using that source. Inspect the cited page and passage, then repeat with another account to test source isolation. Restart the worker during a controlled job and inspect its recovery behavior. Include a 3D conversion when that endpoint is enabled.

Acceptance requires completed results, consistent history, private source access and the implemented recovery behavior. Queue, model and worker failures must remain visible to the learner.

#### 2.5.2 Scenario 2 - Multilingual Audio Communication

Upload lecture material and ask a question that depends on its content. Submit English, Tamil and Sinhala recordings through their configured transcription routes. Inspect the resulting text, grounded answer and language-specific speech output.

Generate revision audio and verify playback and download behavior. Where sectioned revision is enabled, test section navigation and source inspection. Disable or interrupt an endpoint in an isolated environment to verify controlled fallback and learner-visible error behavior.

Acceptance requires usable transcription, document-based responses, playable enabled audio and retained history. Restart the API and index to confirm persistence, and verify that unrelated accounts cannot access private files.

#### 2.5.3 Scenario 3 - Adaptive Assessment

Upload a supported source document, start a session and inspect the generated questions and source context. Submit correct and incorrect MCQ and open-ended answers. Request a hint, advance through the session and inspect the final analytics and recommendations.

Use different answer patterns to exercise difficulty adaptation. Restart the application during an isolated session and inspect retained session/checkpoint data. Simulate a generation timeout and verify that the session presents an understandable failure outcome.

Acceptance requires compatible question and answer contracts, recorded evaluation, coherent session progression, grounded content and persistent state. Access-control tests are performed independently of session functionality.

#### 2.5.4 Scenario 4 - Image-to-Text Processing

Submit a representative Sinhala handwritten image and inspect the original/enhanced comparison, cleaned Sinhala text, line crops and confidence values. Check both Tamil and English translation fields; a successful overall response can still contain an empty translation after a translation-service error.

Submit invalid media types and an upload above the configured limit. The processing route permits JPEG, PNG, WebP and BMP. Test an unavailable model endpoint and inspect the returned configuration or inference error.

Save a controlled crop correction through `/api/feedback/ocr`, restart the API and verify that the image and corresponding metadata remain available. Acceptance uses an isolated dataset so that test corrections do not enter the training collection.

### 2.6 Backup and Recovery Strategy

Release recovery preserves application versions, dependency environments and model endpoint configuration alongside consistent data backups. Frontend, CPU backend and GPU services can be restored independently when their request/response contracts remain compatible.

| Component | Backup and recovery requirements |
| --- | --- |
| Interactive visualizations | Preserve Supabase data/assets and a known good API/worker release; retain deployment backups and environments |
| Multilingual audio | Preserve Supabase data, source documents, history, Chroma state and optional actions; retain compatible model artifacts |
| Adaptive assessment | Preserve Supabase data and configured local session/checkpoint, upload and index resources; use consistent SQLite backups where applicable |
| Image-to-text processing | Preserve Supabase data and local feedback images/JSONL metadata where used; retain model and API versions |

Visualization activation restores the previous source and Python environment when activation or readiness fails. Application rollback does not reverse a database migration or a Modal model update. Migration compatibility is checked before restoring code, and learner data is not discarded merely to return to a previous application version.

Backup restoration is verified in an isolated environment. SQLite backups use a consistent database backup method or a stopped-write interval, rather than copying a live database file alone. Document indexes and their source/metadata sets remain aligned after restoration.

### 2.7 Deployment Details

| Item | Arrangement |
| --- | --- |
| Project | BioLearnX / R26-SE-041 |
| Interface target | Web clients and the common learning interface |
| Application services | FastAPI; a separate durable visualization worker |
| GPU inference | Independent Modal services |
| Backend hosting | AWS EC2 for Koji and Baskaran |
| Frontend hosting | Vercel for Koji and Baskaran |
| Managed data platform | Supabase for all four components |
| Additional application stores | SQLite, ChromaDB and feedback files where used |
| Visualization release | Component GitHub Actions workflow, HTTPS receiver and Vercel publication |
| Other component releases | Component build/model procedures with host-specific process and storage configuration |

Host identifiers, public URLs, commit hashes and model revisions are maintained in the deployment inventory. Private credentials are stored separately. CPU specifications and concurrent-user capacity are determined for the selected installation through resource and workload measurements.

### 2.8 Deployment Checklist

#### Pre-Deployment

- Select the release commit and verify compatible component contracts.
- Resolve frontend build dependencies and required access-control configuration.
- Verify secrets, origins, model artifacts and endpoint URLs.
- Prepare persistent stores, reviewed migrations and consistent backups.
- Identify the previous compatible release and recovery procedure.

#### During Deployment

- Initialize required schema, indexes, private storage and model artifacts.
- Deploy model services before dependent application changes.
- Start API/worker processes with the intended private environments.
- Publish frontend assets with the correct public configuration.
- Verify HTTPS routes, startup logs and dependency connectivity.

#### Post-Deployment

- Execute all four component scenarios and record outcomes.
- Verify account boundaries, persistence and restart behavior.
- Review model errors, cold starts, timeouts and partial outputs.
- Confirm backup restoration and release compatibility.
- Update the deployment inventory and outstanding-issue register.

### 2.9 Deployment Verification and Completion

A release is complete when required processes and dependencies are available, the hosted interfaces reach the intended APIs, all mandatory scenarios pass, and learner data remains protected and persistent. Component-specific blockers are resolved before group acceptance.

Verification records contain the release identifiers, environment configuration names, test outcomes and recovery checks. Unresolved failures remain in the issue register with their effect on the relevant learning workflow.

## 3. ISSUES, RESOLUTION, AND MONITORING

### 3.1 Issues Encountered During Deployment

#### Issue 1 - Missing Specialist Frontend API Modules

The assessment and OCR specialist interfaces import `@/lib/api`, but the corresponding modules are absent from the current project files. Their standalone builds depend on restoring the API implementation and response types. The common frontend provides its own transport layer; it does not replace a missing module in a specialist build.

#### Issue 2 - Audio Container Build and Health Checks

The audio frontend runner expects a completed standalone Next.js build. Compose uses curl-based checks, while the backend Dockerfile does not explicitly install curl. The production setup also needs a public browser API URL and removal of the development source mount.

#### Issue 3 - Model Artifacts and Endpoint Compatibility

Audio Gemma services require a populated model volume. Visualization PDF support requires compatible schema and agent context fields. The OCR main route requires the line-level TrOCR URL. A deployment can initialize its API while still failing requests because an artifact, URL or schema dependency is missing.

#### Issue 4 - Persistence and Access Boundaries

Assessment session/checkpoint databases and indexes require persistent disk. OCR feedback writes local images and metadata. Quiz and OCR access control must be enforced at the backend for authenticated use. Shared frontend sign-in cannot correct missing server authorization or a mismatched audio/visual identity issuer.

#### Issue 5 - Partial Output and Readiness Gaps

OCR translation failures can leave empty translated fields within an otherwise successful processing response. Audio and assessment health endpoints report liveness without verifying the full dependency chain. OCR uses its root route for liveness and has no dedicated readiness endpoint in the application entry point.

### 3.2 Resolutions and Required Actions

| Issue | Resolution | Completion check |
| --- | --- | --- |
| Specialist API modules | Restore request handling, types and configurable HTTPS origins | TypeScript checks and production builds pass |
| Audio runner/health checks | Build standalone assets; supply the health-check executable and production configuration | Containers start, checks pass and browser requests reach the public API |
| Model/schema dependencies | Provision artifacts and compatible endpoints; apply required migrations | Representative inference and retrieval requests succeed |
| Persistence/access | Mount durable stores and enforce intended backend ownership checks | Restart, restoration and unauthorized-access tests pass |
| Partial output/readiness | Check required result fields and dependency workflows beyond liveness | Missing output is detected and failures remain understandable |

These items remain release prerequisites until their completion checks are recorded. Model source identifiers and resolved revisions are retained so that a rebuilt endpoint uses the intended weights and adapter.

### 3.3 Impact Analysis

Missing frontend modules block standalone client publication. Incorrect browser URLs or absent model files prevent learning requests even when containers start. Schema mismatches can break document retrieval and generation history. Missing persistence can remove session state, uploaded sources or feedback after a restart.

Access-control gaps affect learner-data confidentiality independently of model quality. Partial translation and voice output affect the completeness of multilingual learning results. Each issue is evaluated against the component workflow it interrupts rather than treated as a single platform-wide failure.

### 3.4 Monitoring and System Observability

Monitoring combines application logs, process/container status, model-platform logs and persistent-storage usage. Requests are correlated with job or session identifiers where available. The API and model stages are inspected separately to identify initialization delays, retrieval failures and downstream inference errors.

Visualization monitoring includes queued-job age, leases and activation readiness. Audio monitoring follows cache availability, indexing, language routes and generated audio. Assessment monitoring follows database contention, session progression and model timeouts. OCR monitoring follows accepted uploads, per-stage errors and dataset growth.

Health checks remain distinct from workflow probes. A successful liveness response confirms that the application answers requests; a representative learning request verifies the external dependencies and expected output fields.

### 3.5 Monitoring Results

| Component | Operational checks | Result or required evidence |
| --- | --- | --- |
| Interactive visualizations | EC2/API proxy, account control, endpoint health and sketch inference | Installation record dated 14 October 2026 records passing checks |
| Multilingual audio | Cache/index, configured languages, answers and playback | Language-specific request, playback and restart results |
| Adaptive assessment | Grounded quiz, evaluation and checkpoint retention | Complete quiz, evaluation and session-restart results |
| Image-to-text processing | Enhancement, OCR, both translations and feedback retention | Processing output and persistent correction results |

The visualization installation record includes HTTP 200 responses from EC2 readiness and the production frontend API proxy, HTTP 401 for unauthorized control requests, successful account switching and rollback, and endpoint health checks with real sketch inference in all three registered Modal accounts. These checks establish the recorded visualization operations; they do not establish audio, assessment, OCR or all visualization-feature results.

Latency, error percentages and uptime are established from a defined observation interval. Numerical results are entered with their test workload and release identifiers so that cold starts, expected input rejections and genuine service errors remain distinguishable.

### 3.6 User Feedback

User acceptance covers whether learners can complete the four workflows, interpret output, understand failure messages and retrieve prior work. Visualization feedback includes label editing and source inspection. Audio feedback includes language selection, transcription readability and playback. Assessment feedback includes question clarity, answer evaluation and recommendations. OCR feedback includes text readability, translations and correction submission.

User acceptance records include participant counts, observed difficulties and resulting changes. Usability findings are evaluated separately from infrastructure health and technical service checks.

## 4. POST-DEPLOYMENT VALIDATION, DOCUMENTATION, AND LESSONS LEARNED

### 4.1 Post-Deployment Validation

Post-deployment validation confirms the complete platform behavior after compatible component releases are installed. It covers infrastructure availability, application integration, interface actions, data access and recovery. Controlled accounts and representative learning material are used to keep acceptance activity separate from real learner records and training corrections.

| Component | Application checks |
| --- | --- |
| Interactive visualizations | Frontend type/unit/export checks; backend and deployment tests with a disposable pgvector database |
| Multilingual audio | Frontend type/build checks; backend tests; language-specific document-to-audio scenarios |
| Adaptive assessment | Frontend type/build checks; backend tests; complete quiz and restart scenarios |
| Image-to-text processing | Frontend type/export checks; OCR cleanup tests; image processing and feedback scenarios |

Visualization integration tests use `STUDIO_TEST_DATABASE_URL` with a disposable test database. Production Supabase data is excluded from that test fixture. API and proxy readiness are checked separately from model output and account isolation.

Audio acceptance verifies actual document indexing and the configured speech services, in addition to `/health`. Assessment acceptance exercises source ingestion, question/answer contracts, adaptation and persistent session state. OCR acceptance inspects both translation fields and retained corrections in addition to the root response.

### 4.2 Validation Activities

| Validation level | Required activities |
| --- | --- |
| Infrastructure | Inspect processes, HTTPS routing, persistent mounts and startup logs |
| Application | Verify schemas/indexes, model artifacts, endpoint behavior and controlled failures |
| User interface | Exercise hosted builds, uploads, microphone flow, result display and history |
| Identity and data | Test accepted identity issuers, unauthorized requests and owner isolation |
| Recovery | Restart services, restore consistent backups and check previous-release compatibility |

Group validation also confirms that common frontend navigation connects the intended services. Authentication is tested against each relevant backend issuer, and switching accounts must not expose previously loaded private material. Component storage remains separate even when the interface presents a shared workspace.

### 4.3 Supporting Operational Artefacts

The deployment package includes dependency manifests, component environment templates, model endpoint definitions and installation guidance. Visualization additionally includes the GitHub Actions workflow, release receiver, activation logic and systemd templates. Audio includes backend/frontend Dockerfiles and Compose configuration. Assessment includes its generation endpoint and persistent-state services. OCR includes enhancement, line extraction, translation and feedback services.

The visualization account-controller installation record is maintained in `koji-interactive-infographic-generator/docs/modal-accounts.md`. It includes the dated readiness, authorization, account-switching, rollback and sketch-inference results. Common authentication setup is maintained in `common-frontend/AUTH_SETUP.md`; it specifies backend issuer compatibility while preserving component data credentials.

The deployment inventory retains the application commit, frontend build, model revisions, schema version, service origins, persistent paths, acceptance output and backup identifiers. Credentials remain in private configuration stores. These records support troubleshooting and reproducible restoration without exposing learner data or deployment secrets.

### 4.4 Key Lessons Learned

- Long-running learning tasks need an execution model that survives browser closure; visualization uses a separate durable worker for this purpose.
- Frontend build variables and backend runtime variables have different update requirements. Changing a public API origin requires a new client build.
- Model endpoint availability does not guarantee complete learning output. Translation fields, enabled audio and source-grounded answers require explicit acceptance checks.
- Local session databases, document indexes and feedback datasets are essential deployment state and require coordinated persistence and backup.
- Frontend authentication and server-side authorization are separate responsibilities. Identity compatibility and ownership enforcement must be tested at the API boundary.
- Application, schema and model releases need compatible contracts and independent rollback decisions.

### 4.5 Conclusion of Post-Deployment Assessment

BioLearnX uses Modal.com and Supabase across all four components. Koji and Baskaran additionally use AWS EC2 for their backends and Vercel for their frontends. The components retain independent release responsibilities while supporting a common learning experience.

Visualization provides an automated tested-artifact release path, backend rollback and a dated record of EC2, Vercel proxy and Modal account-control checks. Audio, assessment and image processing retain component-specific build, hosting, persistence and access requirements. Group release sign-off requires recorded results for all four learning scenarios, data-boundary checks and recovery activities.
