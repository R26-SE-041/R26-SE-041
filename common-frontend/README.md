# BioLearnX learning dashboard

A responsive common entry point for the four independently deployed BioLearnX components. The dashboard opens immediately, with no shared-login or backend configuration required. Every component opens in a new tab and keeps its existing authentication.

## Run locally

```powershell
cd common-frontend
npm.cmd install
npm.cmd run web
```

Open http://localhost:8085. No `.env.local` is required for the launcher.

## Components

| Workspace | Deployment |
| --- | --- |
| Visual Studio | https://koji-studio.vercel.app/ |
| VoiceLearn | https://voicelearn-audio.vercel.app/ |
| Adaptive Quiz | https://nishy-adaptive-quiz.vercel.app/ |
| Smart Notes | https://sarmitha-ocr.vercel.app/ |

Edit names, descriptions, capabilities and destinations in `src/launcher/components.ts`. The desktop/mobile web layout is in `src/launcher/Launcher.web.tsx` and `styles.ts`; the native link launcher is in `Launcher.tsx`.

The dashboard includes component search, responsive top navigation, a suggested learning journey, and a shortcut to the most recently opened component. Launch history is stored only in this browser; it records link openings, not login state, completed lessons or learning progress. Navigation continues working when browser storage is blocked.

## Design reference

The visual reference is [Anthropic's official homepage](https://www.anthropic.com/), inspected on 18 October 2026: warm ivory (`#FAF9F5`), paper (`#F0EEE6`), charcoal (`#141413`), terracotta (`#C6613F`), and sand (`#E3DACC`). The layout pairs bold sans-serif headlines with serif editorial text, generous spacing, understated links, paper panels, and subtle reveal transitions. Arial and Georgia match the official site's declared fallback families; proprietary Anthropic fonts are not included. Biology illustrations and BioLearnX branding are original. Reduced-motion preferences disable reveal animations.

This is navigation integration. Accounts, sessions, databases and content remain managed by each component. The dashboard does not embed or proxy the component apps.

## Validate and build

```powershell
npm.cmd run typecheck
npm.cmd test
npm.cmd run build:web
```

The production website is exported to `dist/`.
Run `npm.cmd run preview` to preview that build at http://localhost:8085.

## Deploy on Vercel

Production: https://biolearnx-dashboard.vercel.app/

Import this repository and set **Root Directory** to `common-frontend`. The included `vercel.json` sets the build command to `npm run build:web` and output directory to `dist`. Use Node 24 and framework preset **Other**. The launcher needs no environment variables or backend proxy. Deploying this directory does not redeploy the other four components.

## Preserved integrated workspace

The previous API-backed workspace is preserved in `IntegratedWorkspace.tsx`, with its documentation in [INTEGRATED_WORKSPACE.md](INTEGRATED_WORKSPACE.md), [AUTH_SETUP.md](AUTH_SETUP.md), and [INTEGRATION.md](INTEGRATION.md). It is not imported by the launcher. To explicitly restore that implementation, change `App.tsx` to:

```tsx
export { default } from './IntegratedWorkspace';
```

That alternative still requires the authentication and backend setup described in its guide.
