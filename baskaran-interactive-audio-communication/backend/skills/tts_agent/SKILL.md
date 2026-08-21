---
name: tts-agent
description: >
  Text-to-Speech agent skill for VoiceLearn AI. Routes English to Kokoro-82M,
  Tamil to Indic Parler-TTS, and Sinhala to SinhalaVITS, then uploads WAV audio
  to Supabase Storage and returns a signed URL.
---

# TTS Agent

## Routing

| Language | Model | Endpoint |
|---|---|---|
| English | `hexgrad/Kokoro-82M` | `modal_endpoints/english_kokoro_tts.py` |
| Tamil | `ai4bharat/indic-parler-tts` | `modal_endpoints/indic_parler_mixed_tts.py` |
| Sinhala | `dialoglk/SinhalaVITS-TTS-F1` | `modal_endpoints/sinhala_vits_tts.py` |

English TTS must always use `call_english_tts()` and Kokoro-82M. The legacy
generic MMS-TTS caller is not part of the final language routing.

## English Kokoro contract

Request:

```json
{"text": "Answer text", "voice": "af_heart", "speed": 1.0}
```

Response: 24 kHz, 16-bit PCM `audio/wav`.

Configuration:

```dotenv
USE_ENGLISH_TTS=true
MODAL_ENGLISH_KOKORO_TTS_URL=<EnglishKokoroTTS.synthesize URL>
ENGLISH_TTS_VOICE=af_heart
ENGLISH_TTS_SPEED=1.0
```

Deploy with:

```bash
modal deploy backend/modal_endpoints/english_kokoro_tts.py
```

## State contract

| Key | Direction | Type | Description |
|---|---|---|---|
| `localized_answer` | IN | `str` | Text to synthesize; falls back to `answer` |
| `language` | IN | `str` | `english`, `tamil`, or `sinhala` |
| `session_id` | IN | `str` | Storage path prefix |
| `audio_url` | OUT | `str \| None` | Signed Supabase audio URL |

If synthesis fails, the text answer remains available and `audio_url` is
`None`. Successful WAV output is uploaded through `services/storage.py`.
