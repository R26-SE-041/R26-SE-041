---
name: stt-agent
description: >
  Speech-to-Text agent skill for VoiceLearn AI.
  Handles all audio-to-transcript conversion using
  Whisper Large V3 on Modal serverless GPU (T4).
  Triggered when you need to transcribe audio, handle
  language hints, or debug STT pipeline issues.
---

# STT Agent — Whisper Large V3

## Overview

Converts raw audio bytes into a text transcript.
Single responsibility: **audio in → transcript out**.

**Model:** OpenAI Whisper Large V3  
**Backend:** `faster-whisper` (CTranslate2, 4× faster than openai-whisper)  
**Hosting:** Modal serverless, GPU T4  
**Parameters:** 1.5 B  
**Cold-start timeout:** 120 s (set in `modal_client.py`)

---

## Key Files

| File | Role |
|---|---|
| `backend/modal_endpoints/whisper_stt.py` | Modal endpoint — model load + transcribe |
| `backend/app/agents/stt_agent.py` | LangGraph node — calls Modal, updates state |
| `backend/app/services/modal_client.py` | `call_whisper()` — HTTP POST to Modal URL |

---

## State Contract

| Key | Direction | Type | Description |
|---|---|---|---|
| `audio_bytes` | IN | `bytes` | Raw audio data (webm/wav/mp3/ogg) |
| `audio_filename` | IN | `str` | Original filename (format hint for ffmpeg) |
| `language` | IN | `str` | User-selected mode (see Language Mapping) |
| `transcript` | OUT | `str` | Whisper transcription result |
| `detected_language` | OUT | `str` | ISO code e.g. `"ta"`, `"en"`, `"si"` |
| `duration_ms` | OUT | `int` | End-to-end processing time in ms |

---

## Language Mapping

| User Selection | Whisper Code | Behavior |
|---|---|---|
| `english` | `"en"` | Force English decode |
| `tamil` | `"ta"` | Force Tamil decode |
| `sinhala` | `"si"` | Force Sinhala decode |
| `mixed` | `None` | Auto-detect (best for code-switching) |

---

## Modal Endpoint Details

```python
# whisper_stt.py
segments, info = self.model.transcribe(
    tmp_path,
    language=whisper_lang,   # None = auto-detect
    task="transcribe",
    beam_size=5,
    vad_filter=True,         # skips silence → faster + accurate
)
```

**Accepted formats:** `multipart/form-data`
- `audio_file` — raw audio bytes
- `language_hint` — string from LANG_MAP

**Response:**
```json
{
  "transcript": "...",
  "detected_language": "ta",
  "duration_ms": 1234
}
```

---

## Deployment

```bash
modal deploy backend/modal_endpoints/whisper_stt.py
```

Set the printed URL as `MODAL_WHISPER_URL` in `backend/.env`.

---

## Common Issues

| Symptom | Cause | Fix |
|---|---|---|
| Timeout after 120s | Cold-start model download | First deploy → wait for volume cache |
| Empty transcript | Silent audio / VAD filtered everything | Check audio file has actual speech |
| Wrong language detected | `mixed` mode on single-language input | Pass explicit `language_hint` |
| `RuntimeError: MODAL_WHISPER_URL not set` | `.env` missing | Run `modal deploy` and copy URL |

---

## LangGraph Position

```
START → [stt] → prompt_enhancer → rag → localization → tts → END
```

Output `transcript` feeds directly into the Prompt Enhancement Agent.
