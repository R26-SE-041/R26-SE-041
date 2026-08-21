---
name: voicelearn-agents
description: >
  Master skills index for VoiceLearn AI LangGraph pipeline.
  References all individual agent skills. Use this as a navigation
  guide — each agent has its own dedicated SKILL.md for full details.
---

# VoiceLearn AI — Agent Skills Index

## Pipeline Overview

```
Audio Input
    ↓
[STT Agent]               — Whisper Large V3 on Modal (T4)
    ↓
[Prompt Enhancement]      — Qwen2.5-3B-Instruct on Modal (T4)
    ↓
[RAG Agent]               — ChromaDB + Qwen2.5-7B-Instruct on Modal (A10G)
    ↓
[Localization Agent]      — Qwen2.5-7B-Instruct on Modal (T4)
    ↓
[TTS Agent]               — Language-specific TTS + Supabase Storage
    ↓
Text + Audio Response
```

---

## Individual Agent Skills

> Each agent has its own `SKILL.md` with full state contract, endpoint
> details, deployment steps, and troubleshooting guide.

| Agent | Skill File | Model | GPU |
|---|---|---|---|
| STT | [`skills/stt_agent/SKILL.md`](./stt_agent/SKILL.md) | Whisper Large V3 | T4 |
| Prompt Enhancement | [`skills/prompt_agent/SKILL.md`](./prompt_agent/SKILL.md) | Qwen2.5-3B-Instruct | T4 |
| RAG Generation | [`skills/rag_agent/SKILL.md`](./rag_agent/SKILL.md) | Qwen2.5-7B-Instruct | A10G |
| Localization | [`skills/localization_agent/SKILL.md`](./localization_agent/SKILL.md) | Qwen2.5-7B-Instruct | T4 |
| TTS | [`skills/tts_agent/SKILL.md`](./tts_agent/SKILL.md) | Kokoro / Indic Parler / SinhalaVITS | CPU / A10G / T4 |

---

## LangGraph Topology

### Full Pipeline (`orchestrator.build_graph`)
```
START → stt → prompt_enhancer → rag → localization → tts → END
```

### Phase 1 — STT Only (`orchestrator.build_stt_only_graph`)
```
START → stt → END
```

---

## Adding a New Agent

1. Create `app/agents/<name>_agent.py` — `async def <name>_node(state: dict) -> dict`
2. Create `modal_endpoints/<name>.py` — Modal app + endpoint class
3. Add `call_<name>()` in `app/services/modal_client.py`
4. Register node in `app/agents/orchestrator.py`
5. Create `backend/skills/<name>_agent/SKILL.md` using the per-agent format
6. Add entry to the table above in this file

---

## Known Issues & Fixes

| Issue | Root Cause | Status |
|---|---|---|
| `enhanced_query` == raw `transcript` (prompt enhance silent fail) | Timeout was 30s → too short for cold T4 (60-90s load) | ✅ Fixed — raised to 120s in `modal_client.py` |
| Localizer CUDA errors | `debian_slim` base missing CUDA libs | ⚠️ Use `nvidia/cuda:12.1.1` base if needed |
