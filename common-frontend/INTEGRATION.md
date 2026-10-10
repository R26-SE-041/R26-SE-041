# Common frontend integration

All implementation changes live in `common-frontend`. Backend schemas, databases and original frontend source files are preserved. Shared Supabase login identifies the user; each component retains its own workflow and storage. Dashboard data aggregation can be added later with explicit summaries from each service.

| Component | Existing API groups covered | Common frontend flow |
| --- | --- | --- |
| Shared auth | Supabase SDK sign-up/sign-in/reset/update/sign-out | Shared account, refresh, password recovery, local sign-out |
| Visual | Orchestrator `/generate`; prompt `/enhance`; image `/generate`; evaluation `/evaluate` | General images, anatomy enhancement, evaluation and retries |
| Visual interaction | `/auto-labels`, interactive analysis and question requests | Verified labels, point/box selection, identify/explain/ask |
| Visual 3D | `/convert/start`, `/convert/result/{id}` | Poll jobs, view and download GLB, conversion feedback |
| Visual memory and feedback | `/memory/settings`, `/memory/preferences`, preference revoke, `/memory/clear`, `/memory/context`; output feedback | Explicit memory settings, revoke/clear, prompt/image feedback |
| Quiz documents | `/api/v1/documents/`, `/api/v1/documents/upload` | Upload and choose the existing shared document library |
| Quiz sessions | `/api/v1/session/start`, session readiness, quiz question/answer/advance | MCQ, structured, essay, mixed formats; terminal answers advance on the backend; unfinished open answers explicitly finalize |
| Quiz reports | Results, recommendations, session feedback | Marks, attempts, topic/Bloom breakdown, learning resources, feedback and report export |
| Notes | `/api/process`, `/api/enhance`, `/api/ocr`, `/api/feedback/ocr` | Image processing, translations, line review/correction, downloads and local saved results |
| Audio documents | `/api/v1/documents` upload/list/delete, `/ask`, `/enhance` | Separate document library, tutoring, query correction and cited answers |
| Audio voice | `/api/v1/voice/transcribe`, `/query`, `/tts` | Voice input, direct grounded answers, playback and downloads |
| Audio history/sessions | `/api/v1/history` create/list, history audio GET/PUT, `/api/v1/sessions/` | Saved text/audio, conversation identity and history retrieval |
| Connections | Service health endpoints | Per-service reachability checks |

Local visual/quiz/notes archives use independent IndexedDB databases per account. Audio conversation drafts use account-scoped storage; persistent audio history remains in the existing backend. Large images/audio are not written into small draft storage. Opening another module preserves the current workspace; account changes abort authenticated requests and unmount workspaces.

## Existing backend limits

- Quiz document listing is shared, and its current APIs do not enforce bearer-token ownership. Passing `student_id` is not server authorization. OCR also lacks backend auth enforcement. Frontend login cannot correct these backend security properties.
- Audio's verifier must accept tokens from the configured Supabase project; its current implementation uses HS256. Configure the existing matching project rather than putting a JWT secret in the frontend.
- OCR returns extraction and translations, not full contextual study-note synthesis. The UI labels this accurately.
- Audio session APIs currently do not return a complete message archive; the UI uses history endpoints and account-scoped drafts instead.
- Quiz time limits are advisory in the current backend; the frontend displays elapsed time without silently submitting answers.
- Deprecated visual `/localize-structures`, administrative `/generate-skill`, quiz debugging and deployment/metrics endpoints are excluded from learner navigation. Existing specialist frontends and operational tooling remain available.

## Verification boundary

`npm.cmd run typecheck`, `npm.cmd test` and `npm.cmd run build:web` validate source and transport contracts. The fixture server is exclusively a local test helper, with synthetic credentials and outputs. Real auth, model quality, uploads, microphone capture and database persistence require configured live services. Android/iOS have not been verified; web is the supported initial target.
