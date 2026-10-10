# Adaptive Assessment Platform

A monorepo containing the backend (FastAPI) and frontend (Next.js) for the Adaptive Assessment Platform.

## Structure
- `backend/`: FastAPI Python application with LangGraph multi-agent workflow for quiz generation and evaluation.
- `frontend/`: Next.js 14 React application with TailwindCSS for the user interface.

## Getting Started

To run this project, set up and start both the **backend** (FastAPI) and the **frontend** (Next.js). Text generation uses the deployed Nishy Qwen2.5-7B fine-tuned Modal endpoint.

### 1. Configure the Nishy model endpoint
The backend defaults to `https://nisharahtheva--nishy-qwen-api-generate.modal.run`. Set `MODAL_ENDPOINT_URL` only if the deployed Nishy endpoint URL changes.

### 2. Set Up and Run the Backend


1. Open a terminal and navigate to the `backend/` directory: `cd backend`
2. Create and activate a Python virtual environment:
   ```bash
   python -m venv venv
   .\venv\Scripts\activate      # On Windows
   # source venv/bin/activate   # On Mac/Linux
   ```
3. Install dependencies: `pip install -r requirements.txt`
4. Configure environment variables:
   - Copy `.env.example` to `.env`: `cp .env.example .env`
   - The supplied value points to the deployed Nishy endpoint.
5. Start the FastAPI server: `uvicorn app.main:app --reload --port 8000`
   - *API available at `http://localhost:8000`*

### 3. Set Up and Run the Frontend
1. Open a new terminal and navigate to the `frontend/` directory: `cd frontend`
2. Install dependencies: `npm install`
3. Start the development server: `npm run dev`
   - *App available at `http://localhost:3000`*
