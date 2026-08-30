# Adaptive Quiz Generation Platform — Phase 1

**MSc Research | Multi-Agent Adaptive Assessment with RAG + Qwen2.5-7B**

## Architecture

```
quiz-frontend/          Next.js 15 + TypeScript + Tailwind CSS
adaptive-assessment-platform/
├── app/                FastAPI backend
├── agents/             LangGraph multi-agents (7 agents)
├── services/           RAG, LLM, Grounding, DB services
├── graph/              LangGraph StateGraph
├── modal_inference/    Qwen2.5-7B serverless endpoint
└── db/                 ChromaDB + SQLite
```

## Quick Start

### 1. Configure the deployed Nishy Qwen2.5-7B endpoint

```bash
cd adaptive-assessment-platform

# The application uses the already-deployed Nishy fine-tuned endpoint:
# https://nisharahtheva--nishy-qwen-api-generate.modal.run
```

### 2. Configure Backend

```bash
cd adaptive-assessment-platform
cp .env.example .env

# Edit .env:
# MODAL_ENDPOINT_URL=https://nisharahtheva--nishy-qwen-api-generate.modal.run
```

### 3. Install Backend Dependencies

```bash
cd adaptive-assessment-platform

# (Optional) Create virtual environment
python -m venv venv
.\venv\Scripts\activate      # Windows
# source venv/bin/activate   # Mac/Linux

pip install -r requirements.txt

# sentence-transformers model downloads automatically on first run (~90MB)
```

### 4. Run the Backend

```bash
cd adaptive-assessment-platform
uvicorn app.main:app --reload --port 8000

# API docs: http://localhost:8000/docs
# Health:   http://localhost:8000/health
```

### 5. Run the Frontend

```bash
cd quiz-frontend
npm install
npm run dev

# Open: http://localhost:3000
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/session/start` | Upload docs + create session |
| GET | `/api/v1/session/{id}/status` | Poll for ready status |
| GET | `/api/v1/quiz/{id}/question` | Get current question |
| POST | `/api/v1/quiz/{id}/answer` | Submit answer |
| GET | `/api/v1/analytics/{id}/report` | Get analytics report |

## Research Metrics

- **Grounding Score**: Cosine similarity between generated question embedding and source chunks (sentence-transformers)
- **Bloom's Taxonomy Coverage**: Distribution across 6 cognitive levels
- **Adaptive Difficulty Progression**: IRT-based difficulty trajectory per session
- **Topic Coverage**: % of detected topics covered in quiz

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Frontend | Next.js 15, TypeScript, Tailwind CSS |
| Backend | FastAPI, Python 3.11 |
| Agents | LangGraph 0.2.55 |
| LLM | Nishy Qwen2.5-7B fine-tuned model (Modal.com) |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 |
| Vector DB | ChromaDB |
| Session DB | SQLite |

## Phase 1 Scope (Complete)

- [x] Document upload (PDF, DOCX, PPTX, TXT)
- [x] RAG ingestion (local sentence-transformers embeddings)
- [x] Topic extraction (LangGraph knowledge agent)
- [x] Adaptive MCQ generation (Qwen2.5-7B via Modal.com)
- [x] Grounding score verification per question
- [x] Real-time difficulty adaptation (IRT-based)
- [x] Quiz taking UI (Next.js)
- [x] Results + analytics page

## Coming in Phase 2

- [ ] Recommendation agent (online resource suggestions)
- [ ] Concept knowledge graph visualization
- [ ] Multi-session progress tracking
- [ ] Essay/structured answer evaluation
