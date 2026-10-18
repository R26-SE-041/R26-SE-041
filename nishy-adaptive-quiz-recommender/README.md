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
   - Set `SUPABASE_URL` and `SUPABASE_ANON_KEY` for account authentication.
5. Start the FastAPI server: `uvicorn app.main:app --reload --port 8000`
   - *API available at `http://localhost:8000`*

### 3. Set Up and Run the Frontend
1. Open a new terminal and navigate to the `frontend/` directory: `cd frontend`
2. Install dependencies: `npm install`
   - Copy `.env.example` to `.env.local`, set the API URL and the public Supabase URL/anon key.
3. Start the development server: `npm run dev`
   - *App available at `http://localhost:3000`*

## Production deployment

Deploy this component's frontend to Vercel, API to EC2 and relational database
to Supabase using [DEPLOYMENT.md](./DEPLOYMENT.md). It includes an EC2
CloudFormation template, Docker/HTTPS setup, database migration and local-data import.

Live frontend: https://nishy-adaptive-quiz.vercel.app

Accounts include signup, sign-in, password recovery and password changes.
Each learner has private study documents and quiz history with search, filters,
saved results, recycle bin, undo and restore. See [DEMO_GUIDE.md](./DEMO_GUIDE.md)
for the panel demonstration sequence.

Custom SMTP is still required for signup/reset emails to arbitrary addresses;
Supabase's default mailer is limited to project team emails. See the accounts
section in [DEPLOYMENT.md](./DEPLOYMENT.md) for configuration.
