# BioLearnX common frontend

An independent Expo / React Native app, initially targeting web, with a warm cream, terracotta and charcoal palette and translucent glass cards. It calls the existing four APIs. No existing backend or frontend source files are changed.

## Run

Node 24 is recommended (the proxy uses Node's env-file support).

```powershell
cd common-frontend
npm.cmd install
Copy-Item .env.example .env.local
```

Edit `.env.local` with the **new common Supabase Auth project's** URL and public anon/publishable key. Keep existing component data projects separate. Existing authenticated backends need additive support for the new auth issuer while retaining their original login support; changing frontend variables alone does not enable this. See [AUTH_SETUP.md](AUTH_SETUP.md). Never put a service-role key or JWT secret in `EXPO_PUBLIC_*` variables. Set `VISUAL_API_URL` to your deployed **orchestrator** URL, and configure the five specialist visual agent URLs (`PROMPT`, `IMAGE`, `INTERACTIVE`, `EVALUATION`, `THREED`) for the complete studio. Set the remaining target URLs to your running backend root URLs.

In two terminals:

```powershell
cd common-frontend
npm.cmd run proxy
```

```powershell
cd common-frontend
npm.cmd run web
```

Open http://localhost:8085. Without Supabase configuration, the login screen and all four component workspaces are available in preview mode. Navigation and local form editing work in preview; backend learning actions require sign-in. Preview audio does not load or persist an account draft. No mock AI outputs are used.

## Frontend files for team members

Each learning component has its own entry screen. Make component-specific UI changes in that feature's folder:

| Area | File / folder |
| --- | --- |
| Dashboard overview | `src/screens/Dashboard.tsx` |
| Visual studio | `src/features/visual/App.tsx` and `src/features/visual/components/` |
| Adaptive practice | `src/features/quiz/Quiz.tsx` and `src/features/quiz/Results.tsx` |
| Image to notes | `src/features/notes/Notes.tsx` |
| Audio tutor | `src/features/audio/AudioTutor.tsx` |
| Login / registration | `src/screens/Login.tsx` |
| Connections / account | `src/screens/Connections.tsx` |
| Dashboard cards and navigation labels | `src/navigation.ts` |
| Shared UI and theme | `src/ui.tsx` |

`App.tsx` owns the shared session, navigation, layout and feature lifecycle. `src/modules.tsx` exports the four feature screens. Update each feature's files for its UI; update shared files when the change should apply across the workspace. Feature state remains mounted while switching tabs and is reset when the account changes or signs out.

## Run all backends together

Use each component's existing Python environment and configuration. The quiz and OCR guides both default to port 8000; choose different ports when running them together:

| Component | Working directory | Command / address |
| --- | --- | --- |
| Visual | `koji-interactive-infographic-generator/backend` | Existing Modal orchestrator deployment URL |
| Quiz | `nishy-adaptive-quiz-recommender/backend` | `uvicorn app.main:app --reload --port 8000` |
| Notes | `sarmitha-image-text-extractor-study-gen/backend` | `uvicorn main:app --reload --port 8001` |
| Audio | `baskaran-interactive-audio-communication/backend` | `uvicorn app.main:app --reload --port 8002` |

The local proxy listens only on loopback port 8787, forwards bearer tokens and uploads to fixed configured targets, and accepts the common app's origin. It avoids modifying the backends' CORS rules. It is a development helper, not a production API gateway. Existing frontends can keep using their own configured URLs and ports. If you change a backend's running port, any original frontend connecting to that instance needs its URL configured accordingly; alternatively keep your existing backend ports and enter those in this app's configuration.

For production, set `EXPO_PUBLIC_*_API_URL` to HTTPS services with the web app origin allowed in CORS, or deploy a properly configured same-origin reverse proxy. Do not publish localhost API URLs.

## Shared login: actual compatibility

- Supabase SDK handles registration, login, refresh and session persistence. The app uses its own storage key. Signing out uses `scope: local` to avoid signing out the other frontends' sessions.
- Audio's current token verifier supports HS256 and needs the matching existing Supabase JWT secret on its backend. Projects issuing ES256 tokens require a backend verifier update; this app does not silently bypass verification.
- Visualization validates Supabase bearer tokens for user-scoped memory. Generation currently has its existing access behavior.
- Quiz receives the signed-in Supabase user ID as `student_id`, but its document/session APIs currently do **not** enforce token ownership. Its existing document list is shared. OCR also has no backend auth enforcement. Sending a token or hiding screens does not secure those services. Full cross-service authorization requires additive backend work and is outside this isolated frontend change.
- Password recovery opens the common app's password-update screen. Add the common app origin to the common Auth project's allowed redirect URLs.

## Included learning flows

- Visual: raw and orchestrated generation, anatomy prompt enhancement and evaluation, point/box region interaction, automatic anatomy labels, image/SVG export, feedback, asynchronous 3D conversion/view/download, local history, and personal-memory controls.
- Quiz: document upload/library selection or topic-only MCQ, four question formats, counts, difficulty and optional timer, readiness polling, answer retries/hints, correct backend advancement, resumable local sessions, detailed analytics/recommendations, report export and feedback.
- Notes: image upload, combined processing or enhancement/OCR separately, original comparison, Sinhala extraction and available Tamil/English translations, per-line OCR correction, text/image/JSON downloads, and local saved results. The current API does not synthesize full study notes.
- Audio: document upload/list/delete, microphone or audio-file transcription, direct document voice questions, editable/corrected transcripts, general/document-grounded tutoring in three languages, citations, spoken answers/downloads, backend conversation history and saved audio.
- Connections: per-backend health checks with actionable failures.

The four workspaces retain independent state when navigating between them. Signing out unmounts them; local archives are namespaced by account and component. The dashboard connects navigation and does not merge component databases. Original frontends remain independently runnable against the same backends. Native file/audio and 3D adapters remain follow-up work: this release targets web. Browser recording requires microphone permission and localhost or HTTPS. Health checks confirm API reachability, not model availability.

See [INTEGRATION.md](INTEGRATION.md) for endpoint coverage and backend limitations. Administrative and deprecated endpoints are not presented as learner actions.

## Validation

```powershell
npm.cmd run typecheck
npm.cmd run test
npm.cmd run build:web
```

Type checking, 11 contract/proxy tests and the web export passed. Browser checks used the explicitly separate synthetic fixture server in `tests/serve-fixtures.mjs` for shared sign-in, quiz progression/reporting, audio responses/history/TTS, and visual generation. These do not establish live model accuracy or live database/auth compatibility. Browser file selection and microphone recording have not been exercised end to end. Live verification requires working model endpoints and shared Supabase configuration; no production mock fallback exists.

If the npm registry is unavailable and the original visual frontend already has installed dependencies, `node scripts/reuse-local-visual-deps.mjs` copies missing dependencies into this app without changing that frontend. Normal setup uses `npm.cmd install`.
