---
name: adaptive_quiz_generation
description: >
  Adaptive quiz generation from uploaded study documents using RAG, 
  LangGraph multi-agent workflow, and Qwen2.5-7B on Modal.com. 
  Generates MCQ/structured/essay questions grounded in student-uploaded material,
  with difficulty adapting based on student performance using IRT principles.
---

# Adaptive Quiz Generation Skill

## Overview

This skill enables the agent to:
1. **Ingest** uploaded documents (PDF, DOCX, PPTX, TXT) into a ChromaDB vector store
2. **Extract** key topics and build a concept hierarchy from the material
3. **Generate** contextually grounded questions at appropriate Bloom's taxonomy levels
4. **Adapt** question difficulty in real-time based on student answer patterns
5. **Evaluate** answers and provide targeted feedback

## Architecture

```
Upload → IngestionAgent → KnowledgeAgent → QuizAgent → EvaluationAgent
                                                ↑              ↓
                                          AdaptiveAgent ←──────┘
                                                ↓
                                      RecommendationAgent → AnalyticsAgent
```

## Key Components

### 1. RAG Pipeline
- **Chunking**: 800-char overlapping chunks (150-char overlap) from uploaded docs
- **Embedding**: `sentence-transformers/all-MiniLM-L6-v2` (384-dim, local, free)
- **Vector Store**: ChromaDB with cosine similarity indexing
- **Retrieval**: Top-4 chunks per question topic

### 2. Qwen2.5-7B (Modal.com)
- Model: `Qwen/Qwen2.5-7B-Instruct`
- Hosting: Modal.com serverless GPU (A10G, 24GB VRAM)
- Inference: vLLM for fast generation
- Call: HTTP POST to Modal web endpoint
- Cold start: ~30s | Warm: ~3-5s per question

### 3. Question Generation (QuizAgent)
- Distributes questions proportionally across extracted topics
- Maps difficulty score → Bloom's level:
  - 0.0–0.33: easy → "remember"
  - 0.33–0.66: medium → "apply"  
  - 0.66–1.0: hard → "analyze"
- Verifies grounding score (cosine sim) ≥ 0.55 before accepting question
- Retries with expanded context if grounding check fails

### 4. Adaptive Difficulty (AdaptiveAgent)
- Adjusts difficulty after each answered question
- Correct answer: difficulty += 0.1 (harder)
- Wrong answer: difficulty -= 0.1 (easier)
- Clamped to [0.1, 0.95]

## Prompts

### MCQ Generation Template
```
Use ONLY the following context from the student's uploaded material.
Context: {context}
Generate a {bloom_level}-level MCQ about "{topic}".
Return ONLY valid JSON: {"question", "options": {A,B,C,D}, "correct_answer", "explanation"}

Rules:
- Phrase the question directly as a real-world concept. Do NOT refer to "the context", "the document", "the text", "the uploaded material", or "the page".
```

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/v1/session/start` | Upload docs + create session |
| GET | `/api/v1/session/{id}/status` | Poll for ready status |
| GET | `/api/v1/quiz/{id}/question` | Get current question |
| POST | `/api/v1/quiz/{id}/answer` | Submit answer |
| GET | `/api/v1/analytics/{id}/report` | Get final report |

## Research Metrics (for MSc paper)

- **Grounding Score**: Cosine similarity between question embedding and source chunks
- **Difficulty Adaptation Rate**: Change in difficulty per correct/incorrect answer  
- **Bloom's Coverage**: Distribution of questions across taxonomy levels
- **Topic Coverage**: % of detected topics covered in quiz

## Usage Example

```python
# 1. Start session (multipart form)
resp = requests.post("/api/v1/session/start", 
    files={"files": open("lecture.pdf", "rb")},
    data={"exam_type": "mcq", "num_questions": 10, "difficulty_mode": "adaptive"}
)
session_id = resp.json()["session_id"]

# 2. Poll until ready
while True:
    status = requests.get(f"/api/v1/session/{session_id}/status").json()
    if status["status"] == "ready":
        break

# 3. Take quiz
question = requests.get(f"/api/v1/quiz/{session_id}/question").json()
result = requests.post(f"/api/v1/quiz/{session_id}/answer",
    json={"answer": "B", "time_taken_sec": 45}
).json()
```

## Troubleshooting Guide

When debugging this application, look out for these common issues:

1. **"ModuleNotFoundError: sentence_transformers" or similar in logs:**
   - Usually caused by running the FastAPI backend outside of the Python virtual environment.
   - **Fix:** Always ensure the server is started with the venv python (e.g., `.\venv\Scripts\uvicorn.exe app.main:app --reload --port 8000`).

2. **Graph hangs in "Processing" but /health is OK:**
   - Check if `knowledge_agent` is failing. If the state is stored in memory (`MemorySaver`), the status polling endpoint might not see `chunk_count` or `topics_detected` if the backend relies on an ephemeral graph state instead of SQLite.
   - **Fix:** Ensure topics and chunks are explicitly persisted to the SQLite DB `sessions` table (using `update_session_progress`) before setting status to `ready`.

3. **ZeroDivisionError in QuizAgent:**
   - Occurs if `knowledge_agent` fails to extract any topics (e.g., empty file uploaded) and routes to `quiz_agent` with an empty `topics` list.
   - **Fix:** Implement fallback logic (`topics = state.get("topics", []) or ["General"]`) and ensure conditional graph edges properly route to `error_handler` on ingestion/knowledge failures.

4. **Modal Endpoint 401 Unauthorized:**
   - If `MODAL_API_KEY` is set to a placeholder like `"your-api-key"` in `.env`, passing it as a `Bearer` token can cause Modal API failures.
   - **Fix:** Only send the `Authorization` header if the token exists AND is not the placeholder.

5. **Timeout on Knowledge Extraction:**
   - Qwen takes ~40s to cold start. The `knowledge_agent` sends a large prompt containing chunked document text, which can take an additional ~30s for inference.
   - **Fix:** Keep the `httpx.Client` timeout for the Modal inference endpoint at `90.0` seconds minimum. Set `scaledown_window=360` (6 mins) in `qwen_endpoint.py` to keep it warm.
