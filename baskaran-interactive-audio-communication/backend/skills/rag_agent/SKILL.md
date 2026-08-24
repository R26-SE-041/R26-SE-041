---
name: rag-agent
description: >
  RAG (Retrieval-Augmented Generation) agent skill for VoiceLearn AI.
  Retrieves relevant chunks from ChromaDB and generates grounded answers
  using Qwen2.5-7B-Instruct on Modal serverless GPU (A10G).
  Triggered when dealing with document retrieval, answer generation,
  ChromaDB queries, or RAG pipeline issues.
---

# RAG Agent — Qwen2.5-7B-Instruct + ChromaDB

## Overview

Two-step retrieval + generation:
1. **Embed** the enhanced query (local CPU, `all-MiniLM-L6-v2`)
2. **Retrieve** top-5 relevant chunks from ChromaDB (user-scoped, cosine similarity)
3. **Generate** a grounded answer using Qwen2.5-7B-Instruct — restricted to retrieved context only

**Model:** Qwen/Qwen2.5-7B-Instruct  
**Hosting:** Modal serverless, GPU A10G  
**Parameters:** 8 B  
**Vector Store:** ChromaDB (local, cosine similarity)  
**Embeddings:** `all-MiniLM-L6-v2` (384-dim, sentence-transformers)

---

## Key Files

| File | Role |
|---|---|
| `backend/modal_endpoints/rag_generator.py` | Modal endpoint — Llama model + generate |
| `backend/app/agents/rag_agent.py` | LangGraph node — retrieval + generation |
| `backend/app/services/modal_client.py` | `call_rag_generator()` — HTTP POST |
| `backend/app/services/ingestion.py` | `query_chunks()` — ChromaDB query |

---

## State Contract

| Key | Direction | Type | Description |
|---|---|---|---|
| `enhanced_query` | IN | `str` | Retrieval query (fallback: `transcript`) |
| `user_id` | IN | `str` | For user-scoped ChromaDB collection |
| `language` | IN | `str` | Answer language hint |
| `chunks` | OUT | `list[dict]` | Retrieved context chunks + scores |
| `answer` | OUT | `str` | Generated answer grounded in retrieved context |

---

## Grounding Constraint

System prompt enforced in `rag_generator.py`:

```
Answer ONLY from the provided context.
If the answer is not in the context, say "I couldn't find that in your documents."
Do not use any external knowledge.
```

---

## ChromaDB Retrieval

```python
# ingestion.py
chunks = await query_chunks(query, user_id, n_results=5)
# Returns: [{ "text": str, "metadata": dict, "score": float }]
```

User-scoped: each user has their own ChromaDB collection → no cross-user leakage.

---

## Deployment

```bash
modal deploy backend/modal_endpoints/rag_generator.py
```

Set the printed URL as `MODAL_RAG_GENERATOR_URL` in `backend/.env`.

---

## Common Issues

| Symptom | Cause | Fix |
|---|---|---|
| `"upload documents first"` response | No chunks in ChromaDB for this user | Upload documents via `/api/v1/documents/upload` |
| Hallucinated answer | System prompt not enforced | Check `rag_generator.py` system prompt |
| Low-quality retrieval | Query not enhanced (prompt agent fallback) | Fix prompt enhancer (see `prompt_agent` skill) |
| `RuntimeError: MODAL_RAG_GENERATOR_URL not set` | `.env` missing URL | Deploy endpoint and add URL |

---

## LangGraph Position

```
START → stt → prompt_enhancer → [rag] → localization → tts → END
```

Input: `enhanced_query` from Prompt Enhancement agent  
Output: `chunks` + `answer` consumed by Localization agent
