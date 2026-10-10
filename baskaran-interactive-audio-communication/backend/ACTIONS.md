# Document actions and audio revision

This feature belongs only to the Baskaran component. Existing Q&A endpoints,
language routing, model deployments and benchmark tables are unchanged.
The study page has a separate **Document actions and audio revision** panel. Its microphone
reuses `/voice/transcribe`; its confirmation reuses `/voice/tts`.
The original Ask button continues to send study questions to the original pipeline.

## Working paths

`ACTIONS_PROVIDER=direct` executes the validated tool sequence deterministically.
This is the deadline fallback, not an OpenClaw or new LangGraph integration.

`ACTIONS_PROVIDER=openclaw_mcp` sends the action ticket to the configured OpenClaw
agent. That agent must call the stdio MCP adapter's tools, which call authenticated
FastAPI bridge endpoints. There is no automatic fallback if OpenClaw fails.
Backend execution records and verified files decide success; agent prose is ignored.

Current status: OpenClaw 2026.9.8 (fc23bc8) is installed in the component-local
prefix. Use `openclaw-local.cmd`, which selects private Node 24.21.0 and isolated
state/config under `.actions-runtime/openclaw-state`. A dedicated
`voicelearn-actions` agent and authenticated loopback Gateway configuration are
prepared. `config validate` and OpenClaw's `mcp doctor voicelearn-actions --probe`
passed. Four production MCP tools are selected; built-in execution, filesystem,
browser and messaging tools are denied. Heartbeats are disabled.

A Gateway token was generated in local private files without printing it.
The dedicated agent uses `google/gemini-3.5-flash-lite`, with empty model fallback
chains and the Google plugin enabled. The user confirmed the project is on the
Free tier in AI Studio; no billing upgrade was performed. Gemini 3.8 requests
stalled during initial feasibility checks, so the working Flash-Lite model was
selected. The local Gateway is running. The user verified summarize, save/download
and combined summarize/save in OpenClaw mode. Voice input remains untested.
Gateway tokens and the bridge secret stay in ignored local files. Gemini receives
scoped action instructions and small tool results, not the document or transcript.
Temporary ping access has been removed from the production Gateway tool allowlist.
Heartbeats, cron and the memory-core plugin are disabled in this isolated setup.
These are prototype observations, not measured reliability or research novelty.

Historical preparation notes (superseded by the current status above, 7 October 2026): the real stdio MCP adapter was verified,
including fresh ping execution and disabled-ping rejection. The **Gateway/model**
loop was unverified at that stage. OpenClaw npm metadata access returned HTTP 403 in this
execution environment. System Node is 24.14.0; current official install docs
require Node 24.16+ or 26.1+. A separate official Node 24.21.0 runtime (npm 11.19.0)
was downloaded, SHA256-verified and installed under
`.actions-runtime/node-v24.21.0-win-x64`. The system installation was not updated.
An actual OpenClaw install using that supported runtime also returned HTTP 403
from `https://registry.npmjs.org/openclaw`; no OpenClaw installation completed.
PowerShell's registry request additionally reported a TLS certificate trust
failure. No TLS verification or network policy was disabled. Anthropic API access
and a Gateway token are not configured. Direct mode remains active.

Network diagnosis: the campus browser displayed SLIIT's Application Control
block for Npmjs. After switching to the user's mobile hotspot, a metadata lookup
with `--strict-ssl=true` succeeded and returned version `2026.9.8`. Installation
is a separate step; metadata access alone does not prove the runtime is installed.

Run from `backend` to install the pinned release with TLS verification enabled:

```powershell
$privateNode = Join-Path $PWD '.actions-runtime/node-v24.21.0-win-x64'
$env:PATH = "$privateNode;$env:PATH"
& (Join-Path $privateNode 'npm.cmd') install --global --prefix .actions-runtime/openclaw openclaw@2026.9.8 --strict-ssl=true --allow-scripts=openclaw --cache .actions-runtime/npm-cache --no-audit --no-fund
& ./.actions-runtime/openclaw/openclaw.cmd --version
```

The PATH assignment affects only this terminal. The CLI is component-local;
subsequent examples using `openclaw` can use the full `.cmd` path above.
Configure the selected provider's API key locally, never in chat or source control.
Only enable `openclaw_mcp` after the live Gateway feasibility check passes.

## Local provider credential step

Open `https://aistudio.google.com/api-keys`, sign in and create a key in a project
whose Billing Tier is **Free tier**. Do not enable paid billing. The zero-cost
target applies to orchestration API usage within free-tier quotas, not existing
Modal inference, network access or other project costs. A model's presence in the
catalog does not prove the key's project is on the free tier. Quota/provider
failure must be recorded as a failed test; do not switch to a paid provider.

Set the blank `GEMINI_API_KEY=` line in
`backend/.actions-runtime/openclaw-state/.env` to the actual key locally. Preserve
the generated `OPENCLAW_GATEWAY_TOKEN` line. This file is ignored by Git; do not
paste it or screenshots containing it into chat. No key is needed in frontend
code. After saving, validate provider/model availability and start the isolated
Gateway before the live tool execution proof.

```powershell
./openclaw-local.cmd --version
./openclaw-local.cmd config validate
./openclaw-local.cmd mcp doctor voicelearn-actions --probe
```

Official key instructions: https://ai.google.dev/gemini-api/docs/api-key
Free-tier pricing: https://ai.google.dev/gemini-api/docs/pricing

Gemini receives the validated action intent, scoped ticket and small tool results;
the document and summary remain in FastAPI/Modal. The current parser has already
chosen the intent and the prompt specifies tool order. The experiment measures
model-driven execution of validated actions versus deterministic execution; it
does not prove independent unrestricted natural-language intent recognition.

## Enable the deadline fallback

Add to `backend/.env`, then restart the backend:

The implementation enabled the existing local guest demo in the current `.env`
with `ACTIONS_ENABLED=true`, `ACTIONS_PROVIDER=direct` and
`ACTIONS_ALLOW_LOCAL_GUEST=true`. Existing settings were preserved. The safe
defaults in source and `.env.example` remain disabled and require authentication.

```dotenv
ACTIONS_ENABLED=true
ACTIONS_PROVIDER=direct
ACTIONS_ALLOW_LOCAL_GUEST=false
ACTIONS_MAX_DOCUMENT_CHARS=12000
ACTIONS_TIMEOUT_SECONDS=600
```

Use a signed-in account for user isolation. For the existing localhost guest demo,
set `ACTIONS_ALLOW_LOCAL_GUEST=true`. This works only for loopback requests and
local Chroma configuration. It deliberately uses the existing shared `guest`
document identity; it does **not** isolate different people using guest mode.
Do not enable guest mode in a shared/hosted deployment. Bind the demo backend to
127.0.0.1. Reverse proxy setups need authenticated accounts, not guest mode.

`MODAL_BASE_GEMMA_URL` must point to the existing base document-answer service.
Summary generation uses a dedicated summary prompt and **all extracted text**
of the selected document, without top-k retrieval. PDF/TXT/MD are supported.
Oversized documents are rejected, never silently truncated. The 12,000-character
cap is a conservative prototype scope, not a measured tokenizer context limit;
validate coverage and latency on the actual deployed model and demo PDFs.
No model deployment or additional GPU configuration is needed by this patch.

## OpenClaw MCP setup

Install optional adapter dependencies separately from the main backend. Current
MCP SDK releases require newer shared packages, so do not upgrade the existing
backend environment just to add MCP. Use an isolated target:

```powershell
python -m pip install --target .actions-runtime/python -r requirements-actions.txt
```

On the separately installed OpenClaw runtime:

1. Configure a fresh Google AI Studio API key locally and confirm its project
   is on the Free tier before generation tests. The current candidate is
   `google/gemini-3.5-flash-lite`; confirm account availability with
   `openclaw-local.cmd models list --provider google --refresh` after credentials
   are ready. Keep model fallback chains empty. The selected model must pass
   actual tool-calling checks; selection is not a measured reliability result.
   Keep summary generation on the existing Modal base model. No provider billing
   upgrade is needed for the selected free-tier orchestration model within quota.
2. Create a dedicated `voicelearn-actions` agent. Its tool policy should allow
   only the VoiceLearn tools; exclude shell, browser, messaging and other tools.
3. Enable the Gateway chat-completions endpoint (it is disabled by default):
   `gateway.http.endpoints.chatCompletions.enabled = true`.
4. Keep the Gateway on loopback/private networking. Its token has operator access.
5. Add a stdio MCP server with the backend environment's Python executable as
   `command`, `run_actions_mcp.py` as an absolute-path argument and backend as `cwd`.
   The launcher reads only adapter settings from backend `.env`; a random
   `ACTIONS_BRIDGE_SECRET` has been generated there without printing it. An
   explicit process environment value overrides the local file. Never pass
   secrets in command arguments.
6. Set `VOICELEARN_BACKEND_URL=http://127.0.0.1:8000` in the adapter environment.
   If using containers/WSL, localhost refers to that environment; configure a
   reachable private address instead. The adapter must reach FastAPI and FastAPI
   must reach the Gateway.

Backend environment:

```dotenv
ACTIONS_ENABLED=true
ACTIONS_PROVIDER=openclaw_mcp
OPENCLAW_GATEWAY_URL=http://127.0.0.1:18789
OPENCLAW_AGENT_ID=voicelearn-actions
OPENCLAW_GATEWAY_TOKEN=<backend-only gateway token>
ACTIONS_BRIDGE_SECRET=<same secret in the MCP process environment>
```

See current official documentation for version-specific policy/configuration keys:
- https://docs.openclaw.ai/tools/mcp
- https://docs.openclaw.ai/gateway/openai-http-api
- https://docs.openclaw.ai/tools
- https://docs.openclaw.ai/install
- https://docs.openclaw.ai/providers/google
- https://ai.google.dev/gemini-api/docs/pricing
- https://ai.google.dev/gemini-api/docs/function-calling

## Adapter-only checks (no microphone, model or Gateway required)

The isolated dependency target has been installed in `.actions-runtime/python`.
Use a working Python 3.11+ interpreter:

```powershell
python check_mcp_adapter.py --ping
python check_mcp_adapter.py
```

The first verifies actual stdio discovery and two distinct server-generated
execution IDs. The second verifies only the four production tools are discoverable
and ping cannot execute. This is not an OpenClaw feasibility pass. The launcher
processes Windows package initialization hooks and keeps its dependency paths
inside the adapter process, separate from FastAPI.

## Feasibility proof

Temporarily set `VOICELEARN_MCP_ENABLE_PING=true` in the MCP process environment.
Allow `ping_tool` in the dedicated agent's tool policy. Reload the Gateway's MCP
connection after changes, then:

```powershell
openclaw mcp doctor voicelearn-actions --probe
python check_openclaw_actions.py
```

The MCP server generates an execution ID and logs it to stderr. Match it with the
Gateway response. Block the ping tool and repeat: it must not execute. Discovery
alone or a plausible response does not prove the loop. Remove the ping environment
   flag and permission before the production demo. If the loop cannot be proven in
the agreed timebox, keep `ACTIONS_PROVIDER=direct` and describe the fallback honestly.

## Demo

1. Restart backend; open `/study-assistant`, Document Study mode.
2. Select a PDF/TXT/MD in **Document for this action**.
3. Record English speech or type `Summarize this document`; click **Run action**.
4. Use `Save the summary` in the same browser tab/session/document later.
5. Alternatively use `Summarize this document and save it`.
6. Verify summary text, actual `.txt` download and brief English confirmation.
7. Verify ordinary questions through the original Ask button in all languages.

The command parser accepts a narrow anchored English command set, including
polite prefixes and summarize/summarise spelling. Unsupported commands return
guidance; they never become Q&A requests. Selected documents are checked against
the authenticated owner. Action tickets expire, restrict allowed operations and
are closed after completion/failure. Treat tickets as credentials; do not log them.

## Persistence and limitations

Actions and summaries use SQLite under `local_actions`; files use generated IDs.
Requests return a job ID and the panel polls progress. Background work runs in the
FastAPI process: restart/crash loses active work; expiry surfaces an honest failure.
This is a single-backend prototype, not a distributed job queue. Keep the MCP
bridge pointing to the same backend process. Completed summaries survive restart.
Downloads use the same authenticated API client and recheck source ownership.
Deleting the source prevents download, but does not automatically purge summary
records. Local action files need explicit retention/cleanup for a future deployment.

The frontend tracks the previous summary by authenticated owner, browser action
session and selected document. A different tab/session cannot silently save another
session's latest summary. Final mic/STT/TTS and summary quality must be checked with
actual services; text output remains available if TTS fails.

Disable with `ACTIONS_ENABLED=false` and restart backend; the panel disappears.

## Implementation validation

- 19 action tests passed, including real local artifact content, later saving,
  ownership, bridge authentication, closed/expired tickets, timeouts, partial
  failure, mocked Gateway/MCP execution and rejection of fabricated agent success.
- 19 selected existing document/model-routing/ASR regression tests passed.
- Frontend TypeScript checking and production build passed.
- A separate existing voice-test run passed 9 tests and failed 3: Tamil/Sinhala
  TTS tests send English-only text that the existing cleaner rejects; the
  unauthenticated transcription test expects rejection although current auth is
  optional, and attempts an unmocked live STT call. Voice/auth implementation
  was not changed by this feature. These failures are not resolved here.
- MCP adapter scripts were syntax-checked. MCP 1.30.0 was installed in an isolated
  target and real stdio discovery,
  ping execution and disabled-ping checks passed. Subsequently the user verified
  all three typed summary/save flows in OpenClaw mode. Microphone end-to-end
  validation remains pending.
- Formatting follow-up: 19 action tests pass. A leading standalone `thought`
  model label and paired `<think>` blocks are removed from summaries. The screen
  retains Markdown formatting; `.txt` downloads contain plain headings and bullet
  text. Previously stored summaries also display/download cleanly after restart.

## English document-to-audio revision

Command: `Create a short audio revision of this document and save it`.
The audio revision command always requests both transcript and WAV persistence.
This remains entirely inside the audio component; no quiz, infographic or OCR
component service is used.

1. `summarize_document` uses the existing Modal base answer model with a dedicated
   source-grounded spoken-script prompt. One short script is generated; an ordinary
   summary is not generated and then rewritten in a second model call.
2. `create_revision_audio` sends that script to existing English Kokoro TTS, checks
   the returned PCM WAV for duration and complete samples, and stores generated-ID
   audio under the ignored local action store.
3. `save_audio_revision` verifies that both the plain transcript and WAV exist.
   Backend records and artifacts, not agent prose, decide completion.

The panel shows the transcript, an audio player, playback speeds from 0.75 to 1.5,
transcript download and WAV download. Audio revision does not autoplay. Native
player controls provide pause/resume and seeking; voice playback controls and
separate topic audio sections are not implemented in this iteration.

If TTS fails, the job is partial and the transcript stays visible/downloadable.
It cannot claim successful audio generation. Audio routes enforce action ownership
and recheck source document ownership. No audio bytes or script are returned to
Gemini. Existing summary/save commands and the ordinary Q&A/TTS pipeline retain
their original behavior.

Source limits: PDF/TXT/MD up to the existing 12,000-character limit; no OCR.
The original English iteration is described above; current Tamil/Sinhala support
and command examples are described below.
The script prompt targets 180-250 words, with a hard 4,000-character response limit.
Exact length and duration are model-dependent. WAV duration is capped at 10 minutes
and bytes at 60 MB; existing action deadline is 600 seconds. Free-tier Gemini
quotas apply, and existing Modal generation/TTS usage costs remain separate.

Live verification (explicitly opt-in):

```powershell
python check_audio_revision.py --sample
```

This creates a clearly named fictional classroom test lecture, invokes the real
OpenClaw path and verifies the three tool records, downloadable transcript and WAV.
It writes non-sensitive metrics to ignored `.actions-runtime/audio-revision-check.json`.
It never automatically chooses a user's first document. Local guest mode and a
running backend/Gateway are required. Listen to the audio to assess pronunciation,
clarity and source faithfulness; structural validation does not establish these.

Validation for this addition: 26 action tests pass, covering artifacts, ownership,
tool ordering/scope, invalid audio, transcript retention and expiry during TTS.
Frontend type-check and production build pass. Adapter discovery exposes four
production tools, and disabled ping cannot execute. Live result is recorded
separately after completion; microphone testing remains pending.

Live sample observation: the OpenClaw workflow completed with a saved 80.18-second
WAV and transcript. The agent repeated some idempotent tool calls; the backend
reused the generated script/audio. Repeats remain visible in the stored trace.
This single run is not an aggregate reliability result.

Live download verification passed after backend restart: 194-word transcript,
80.18-second PCM WAV, 3,848,684 downloaded bytes. Both transcript equality and
WAV duration/sample availability were verified via authenticated action routes.
Evidence is `.actions-runtime/audio-revision-check.json` (no tickets/secrets).
Sixteen additional English-TTS/document-store/model-router/ASR tests passed.
The local backend was restarted on loopback port 8000 without autoreload after
its previous reload process stopped responding; Gateway remains on port 18789.
The browser automation surface was unavailable, so visual playback review and
microphone testing are still manual checks, not claimed as completed.

## Tamil and Sinhala commands and audio revision

The panel has its own **Command and output language** selector: English, Tamil,
or Sinhala. This selection controls command ASR, output localization and TTS.
It is independent of the ordinary Q&A panel. English commands remain accepted,
and a bounded native-script command set is now supported; this is not unrestricted
natural-language intent recognition. Users can edit recognized speech before Run.

| Operation | Tamil command | Sinhala command |
| --- | --- | --- |
| Summary | ???? ??????? ??????????? | ??? ????? ?????? ????? |
| Save summary | ??????????? ??????????? | ??????? ???????? |
| Summary and save | ???? ??????? ???????? ??????????? | ??? ????? ?????? ?? ???????? |
| Audio revision and save | ???? ????????? ??? ???????? ????????? ??????????? | ??? ?????? ???????? ????????????? ???? ???????? |

Existing Modal summary generation creates the English source revision. The
existing localizer prepares native text. Since existing Tamil TTS removes Latin
terms, any remaining foreign words trigger a bounded native-script rewrite using
the existing base answer model. It must preserve terms/names through translation
or native-script pronunciation; the final transcript is rejected if it still has
foreign-script letters or exceeds 6,000 characters. This script check is not a
semantic translation-quality score. Native-speaker review remains necessary.
If preparation fails, the English source stays visible, explicitly labelled as
English, and the job is partial; it cannot claim native audio success.

The verified transcript goes to existing `call_tamil_tts` (Indic Parler) or
`call_sinhala_vits_tts_direct` (Sinhala F5-TTS). No new TTS model is deployed.
The same owner-bound MCP tools generate/save transcript and WAV. Later summary
saving is scoped to document, session and language; switching to Tamil cannot
silently save an earlier English summary. Download filenames include language.
Old action records without language metadata default to English.

Live sample checks (no existing user document is selected):

```powershell
python check_audio_revision.py --sample --language tamil
python check_audio_revision.py --sample --language sinhala
```

These perform real model/localization/TTS calls and may consume existing Modal
credits, while Gemini orchestration remains on the confirmed free-tier project.
Evidence files are `.actions-runtime/audio-revision-check-<language>.json`.
Use `--verify-latest-sample --language <language>` to verify an existing sample's
downloads without another generation call.

41 action tests pass, including native command parsing, language-specific TTS,
wrong-language translation rejection and language-scoped saving. Frontend type
checking passes. Live native audio results are recorded after the runs finish;
microphone recognition and native-speaker audio/meaning review remain pending.

Multilingual validation follow-up: the native-script rewrite now passes the selected
Tamil/Sinhala language to the existing base endpoint, whose language policy would
otherwise force English. A regression test verifies that argument. Native-script
translation errors returned through MCP are retained as meaningful job errors,
instead of being replaced by a generic missing-tool message. No model redeploy
or change to the ordinary Q&A localization pipeline was needed.

Corrected real OpenClaw sample runs passed for both native languages:
- Tamil: 170-word native transcript; 87.59-second WAV; 7,725,468 downloaded bytes.
- Sinhala: 202-word native transcript; 110.05-second WAV; 4,853,052 downloaded bytes;
  full workflow took 326.64 seconds in this sample run.
Both runs verified transcript download equality, native language metadata, WAV
samples/duration, required tool sequence and saved files. The first attempted
native rewrite used English output routing and failed; it was corrected and
retested rather than treating those partial jobs as successes. The Tamil
verification was attached after its job started, so its recorded verification
interval is not reported as total generation latency.

Frontend type-check and production build pass. Sixteen related existing TTS,
document-store, model-router and ASR tests also pass. These sample observations
are not aggregate success rates. Native-speaker semantic/pronunciation review and
real microphone command testing remain pending. Use the displayed native command
phrases, check the ASR transcript and then Run action; free-form commands outside
the supported set are rejected with guidance.


## Source-linked sectioned audio revision

The audio action panel now offers **Sectioned audio with supporting source passages**
and **Single audio (baseline)**. Old records and API requests without a mode stay single.
Set ACTIONS_SECTIONED_ENABLED=false to hide/reject the sectioned mode without disabling
existing summaries, single audio, ordinary Q&A or Muscle Tutor.

Sectioned workflow (same four production MCP tools, no document/script bytes sent to Gemini):
1. summarize_document deterministically groups extracted paragraphs into up to three
   contiguous source spans (using line/sentence boundaries for long text without blank
   paragraphs) and records offsets plus a SHA-256 extraction hash. One
   structured generation call prepares an English spoken script for each span. Invalid
   JSON/section IDs/counts are rejected; there is no extra-generation fallback.
2. Existing localization prepares each native script. Titles remain English labels;
   the spoken transcripts/audio use the chosen language. Each section is checked before TTS.
3. create_revision_audio uses the existing language-specific TTS for each section,
   caches successful section WAVs, verifies matching PCM parameters, concatenates samples,
   and derives section start/end times from frame counts. No approximate sentence timestamps.
4. save_audio_revision verifies transcript, combined WAV, section files and JSON manifest.
   A changed source prevents successful saving. The tool response contains only IDs/flags/counts.

The browser provides Play from here, Replay section (stops at its end), active-section
highlighting, and an authenticated View source panel. Source passages remain in the original
source language. The source route rechecks ownership and extraction hash; deleted/changed
sources cannot be displayed as verified passages. Offsets refer to extracted text, not PDF
page numbers. An assigned source span is not proof that every generated claim is supported.

Full TXT and combined WAV downloads remain available. If one TTS section fails, the action
is partial: transcript and source passages remain available, but complete audio is not claimed.
One-paragraph documents may have one section. Tables/equations can lose structure in PDF
extraction. More localization/TTS calls increase latency and may consume more Modal credits.

Separate sectioned deadline: ACTIONS_SECTIONED_TIMEOUT_SECONDS=1800 (single remains 600).
Align Gateway mcp.servers.voicelearn-actions.requestTimeoutMs to 1800000 and
agents.defaults.timeoutSeconds to 1800, then restart Gateway.
The local runtime configuration has been updated accordingly. No billing/model changes.

Opt-in generated-sample verification:

    python check_audio_revision.py --sample --language english --revision-mode sectioned
    python check_audio_revision.py --sample --language tamil --revision-mode sectioned
    python check_audio_revision.py --sample --language sinhala --revision-mode sectioned

The checker creates a fictional three-paragraph lecture; validates required tool sequence,
transcript/WAV downloads, section timings and authenticated source passages. Reports are
ignored runtime JSON, keyed by language and mode. --verify-latest-sample verifies a saved
sample without another inference call. Human faithfulness/pronunciation and navigation
measurements must be collected separately; successful structural checks are not learning evidence.

Automated validation: 64 action tests pass (including baseline regression, native section
routing, exact source offsets, ownership/hash checks, invalid structured output, failed section
TTS, cached tools, manifest tampering and WAV mismatch). Frontend production build passes.

Gateway continuation handling: if an agent response arrives while a bridge call is running,
the backend waits for that call. If verified progress exists but steps remain, one additional
OpenClaw turn requests only missing steps. There is no direct-provider fallback and no
continuation for prose-only success or a recorded tool error. Agent orchestration may therefore
consume one extra free-tier turn; total work remains bounded by the action deadline.

Sectioned live observations on generated fictional samples:
- English: two sections (before trailing-space paragraph splitter correction), 57.02 seconds
  of audio, 129 transcript words; full generation/check took 142.38 seconds.
- Tamil: three sections, 89.13 seconds of audio, 151 transcript words; full generation/check
  took 839.80 seconds. Existing localizer timeouts and native rewrite calls increased latency.
- Both were reverified after restart with final manifest/combined-WAV verification and
  authenticated source routes. Verification-only timing is not generation latency.
The checker now writes verification-only reports with a -verified suffix, preserving
generation reports. A first concurrent Sinhala attempt returned without the required
completed tools and was marked failed; it is not counted as successful validation.

For navigation evaluation, the completed sectioned result includes a Show section navigation
and source view checkbox. Disabling it displays the same full transcript and WAV in a
single-player view. This controls content differences and requires no new model/TTS call.
The original Single audio mode remains a separate generation baseline.

Prepared-audio retry: a partial sectioned job with a fully prepared target-language transcript
shows Retry audio using prepared transcript. A new owner-bound ticket rechecks source/hash,
reuses scripts and valid cached section WAVs, and invokes the same OpenClaw tool sequence.
No source generation/localization is repeated. Changed sources, wrong-language scripts,
other owners and completed jobs are rejected. Gateway HTTP errors now wait for active bridge
work before deciding completion/continuation. Tool metadata explicitly returns next_tool and
completed_tools to discourage repeated summary requests; no content is sent to Gemini.
The generated-sample checker supports --retry-latest-sample and requires exact fictional
sample bytes before any resumed live call. Free-tier Gateway errors can still yield partial jobs.

Sinhala recovery validation: the original prepared-script job was partial after Gateway
interaction failure (repeated cached summarize calls); the existing TTS service did return
audio, so this was not reported as a confirmed speech-service failure. After the recovery
fixes, a new ticket reused the exact fictional source and prepared native scripts through
OpenClaw. It completed three sections, a 65.97-second WAV (2,909,388 bytes), and a 125-word
transcript. Resume/check took 115.23 seconds; this excludes original preparation time and
is not end-to-end generation latency. Source passages/timings, manifest, downloaded TXT
and WAV were verified. One repeated create_revision_audio call reused the existing audio.
All three languages now have structurally verified live outputs, while pronunciation,
semantic support and browser navigation usability remain manual/human-review checks.
Final frontend production build and TypeScript checking pass; 64 action tests plus the
16 selected related regressions pass. No student-study results are claimed.
