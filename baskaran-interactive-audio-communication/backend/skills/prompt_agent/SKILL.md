---
name: prompt-enhancement-agent
description: >
  Prompt Enhancement agent skill for VoiceLearn AI.
  Rewrites raw Whisper transcripts into clear, retrieval-optimized
  academic queries using Qwen2.5-3B-Instruct on Modal serverless GPU.
  Triggered when dealing with prompt enhancement, query optimization,
  or debugging why enhanced_query equals the raw transcript.
---

# Prompt Enhancement Agent — Qwen2.5-3B-Instruct

## Overview

Converts noisy, spoken-language transcripts into clean, structured
academic queries suitable for ChromaDB vector retrieval.

**Model:** Qwen/Qwen2.5-3B-Instruct  
**Hosting:** Modal serverless, GPU T4  
**Parameters:** 3 B  
**Timeout:** 120 s (cold T4 model load can take 60–90 s)  
**Decode strategy:** Greedy (`do_sample=False`) — deterministic, no hallucinations

---

## Key Files

| File | Role |
|---|---|
| `backend/modal_endpoints/prompt_enhancer.py` | Modal endpoint — model + enhance logic |
| `backend/app/agents/prompt_agent.py` | LangGraph node — calls Modal, updates state |
| `backend/app/services/modal_client.py` | `call_prompt_enhancer()` — HTTP POST |

---

## State Contract

| Key | Direction | Type | Description |
|---|---|---|---|
| `transcript` | IN | `str` | Raw Whisper output |
| `language` | IN | `str` | Language mode for context |
| `enhanced_query` | OUT | `str` | Retrieval-optimized query |

> **Fallback:** If `MODAL_PROMPT_ENHANCER_URL` is unset **or** the call fails,
> `enhanced_query` is set to the original `transcript` unchanged.

---

## System Prompt

```
You are an academic query optimizer.
Rewrite the student's question into a clear, specific, retrieval-optimized query.
Keep the same language as the input. Return ONLY the rewritten query, nothing else.
```

---

## Modal Endpoint Details

```python
# prompt_enhancer.py — POST body
class PromptEnhancerRequest(BaseModel):
    query: str
    language: str = "english"
```

**Request:** JSON `{ "query": "...", "language": "english" }`  
**Response:** JSON `{ "enhanced_query": "..." }`

Generation config:
```python
max_new_tokens=150
do_sample=False        # greedy decode — deterministic
pad_token_id=eos_token_id
```

Guard: if model output < 5 chars → returns raw query unchanged.

---

## Deployment

```bash
modal deploy backend/modal_endpoints/prompt_enhancer.py
```

Set the printed URL as `MODAL_PROMPT_ENHANCER_URL` in `backend/.env`.

---

## Common Issues

| Symptom | Cause | Fix |
|---|---|---|
| `enhanced_query` == `transcript` (no change) | Cold-start timeout (was 30s, now fixed to 120s) | Redeploy after fixing timeout in `modal_client.py` |
| `enhanced_query` == `transcript` (no change) | `MODAL_PROMPT_ENHANCER_URL` not set in `.env` | Deploy endpoint and add URL to `.env` |
| Model echoes the instruction | Chat template not applied correctly | Verify `apply_chat_template` call in `prompt_enhancer.py` |
| Garbled / very short output | Model not loaded (OOM / CUDA error) | Check Modal logs: `modal logs voicelearn-prompt-enhancer` |

> **Root cause of "prompt enhance not working":**  
> The timeout in `call_prompt_enhancer()` was set to `30.0` seconds — too short
> for a cold T4 container loading a 3B model (takes ~60-90s). This caused silent
> fallback to the raw transcript. **Fixed:** timeout raised to `120.0` seconds.

---

## LangGraph Position

```
START → stt → [prompt_enhancer] → rag → localization → tts → END
```

Input: `transcript` from STT agent  
Output: `enhanced_query` consumed by RAG agent
