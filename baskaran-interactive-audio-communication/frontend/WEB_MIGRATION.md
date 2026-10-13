# Expo Web migration

This component now uses Expo/Metro, React Native and React Native Web instead of
the Next.js runtime. The current scope is the browser app. Android/iOS builds
and native microphone/file/storage adapters are deferred.

## UI and feature preservation

`App.web.tsx` registers through Expo and uses a React Native Web root. The eight
existing pages live in `src/screens/*.web.tsx`. Their browser presentation,
warm glass design tokens, SVG icons, responsive Tailwind styling and existing
workflow logic are retained. React DOM is an intentional web platform adapter,
not a native mobile implementation. Expo supports this combination:
https://docs.expo.dev/workflow/web/.

The web screens retain document upload/drop/removal, English/Tamil/Sinhala
selection, Document Study, microphone recording and audio upload,
transcript review/correction, grounded answers and sources, language-specific
TTS, Sinhala answer approval/editing, local question history, all document action
commands, source-linked sections, flashcard flips, downloads, playback commands,
saved result reopening and confirmed deletion. API endpoints and the backend
are unchanged. Existing mock authentication remains mock authentication.

The original URLs are preserved: `/`, `/study-assistant`, `/documents`, `/login`,
`/register`, `/dashboard`, `/dashboard/documents`, `/dashboard/history`.
`/test` redirects to `/study-assistant`. Browser back/forward navigation is handled
by React Router. Missing page URLs show a page-not-found message.

## Run and export

Use Node 24.3 or later, preferably the current Node 24 LTS release.

```sh
cd baskaran-interactive-audio-communication/frontend
npm ci
# Copy .env.example to .env.local and set the public backend address.
npm run dev
```

Open http://localhost:3000/study-assistant. `npm run web` is an alias.
The dev launcher builds/watches the original Tailwind stylesheet and starts Expo.
The FastAPI service continues on port 8000.

```sh
npm run type-check
npm run lint
npm test
npm run build:web
npm start
```

The production website is exported to `dist/`. `npm start` serves that export
with deep-link SPA fallback and the former security headers. `PORT` defaults to
3000; `HOST` defaults to 127.0.0.1. Docker binds 0.0.0.0. Docker builds its own
export; there is no `.next/standalone` requirement.

Set `EXPO_PUBLIC_API_URL` before exporting. Expo embeds public values at build
time; changing a server runtime variable after export does not change the website.
Never put Gemini, Modal, MCP or Supabase service-role secrets in public variables.
For hosting use the actual HTTPS backend URL. `vercel.json` and Netlify's
`public/_redirects` preserve deep links and refresh. The backend must allow the
chosen frontend origin. Hosting/deployment itself is not part of this migration.

## Existing data

The IndexedDB name `voicelearn-test-history`, theme key `vl-theme` and action
session key `voicelearn-action-session` are unchanged. To access existing browser
history use the same origin (`http://localhost:3000`); switching to 127.0.0.1,
another port or a hosted domain creates a different browser storage origin.
Server-side `local_actions`, `local_documents` and `local_history` are untouched.

Python's broad `lib/` ignore rule previously hid `frontend/src/lib`. A scoped
exception now tracks those application modules. Environments, backups, generated
CSS, server data, build outputs and test artifacts remain ignored.

## Verification

`npm run test:web` uses installed Google Chrome through Playwright against an
already running app. Tests mock AI/backend responses to exercise the migrated UI
without consuming quotas or deleting real saved records. They cover original
routes, theme persistence, language/mode changes, uploads, transcription,
correction, question/answer/audio/history, revision variants, cards, downloads,
source-only requests, all twelve playback phrases, reopen/refresh and confirmed
deletion. These tests do not establish AI answer quality or live MCP availability.

Validated on 13 October 2026: production export, TypeScript, lint and four playback
unit test groups passed. All 20 browser workflow tests passed on the running Expo
dev app (15 also passed on the production export before the additional coverage).
Synthetic microphone recording passed. Real backend checks reopened the existing
29-item saved library, a sectioned audio revision with its original source passage,
and a six-card deck without regeneration; there were no browser page errors.
MCP discovery confirmed all six tools. New AI generation was not repeated during
the frontend migration.

Original migration screenshots covered light, dark and narrow layouts.
The current interface retains Document Study; the specialized tutor was removed.

Microphone permission/device behavior needs a real-device check; a synthetic or
uploaded recording only proves the browser pipeline. OpenClaw model quota limits
remain external to this frontend migration.
The local gateway needs Node 24.16+ (the existing helper uses 24.21) due to its
SQLite embedded-NUL check; the system Node 24.14 runs the Expo web app successfully.

## Recovery

The local Git tag `baskaran-nextjs-before-expo-20261013` points to `4177629`, the
Next.js baseline on GitHub. Migration work is isolated on
`baskaran/expo-web-migration`. Preserve or commit migration work before switching
branches; do not use a destructive hard reset to roll back.

Local backups in the ignored `.migration-backup/pre-expo` directory include a
tracked Next.js source archive, the previously ignored library modules, private
environment files and server-side data. Never commit or publish that directory.
The portable Python runtime and virtual environments remain machine-local.

To run the old version in a separate checkout, restore the baseline frontend,
restore the backed-up `src/lib` modules and `.env.local`, then run `npm ci` and
`npm run dev`. Its API client uses `NEXT_PUBLIC_API_URL`; the migration's client
uses `EXPO_PUBLIC_API_URL`. Both point to the same unchanged FastAPI backend.

## Document-only update

The specialized tutor panel, topic cards, quick prompts and mode selector were
removed. Document Q&A now defaults to document grounding. Shared three-language
strings moved to `src/lib/studyLocale.ts`; stored history remains readable.

Validation after removal: 20 browser regressions, four audio-command tests,
TypeScript checking and production export passed. The live saved library still
contained 29 items and one indexed document. Desktop and 390px layouts were
inspected; the narrow layout had no horizontal overflow.

## Signup verification

Registration collects a full name, email and matching passwords. Learner role,
institution/course and preferred language are optional profile metadata; they
do not grant permissions or override a language chosen in the study interface.
Confirmation redirects to `/login`. Email delivery still depends on Supabase's
email provider configuration.

The SDK request/confirmation/retry checks in `e2e/register.spec.ts` intercept all
signup requests, so they create no accounts and send no email. For the complete
suite, export with these isolated test settings in PowerShell:

```powershell
$env:EXPO_PUBLIC_SUPABASE_URL='https://signup-test.supabase.co'
$env:EXPO_PUBLIC_SUPABASE_ANON_KEY='signup-test-public-key'
npm run build:web
```

Serve that export with `PORT=4185` using `node scripts/serve-web.cjs` in another
terminal. Run tests with `WEB_TEST_URL=http://localhost:4185` and
`SIGNUP_AUTH_TEST=1`. Without the flag, only the two SDK integration cases skip;
validation and responsive-layout checks still run. Remove the test Supabase
environment overrides and rebuild before using the normal local application.
