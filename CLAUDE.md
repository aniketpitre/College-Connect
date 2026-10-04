# CollegeConnect

A college ERP for an Indian undergraduate college with a built-in AI help desk
(CollegeConnect AI: cited answers from official documents, in English, Hindi and Marathi).

## Plans — read these before starting ERP work
- [docs/erp/01-product-spec.md](docs/erp/01-product-spec.md): roles and logins, every module's features, unique features, open decisions (D1–D7).
- [docs/erp/02-implementation-plan.md](docs/erp/02-implementation-plan.md): architecture, data model, auth/RBAC design, API outline, phases and the PR list.

Build order: **core ERP first (Phases 0–2), then other features incl. the unique ones (Phases 3–4), CollegeConnect AI last (Phase 5)**. The existing public help desk keeps running unchanged until Phase 5. Work follows the phase/PR order in the implementation plan. If a change departs from the plan, update the plan in the same PR.

## Workflow rules
- **Open a pull request for every code-level change.** Never leave pushed code without a PR.
- One PR per plan item where possible; keep `main` deployable.
- Never commit secrets (`.env`, connection strings, API keys). They live in Vercel environment variables and the gitignored `backend/.env`.

## Stack and layout
- `frontend/`: React + TypeScript + Vite. Help desk UI in `src/HelpDesk.tsx`, admin analytics in `src/Admin.tsx`, strings in `src/i18n.ts` (en/hi/mr).
- `backend/`: FastAPI. RAG pipeline in `app/rag/`, MongoDB in `app/db.py`, query analytics in `app/analytics.py`, routes in `app/routers/`.
- `backend/knowledge/<category>/`: help-desk source documents; rebuild the index with `python -m scripts.ingest` (or `--no-embed`).
- `vercel.json`: frontend and backend deployed as two services on one domain (`/api/*` → backend).

## Commands
- Backend: `cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload --port 8000`
- Frontend: `cd frontend && npm install && npm run dev` · checks: `npm run build && npm run lint`

## Conventions
- Money is stored as integer paise; balances are computed from ledger entries, never edited in place; corrections are reversal entries with a reason.
- Every student-facing string exists in en/hi/mr.
- A student or parent must only ever reach their own (or their linked child's) data; enforce in the backend service layer and test it.
- Environment variables for the app use the `RAG_` prefix for AI settings (plain `CLAUDE_*` names clash with Claude Code's own variables).
