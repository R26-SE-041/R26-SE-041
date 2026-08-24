---
name: localization-agent
description: >
  Localization agent skill for VoiceLearn AI.
  Translates and formats English answers into Tamil, Sinhala, or
  Thanglish (mixed) using Qwen2.5-7B-Instruct on Modal serverless GPU.
  Triggered when handling multi-language output, translation quality,
  or localizer endpoint issues.
---

# Localization Agent — Qwen2.5-7B-Instruct

## Overview

Formats/translates the English RAG answer into the user's chosen language.
English mode is a no-op (zero latency, no Modal call).

**Model:** Qwen/Qwen2.5-7B-Instruct  
**Hosting:** Modal serverless, GPU T4  
**Parameters:** 7 B  
**Decode:** Sampling (`temperature=0.3`) — allows natural phrasing

---

## Key Files

| File | Role |
|---|---|
| `backend/modal_endpoints/localizer.py` | Modal endpoint — model + translate |
| `backend/app/agents/localization_agent.py` | LangGraph node — calls Modal, updates state |
| `backend/app/services/modal_client.py` | `call_localizer()` — HTTP POST |

---

## State Contract

| Key | Direction | Type | Description |
|---|---|---|---|
| `answer` | IN | `str` | English answer from RAG agent |
| `language` | IN | `str` | Target language mode |
| `localized_answer` | OUT | `str` | Translated/formatted answer |

> **Fallback:** If `MODAL_LOCALIZER_URL` is unset, returns original `answer` unchanged.

---

## Mode Behavior

| Mode | Behavior | Script |
|---|---|---|
| `english` | **No-op** — returns original answer, no Modal call | — |
| `tamil` | Full Tamil translation, technical terms in English | தமிழ் |
| `sinhala` | Full Sinhala translation, technical terms in English | සිංහල |
| `mixed` | Thanglish — Tamil meaning in English script, casual tone | Latin |

---

## System Prompts (per language)

```python
# localizer.py
LANGUAGE_INSTRUCTIONS = {
    "tamil":   "Translate the following academic answer to Tamil (தமிழ்). Keep technical terms in English.",
    "sinhala": "Translate the following academic answer to Sinhala (සිංහල). Keep technical terms in English.",
    "mixed":   "Rewrite the following in Thanglish (mix of Tamil and English, using English script for Tamil words). Keep it natural and conversational.",
}
```

---

## Important: Image Base

> ⚠️ **localizer.py** uses `modal.Image.debian_slim` (no CUDA base).  
> If GPU inference fails with CUDA errors, switch to:
> ```python
> modal.Image.from_registry("nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04", add_python="3.11")
> ```
> (same base as `whisper_stt.py` and `prompt_enhancer.py`)

---

## Deployment

```bash
modal deploy backend/modal_endpoints/localizer.py
```

Set the printed URL as `MODAL_LOCALIZER_URL` in `backend/.env`.

---

## Common Issues

| Symptom | Cause | Fix |
|---|---|---|
| Translation returns English unchanged | `language == "english"` → correct behavior | Expected — no-op |
| Translation returns English unchanged | `MODAL_LOCALIZER_URL` not set | Deploy and add URL to `.env` |
| CUDA errors on T4 | `debian_slim` missing CUDA libs | Switch to `nvidia/cuda` base image |
| Unnatural translation | `temperature=0.3` too low | Increase to `0.5` for more fluent output |

---

## LangGraph Position

```
START → stt → prompt_enhancer → rag → [localization] → tts → END
```

Input: `answer` from RAG agent  
Output: `localized_answer` consumed by TTS agent
