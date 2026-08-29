# VoiceLearn AI 🎤

> Production-ready voice-powered study assistant for university students.  
> Ask questions about your lecture PDFs using voice — get answers in **Tamil**, **Sinhala**, **English**, or **Thanglish/Singlish**.

## Architecture

```
Next.js Frontend  →  FastAPI Backend  →  LangGraph Agents  →  Modal.com AI Models
                  ↕                  ↕
            Supabase Auth      ChromaDB Vectors
            Supabase Storage
```

## AI Models (all on Modal.com)

| Model | Purpose | GPU |
|---|---|---|
| Whisper Large V3 (1.5B) | Speech → Text | T4 |
| Qwen2.5-3B-Instruct | Prompt Enhancement | T4 |
| Llama 3.1 8B Instruct | RAG Answer Generation | A10G |
| Qwen2.5-7B-Instruct | Tamil/Sinhala Localization | T4 |
| Kokoro-82M / Indic Parler-TTS / SinhalaVITS | Text → Speech | CPU / A10G / T4 |

## Quick Start

### 1. Clone & configure

```bash
git clone <repo>
cd voicelearn

# Backend
cp backend/.env.example backend/.env
# → Fill in Supabase credentials

# Frontend
cp frontend/.env.example frontend/.env.local
# → Fill in Supabase public keys
```

### 2. Deploy Modal endpoints

```bash
pip install modal
modal setup   # authenticate

modal deploy backend/modal_endpoints/whisper_stt.py
# → Copy the printed URL to MODAL_WHISPER_URL in backend/.env

modal deploy backend/modal_endpoints/english_kokoro_tts.py
# → Copy the printed URL to MODAL_ENGLISH_KOKORO_TTS_URL in backend/.env
```

### 3. Start with Docker Compose

```bash
docker-compose up --build
```

- Frontend: http://localhost:3000  
- Backend API: http://localhost:8000  
- API Docs (debug mode): http://localhost:8000/docs  
- ChromaDB: http://localhost:8001  

### 4. Run backend tests

```bash
cd backend
pip install -r requirements.txt
pytest tests/ -v
```

## Project Structure

```
voicelearn/
├── backend/
│   ├── app/
│   │   ├── agents/          # LangGraph nodes (one file per agent)
│   │   ├── api/v1/routes/   # FastAPI route handlers
│   │   ├── core/            # Config, logging, JWT security
│   │   ├── db/              # Supabase + ChromaDB clients
│   │   ├── schemas/         # Pydantic request/response models
│   │   └── services/        # Modal client, ingestion, storage
│   ├── modal_endpoints/     # Independent Modal deployments
│   ├── skills/SKILL.md      # Agent documentation
│   └── tests/
├── frontend/
│   └── src/
│       ├── app/             # Next.js App Router pages
│       ├── components/      # voice/, chat/, documents/, ui/
│       ├── hooks/           # useVoiceRecorder, useSession
│       ├── lib/             # API client, Supabase client
│       └── store/           # Zustand session store
├── docker-compose.yml
└── .github/workflows/       # CI + Modal deploy
```

## Phase Roadmap

- [x] **Phase 1** — Language selection + Whisper STT
- [ ] **Phase 2** — Prompt Enhancement + RAG Generation
- [ ] **Phase 3** — Localization (Tamil/Sinhala/Mixed)
- [ ] **Phase 4** — TTS + audio playback
- [ ] **Phase 5** — Streaming responses + session history

## Supabase Schema

Run this SQL in your Supabase project:

```sql
-- Documents table
create table documents (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users not null,
  filename text not null,
  storage_path text not null,
  chunk_count int default 0,
  created_at timestamptz default now()
);
alter table documents enable row level security;
create policy "Users see own documents" on documents for all using (auth.uid() = user_id);

-- Sessions table
create table sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users not null,
  language text not null default 'english',
  created_at timestamptz default now()
);
alter table sessions enable row level security;
create policy "Users see own sessions" on sessions for all using (auth.uid() = user_id);
```

## GitHub Actions Secrets Required

| Secret | Where to get |
|---|---|
| `MODAL_TOKEN_ID` | modal.com → Settings → API tokens |
| `MODAL_TOKEN_SECRET` | modal.com → Settings → API tokens |

## Design Principles

- **SRP per agent** — one file, one responsibility, one Modal endpoint
- **No hardcoded secrets** — all via environment variables  
- **Graceful degradation** — optional endpoints return fallbacks when not deployed  
- **User-scoped data** — ChromaDB and Supabase queries always filter by `user_id`
