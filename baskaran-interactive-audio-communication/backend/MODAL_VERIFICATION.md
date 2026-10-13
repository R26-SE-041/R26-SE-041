# Modal workspace verification

Production services used by this component were verified on 13 October 2026.

| Workspace | Passed smoke checks | Completed (UTC) |
|---|---|---|
| visakanbaskaran | 14/14 | 2026-10-13T08:01:04+00:00 |
| krishnavaranan1 | 14/14 | 2026-10-13T08:10:48+00:00 |
| krishnavaranan | 14/14 | 2026-10-13T08:11:23+00:00 |
| varananrp | 14/14 | 2026-10-13T07:59:17+00:00 |

Endpoint source SHA-256: `625f570e1e96178e30dfead5b89b95e87ff13e79e471add542c35ca2fd9232a8`.

Each workspace passed real base/fine-tuned answers, RAG, correction, three-language WAV generation and speech recognition, Tamil/Sinhala translation, embeddings and reranking. These are startup/inference smoke checks, not exhaustive model accuracy, load or UI-command tests. Legacy apps were retained and were not part of this check.

The Windows switch wrapper was tested from visakanbaskaran to varananrp and back. Backend health stayed OK after each restart, and all 29 saved-library IDs and the one document ID were preserved. The app was left on visakanbaskaran; frontend, backend and OpenClaw remained running.

Source/endpoint changes require re-verification before switching. Detailed runtime reports and environment backups are ignored by Git. See [switching instructions](MODAL_WORKSPACES.md).
