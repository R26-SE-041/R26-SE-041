# Document-only Modal verification

The component now uses 12 endpoints and has no dedicated specialized tutor service.
All four workspaces passed the 13 production smoke checks after removal.

| Workspace | Passed checks | Completed (UTC) |
|---|---|---|
| visakanbaskaran | 13/13 | 2026-10-13T10:24:34+00:00 |
| krishnavaranan1 | 13/13 | 2026-10-13T10:32:35+00:00 |
| krishnavaranan | 13/13 | 2026-10-13T10:27:05+00:00 |
| varananrp | 13/13 | 2026-10-13T10:26:56+00:00 |

Endpoint source SHA-256: `a50377a308efef404c9173ed3e009741464af4fe35d6c389b396d63c529fb860`.

Checks cover base document answers, RAG, correction, three-language WAV generation
and speech recognition, Tamil/Sinhala translation, embeddings and reranking.
These are startup/inference smoke checks, not exhaustive accuracy or load tests.
The isolated base app is `voicelearn-document-gemma`; older shared cloud apps
were not redeployed, stopped or deleted.

Additional validation after removal:

- Backend regression suite: 151 passed.
- Browser regressions: 20 passed; audio-command unit tests: 4 passed.
- TypeScript checking, Python compilation, whitespace checks and production web export passed.
- Real backend document Q&A returned a grounded answer with five source references.
- Direct Tamil and Sinhala document answers contained their native scripts without Latin letters.
- Desktop and 390px layouts were inspected; the narrow layout had no horizontal overflow.
- The updated Windows switch wrapper was tested from visakanbaskaran to varananrp and back.
- All 29 saved-library IDs and the one document ID were preserved.

The app was left on visakanbaskaran, with frontend, backend and OpenClaw running.
Source/endpoint changes require re-verification before switching. Runtime reports,
environment backups and QA screenshots are ignored by Git.
See [switching instructions](MODAL_WORKSPACES.md).
