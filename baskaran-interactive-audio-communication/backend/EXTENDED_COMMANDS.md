# Extended audio and revision commands

Use the Document actions panel's **All supported commands** list to fill the command
field, then select **Run action**. Recognized voice transcripts use the same parser.
The existing four commands remain available.
Voice command language and output language are separate: keep English command
recognition selected for the new English phrases, including when listening to a Tamil
or Sinhala revision. The existing four native-language command examples remain available.

**Execution mode** defaults to the configured provider. OpenClaw agent uses Gateway/MCP.
Direct backend explicitly runs the same ordered generation/save tools without the
Gateway agent; choose it when the Gateway or its model quota is unavailable. Modes
never switch automatically. Playback stays local in either mode. Recoverable tool
order errors return `next_tool` without poisoning a valid ticket; traces are deduplicated.

## Generation

| Exact command | Behavior |
| --- | --- |
| Create an audio revision of this section only and save it | Open a sectioned revision and select its source section. Generate one section from that verified original passage. |
| Create a one-minute audio revision and save it | Target about 60 seconds with a concise single-audio script. Display target and actual WAV duration. Duration is approximate; audio is never truncated to force the target. |
| Create a detailed audio revision and save it | Request 400–500 words for single audio or up to 160 words per section. Short sources should not be padded with invented facts. |
| Create an audio revision in Tamil and save it | Override output language with Tamil; reuse localization and Tamil TTS. |
| Create an audio revision in Sinhala and save it | Override output language with Sinhala; reuse localization and Sinhala TTS. |
| Create an audio revision in English and save it | Override output language with English; reuse English TTS. |
| Create flashcards from this document and save them | Save revision cards with question, answer and exact source quote. Flip answers in the UI; download JSON. No grading or adaptive recommendations. |

OpenClaw audio workflows retain the existing three tools. Flashcards add
`create_flashcards` and `save_flashcards`; both must execute and saved files must
verify before completion. The MCP filter must include all six production tools.
Flashcards validate structure, length, duplicate questions and source IDs. Source passages
and offsets are selected by the backend, never invented by the model. This does not
prove semantic correctness automatically. Source passages retain their original language.
Section-only generation checks ownership, document identity, source hash and offsets.

## Playback

These operate directly on loaded revision audio without an LLM call:

- Play the audio
- Pause the audio
- Resume the audio
- Stop the audio
- Play the next section
- Play the previous section
- Replay this section
- Play section two (also accepts one, three, or numeric section numbers)
- Skip forward ten seconds
- Go back ten seconds
- Set playback speed to 0.75
- Set playback speed to 1.25

Stop pauses and resets to the beginning. Resume preserves position. Play restarts
ended audio. Replay stops at the section end. Section commands require section
timings. Seeking is clamped to duration; absent sections produce visible errors.

## Saved results and deletion

**Saved revisions and flashcards** lists owned records after page refresh. Open loads
existing outputs without regeneration. The default artifact folder is
`backend/local_actions/files`; tickets are in `actions.sqlite3`.

**Delete this saved revision** opens Cancel / Confirm delete for the current saved
result. Library rows also have Delete. The backend rejects unconfirmed, foreign-owned,
or unfinished requests. Only validated server-generated artifact IDs under `files/`
can be removed. Shared files remain; the uploaded document remains.

API: `GET /api/v1/actions/saved`; `DELETE /api/v1/actions/{id}` with
`{"confirmed": true}`. Source-only submission adds `source_action_id` and `section_id`.
Flashcard downloads use the existing `/download` endpoint with JSON content type.

## Checks

From backend: `python -m pytest tests/test_document_actions.py -q` and
`python check_mcp_adapter.py`. For an opt-in real-service check, run
`python check_extended_commands.py --document-id <local-document-id>`.
It requires a saved sectioned revision for that document and records metadata-only
evidence in `.actions-runtime/extended-command-check-<provider>.json`.
Use `--provider direct` to verify the real generation pipeline independently of Gateway
availability; that is not evidence of OpenClaw agent orchestration.

From frontend: `node --test tests/audioCommands.test.mjs` (Node 24) and
`npm run type-check`.

Validation on 12 October 2026: 82 backend action tests and four playback test groups
pass, covering the 12 requested playback phrases. Type-check and the study page's
HTTP response pass. Real Direct backend checks saved and downloaded all seven new
generation outputs, including six flashcards and one source-linked section-only
revision. OpenClaw live checks passed one-minute and detailed revision before Gemini
returned quota errors; the remaining new workflows could not be verified through
that agent. MCP discovery verifies all six tools. Browser interaction and microphone
recognition were not automated in this check.
