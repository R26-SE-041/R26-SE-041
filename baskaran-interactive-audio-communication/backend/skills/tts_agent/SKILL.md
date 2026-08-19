---
name: tts-agent
description: >
  Text-to-Speech agent skill for VoiceLearn AI.
  Synthesizes localized answers to audio (WAV) using Facebook MMS-TTS
  on Modal serverless GPU. Uploads to Supabase Storage and returns a
  signed URL. Triggered when dealing with audio generation, MMS-TTS
  language codes, or Supabase Storage upload issues.
---

# TTS Agent — Facebook MMS-TTS

## Overview

Converts the localized answer text into speech audio (WAV format),
uploads it to Supabase Storage, and returns a signed URL (1-hour TTL).

**Model:** facebook/mms-tts-{lang}  
**Hosting:** Modal serverless, GPU T4  
**Storage:** Supabase Storage bucket `audio`  
**URL TTL:** 3600 seconds (1 hour)

---

## Key Files

| File | Role |
|---|---|
| `backend/modal_endpoints/tts.py` | Modal endpoint — MMS-TTS model + WAV synthesis |
| `backend/app/agents/tts_agent.py` | LangGraph node — calls Modal + uploads audio |
| `backend/app/services/modal_client.py` | `call_tts()` — HTTP POST, returns raw WAV bytes |
| `backend/app/services/storage.py` | `upload_audio()` — Supabase Storage upload |

---

## State Contract

| Key | Direction | Type | Description |
|---|---|---|---|
| `localized_answer` | IN | `str` | Text to synthesize (fallback: `answer`) |
| `language` | IN | `str` | Language for MMS-TTS voice selection |
| `session_id` | IN | `str` | Storage path prefix |
| `audio_url` | OUT | `str \| None` | Signed Supabase Storage URL (1hr TTL) |

> If text is empty or TTS fails, `audio_url` is `None` (graceful degradation).

---

## MMS-TTS Language Codes

| User Mode | MMS-TTS Code | Notes |
|---|---|---|
| `english` | `eng` | English voice |
| `tamil` | `tam` | Tamil voice |
| `sinhala` | `sin` | Sinhala voice |
| `mixed` | `eng` | Text is already localized — use English voice |

---

## Supabase Storage Path

```
audio/{session_id}/{timestamp}.wav
```

Signed URL is generated immediately after upload with 3600s TTL.

---

## Deployment

```bash
modal deploy backend/modal_endpoints/tts.py
```

Set the printed URL as `MODAL_TTS_URL` in `backend/.env`.

---

## Common Issues

| Symptom | Cause | Fix |
|---|---|---|
| `audio_url` is `None` | `RuntimeError` from missing URL | Deploy Modal endpoint + set `MODAL_TTS_URL` |
| `audio_url` is `None` | Supabase bucket `audio` doesn't exist | Run `run_migrations()` or create bucket manually |
| Signed URL expires | 1hr TTL | Re-invoke pipeline or increase TTL in `tts_agent.py` |
| Wrong voice / gibberish | Wrong MMS language code | Check MMS_LANG mapping in `tts.py` |

---

## Graceful Degradation

The TTS node wraps everything in `try/except RuntimeError`:

```python
try:
    audio_bytes = await call_tts(text, language)
    ...
    audio_url = result["signedURL"]
except RuntimeError as e:
    logger.warning("TTS skipped: %s", e)
    audio_url = None      # pipeline continues without audio
```

The app still returns a valid text answer even without audio.

---

## LangGraph Position

```
START → stt → prompt_enhancer → rag → localization → [tts] → END
```

Input: `localized_answer` from Localization agent  
Output: `audio_url` — the final pipeline output
