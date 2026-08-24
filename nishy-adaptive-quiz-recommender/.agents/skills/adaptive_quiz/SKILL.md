---
name: adaptive_quiz_generation
description: >
  Adaptive quiz generation from uploaded study documents using RAG, 
  LangGraph multi-agent workflow, and Qwen2.5-7B on Modal.com.
  Generates varied, non-repeating MCQ/structured/essay questions grounded 
  in student-uploaded material, with 3-level progressive hint system,
  difficulty adapting based on student performance using IRT principles.
  Designed for A+ grade preparation with Socratic hint-based learning.
---

# Adaptive Quiz Generation Skill

## Overview

This skill enables the agent to produce **exam-ready, A+ quality adaptive quizzes** from student-uploaded study material. The system is designed around the principle that a student who struggles should learn — not fail — through a progressive 3-level hint system before being shown the answer.

```
Upload → IngestionAgent → KnowledgeAgent → QuizAgent → EvaluationAgent
                                                ↑              ↓
                                          AdaptiveAgent ←──────┘
                                                ↓
                                      RecommendationAgent → AnalyticsAgent
```

---

## Quiz Generation — When and How

### Session Start Flow

1. Student uploads documents → `IngestionAgent` chunks them → `KnowledgeAgent` extracts topics
2. `QuizAgent` builds a **randomized blueprint** of `N` questions distributed across topics
3. All `N` questions are pre-generated and stored in graph state before the quiz begins
4. API returns `status: "ready"` when all questions are prepared

### Blueprint Randomization (Anti-Repeat Strategy)

Every quiz session generates **different questions**, even on the same material. Three layers of randomization:

| Layer | Mechanism |
|-------|-----------|
| **Topic order** | `random.shuffle(topics)` before distributing questions |
| **Blueprint shuffle** | Final `random.shuffle(blueprint)` mixes topic clusters |
| **RAG query variation** | Random seed word appended to each retrieval query (e.g. "comparison", "mechanism", "advantage") |
| **LLM temperature** | `0.5 + random.uniform(0.0, 0.15)` for varied generation |
| **No-repeat injection** | All previously generated questions are injected into the prompt as "DO NOT repeat" |

### Question Quality Rules

The MCQ prompt enforces these quality constraints:

```
Rules for MCQ generation:
1. ALL 4 options must be plausible — no obviously wrong distractors
2. Question must test a specific concept from the context (not general knowledge)
3. Do NOT repeat or paraphrase any question already in this quiz
4. Phrase as real-world concept — do NOT mention "the context", "the document", or "the text"
5. Include one correct answer and three well-crafted distractors at the same conceptual level
```

### Difficulty Mapping → Bloom's Taxonomy

| Difficulty Score | Label | Bloom's Level | What it tests |
|-----------------|-------|---------------|---------------|
| 0.0 – 0.33 | Easy | `remember` | Recall of definitions, facts |
| 0.33 – 0.66 | Medium | `apply` | Application, problem-solving |
| 0.66 – 1.0 | Hard | `analyze` | Analysis, comparison, evaluation |

Initial difficulty is set by the student's chosen mode (`easy=0.2`, `medium=0.5`, `hard=0.8`, `adaptive=0.5`).

### Adaptive Difficulty Adjustment (IRT-inspired)

After each answer, `AdaptiveAgent` updates the difficulty:

| Outcome | Delta | Reasoning |
|---------|-------|-----------|
| Correct, 1st attempt, no hints | +0.10 | Perfect performance |
| Correct, 1st attempt, used hints | +0.07 | Needed guidance |
| Correct, after retries | +0.04 | Eventually got it |
| Wrong, significant struggle (hints ≥ 2) | -0.15 | Major difficulty |
| Wrong, simply incorrect | -0.10 | Standard backoff |
| Fast correct answer (70% of avg time) | ×1.2 bonus | Confidence multiplier |

Difficulty is clamped to `[0.0, 1.0]`.

---

## 3-Level Progressive Hint System (A+ Learning Design)

The hint system follows a **Socratic pedagogy**: never give away the answer — guide the student to reason it out.

### Attempt 1 — Wrong → Level 1 Hint (Hard / Conceptual Clue)
- **Goal**: Force the student to think
- **What it does**: Asks a guiding question or provides a conceptual clue about the underlying topic
- **What it does NOT do**: Never reveals A/B/C/D or the specific answer
- **Prompt instruction**: "Be challenging — make them think. 2-3 sentences."

### Attempt 2 — Wrong → Level 2 Hint (Medium / Focused Explanation)
- **Goal**: Bridge the knowledge gap
- **What it does**: Explains the relevant concept/mechanism at moderate depth, referencing a specific term or principle from the uploaded material
- **What it does NOT do**: Never reveals the option letter
- **Prompt instruction**: "Be more direct — they're struggling. 3-4 sentences."

### Attempt 3 — Wrong → Level 3 Hint (Near-Direct / Concept Walkthrough)
- **Goal**: Ensure learning before moving on
- **What it does**: Walks through the concept step-by-step so the student understands WHY the answer is correct
- **What it does NOT do**: Still doesn't say "the answer is B" — teaches the concept
- **Prompt instruction**: "Teaching moment — 4-6 sentences. Explain thoroughly."

### Attempt 4+ — Reveal Answer
- Reveals the correct option letter and full model explanation
- Format: `"❌ The correct answer is **{letter}**. {model_answer}"`

### Hint Generation Architecture

```python
chunks = rag.retrieve(collection_id, question["topic"], k=3)
context = "\n\n".join([c["text"] for c in chunks])
prompt = HINT_PROMPTS[hint_level].format(
    context=context,
    question=question["question"],
    topic=question["topic"]
)
hint = llm.call(prompt, temperature=0.3)  # Low temp for consistent, accurate hints
```

---

## Question Types

### MCQ (Multiple Choice) — Rule-based evaluation
- 4 options: A, B, C, D — all plausible
- Evaluated by exact string match (case-insensitive)
- 3-attempt retry with progressive hints
- Score: 1.0 correct, 0.0 incorrect

### Structured — LLM rubric evaluation
- Open-ended answer with model answer and marks breakdown
- Marks breakdown: `{content: 40, accuracy: 30, terminology: 20, examples: 10}`
- Partial marks awarded (minimum 0.2 if any correct point made)
- Single attempt (no retries for structured/essay)

### Essay — Holistic LLM evaluation
- Rubric: `{accuracy: 30, completeness: 25, structure: 20, terminology: 15, critical_thinking: 10}`
- Score ≥ 0.5 = correct

---

## RAG Pipeline

| Component | Detail |
|-----------|--------|
| Chunking | 800-char chunks, 150-char overlap |
| Embedding | `sentence-transformers/all-MiniLM-L6-v2` (384-dim, local) |
| Vector Store | ChromaDB (cosine similarity) |
| Retrieval | `k=4` chunks per question, `k=3` for hints |
| Grounding threshold | ≥ 0.55 cosine similarity required |
| Retry on low grounding | Re-retrieves with `k=5` and retries generation |

### Grounding Check
Every generated question is scored against its source chunks. If `grounding_score < 0.55`, the question is flagged with `⚠ Low grounding` in the UI and regeneration is attempted once.

---

## API Reference

| Method | Path | Purpose |
|--------|------|---------| 
| POST | `/api/v1/session/start` | Create session with document_ids + config |
| GET | `/api/v1/session/{id}/status` | Poll: `processing` → `ready` → `error` |
| GET | `/api/v1/quiz/{id}/question` | Get current question (by current_q_index) |
| POST | `/api/v1/quiz/{id}/answer` | Submit answer → evaluation + adaptive update |
| GET | `/api/v1/analytics/{id}/report` | Final performance report |

### Submit Answer Request
```json
{
  "answer": "B",
  "time_taken_sec": 12
}
```
Note: `q_id` is optional — the backend resolves the current question from session state.

### Submit Answer Response
```json
{
  "is_correct": false,
  "score": 0.0,
  "feedback": "❌ Incorrect. [full feedback]",
  "hint": "[clean hint text for frontend display]",
  "hints_used": 1,
  "attempts": 1,
  "next_question_available": true,
  "quiz_complete": false
}
```

---

## Frontend Navigation

The quiz page provides three navigation elements:

| Element | Behaviour |
|---------|-----------|
| **← Prev** button | Visible but disabled for adaptive quizzes (can't go back — each question adapts to previous answer) |
| **Submit Answer →** button | Active when option selected; disabled while submitting |
| **Next →** button | Active only after an answer is submitted and correct / all 3 attempts used |

### Feedback Overlay Behaviour

| Outcome | Overlay shows |
|---------|--------------|
| ✅ Correct | Green panel with full explanation |
| 💡 Wrong (attempt 1,2,3) | Amber panel with level badge + hint text |
| ❌ Wrong (all attempts used) | Red panel with full answer reveal |

---

## Research Metrics

| Metric | Description |
|--------|-------------|
| `grounding_score` | Cosine sim between question embedding and source chunks |
| `difficulty_progression` | Array of difficulty values across the quiz |
| `bloom_coverage` | Distribution across taxonomy levels |
| `topic_coverage` | % of detected topics covered |
| `hints_used` | Total hints across all questions |
| `avg_time_per_question` | Engagement metric |

---

## Troubleshooting

### 1. `q_id` validation error in `/answer`
- **Cause**: Frontend not sending `q_id` in request body
- **Fix**: `q_id` is now `Optional` in `SubmitAnswerRequest` — backend uses `current_q_index` from state

### 2. Same questions repeating across sessions
- **Cause**: Blueprint was built with fixed topic order, fixed temperature
- **Fix**: Topics shuffled, blueprint shuffled, RAG query varied, temperature randomized, previously generated questions injected as "do not repeat"

### 3. Graph hangs in "Processing"
- **Fix**: Ensure topics + chunk_count are persisted to SQLite before status → `ready`
- Check `update_session_progress()` is called after graph completes

### 4. ZeroDivisionError in QuizAgent
- **Fix**: `topics = state.get("topics", []) or ["General"]` — fallback handles empty topics

### 5. Modal Endpoint 401 Unauthorized
- **Fix**: Only send `Authorization` header if `MODAL_API_KEY` exists and is not the placeholder `"your-api-key"`

### 6. Cold start timeouts
- `httpx.Client` timeout must be ≥ 90 seconds for Modal cold start (~30s) + inference (~30s)
- Set `scaledown_window=360` in `qwen_endpoint.py` to keep GPU warm for 6 minutes

### 7. Hint text not showing in frontend
- **Fix**: Check `result.hint` field in `SubmitAnswerResponse` — it's extracted from `feedback` string after `"❌ Incorrect. "` prefix
