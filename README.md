# CollegeConnect AI

A multilingual, source-grounded web application that acts as a digital college help desk — students ask questions in natural language and get answers retrieved from official college documents, with source references (Ask → Retrieve → Answer → Cite).

## Current status

This is a **frontend + backend skeleton**, not the full live RAG system:

- The React frontend is fully built: multilingual chat UI (English / Hindi / Marathi), category quick-filters (Admissions, Fees & Accounts, Examinations, Placements, Hostel & Campus, Notices), source-citation cards, and grounded/confidence badges.
- The FastAPI backend has real, working API routes (`/api/query`, `/api/categories`, `/api/health`), but retrieval runs on a small local `documents.json` file with keyword matching — not a real document repository, embeddings, vector search, or an LLM.
- The clearly marked integration point for the real pipeline is [backend/app/services/retrieval.py](backend/app/services/retrieval.py). See the TODO at the top of that file for what's needed to make this a live RAG system (document ingestion, chunking, embeddings, vector store, LLM-generated answers).

## Project structure

```
College Connect/
  frontend/   React + Vite + TypeScript chat UI
  backend/    FastAPI backend (stubbed retrieval)
```

## Running locally

### Backend

```
cd backend
python -m venv .venv
.venv\Scripts\activate       # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API docs available at http://localhost:8000/docs

### Frontend

```
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Copy `.env.example` to `.env` if you need to point the frontend at a different backend URL.
