# VoiceLearn frontend on Vercel

This component is Expo + React Native Web. The EC2 backend is deployed separately.

Frontend project: `voicelearn-audio`, under `varanans-projects-e30f07cf`.
Production website: https://voicelearn-audio.vercel.app/study-assistant
The backend-pending notice is visible until a backend URL is configured. API
calls are blocked while it is pending so SPA HTML cannot crash document lists.

Verified on 2026-10-13: production HTTPS page and `/study-assistant` return 200,
`/test` redirects to `/study-assistant`, direct-route refresh works, desktop and
390px mobile views have no page errors or horizontal overflow, and no backend
requests are sent while connection is pending. A push to the configured branch
triggered a successful production build. Local type-check/export and seven unit
tests passed. Browser regressions passed across all twenty scenarios; the long
eleven-navigation test needed a 90-second total budget and the two affected
scenarios passed when rerun sequentially. AI workflows in browser regressions
use mocked endpoints, not a hosted EC2 backend.

## Git-connected project

- Repository: `R26-SE-041/R26-SE-041`
- Root directory: `baskaran-interactive-audio-communication/frontend`
- Framework preset: Other
- Node.js: 24.x
- Install command: `npm ci`
- Build command: `npm run build:web`
- Output directory: `dist`
- Production branch: `baskaran/expo-web-migration` (current component branch).

The tracked `vercel.json` handles direct navigation to `/study-assistant`, login,
dashboard routes, and redirects `/test` to `/study-assistant`.

## Backend connection

Set `EXPO_PUBLIC_API_URL` to the real HTTPS backend origin, with no trailing slash,
in Vercel Production and Preview environment settings. Rebuild after changing it.
Do not configure localhost on a public deployment: it points to the visitor's
computer and HTTPS pages cannot reliably call an HTTP backend.

Before the EC2 backend is available, the frontend can be published for UI review,
but uploads, document answers, OpenClaw, flashcards, and audio generation are not
an end-to-end hosted service. Supabase auth is currently a local mock and also
needs production integration. Do not describe a UI-only deployment as complete.

On EC2, add the actual production Vercel origin to `ALLOWED_ORIGINS`. Approved
preview origins need separate CORS configuration. Keep gateway tokens, Gemini
keys, Supabase service-role keys, and backend `.env` out of Vercel frontend env.

## Verification

Run `npm run type-check`, `npm test`, and `npm run build:web` locally. After deploy,
check `/`, `/study-assistant`, `/test`, direct-route refresh, CSS/JS loading, and
the layout on a phone-sized browser. Once the backend is connected, verify login,
upload, Q&A, saved audio, flashcards and reopening/deleting only disposable test
items. Local browser history does not automatically migrate to a new web origin.

## CLI alternative

With the configured monorepo root, run CLI deployments from the repository root,
linking that directory to `voicelearn-audio` first. Keep its `.vercel` metadata
ignored. Prefer pushing the production branch after tests pass; Vercel builds
only the configured frontend root. Do not link to `country-explorer`.
Git auto deployment requires connecting the repository and correct branch; a CLI
upload alone does not establish Git auto deployment.
