# Adaptive Assessment Platform

A monorepo containing the backend (FastAPI) and frontend (Next.js) for the Adaptive Assessment Platform.

## Structure
- `backend/`: FastAPI Python application with LangGraph multi-agent workflow for quiz generation and evaluation.
- `frontend/`: Next.js 14 React application with TailwindCSS for the user interface.

## Getting Started

To run this project, you need to set up and start both the **backend** (FastAPI) and the **frontend** (Next.js). You will also need to deploy the Qwen inference endpoint to Modal if you haven't already.

### 1. Deploy the LLM to Modal
The backend requires a Qwen2.5-7B endpoint running on Modal.com.
1. Open a terminal and navigate to your `backend` directory.
2. Install the Modal CLI: `pip install modal`
3. Authenticate with Modal: `modal token new`
4. Deploy the endpoint: `modal deploy modal_inference/qwen_endpoint.py`
5. Copy the endpoint URL from the output (e.g., `https://YOUR_WORKSPACE--qwen-adaptive-quiz-web-endpoint.modal.run`). You will need this for the backend `.env` file.

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
   - Edit `.env` and set `MODAL_ENDPOINT_URL` to the URL you copied in step 1.
5. Start the FastAPI server: `uvicorn app.main:app --reload --port 8000`
   - *API available at `http://localhost:8000`*

### 3. Set Up and Run the Frontend
1. Open a new terminal and navigate to the `frontend/` directory: `cd frontend`
2. Install dependencies: `npm install`
3. Start the development server: `npm run dev`
   - *App available at `http://localhost:3000`*
