# CollegeConnect — Implementation Plan

> **Status:** Draft v1 · **Last updated:** 2026-10-04
>
> How we build the product described in [01-product-spec.md](01-product-spec.md): the
> architecture, the data model, authentication, the order of work, and how each piece is
> tested and shipped. Every phase is delivered as small pull requests; each PR leaves `main`
> deployable.

---

## 1. Where we start

Already in `main`:

| Piece | Location |
|---|---|
| React + Vite + TypeScript help desk UI (EN/HI/MR) | `frontend/src/HelpDesk.tsx` |
| Admin analytics portal (token login) | `frontend/src/Admin.tsx`, `backend/app/routers/admin.py` |
| FastAPI backend | `backend/app/main.py` |
| RAG pipeline (BM25 / Voyage vectors + Claude) | `backend/app/rag/` |
| MongoDB Atlas connection + query logging | `backend/app/db.py`, `backend/app/analytics.py` |
| Knowledge base + ingestion | `backend/knowledge/`, `backend/scripts/ingest.py` |
| Vercel deployment (two services, one domain) | `vercel.json` |

The ERP is built **inside this same repo and deployment**. The help desk becomes one module of it.

---

## 2. Architecture

```
                       ┌──────────────────────────────────────────────┐
  Browser / phone      │  React SPA (Vite)                            │
  (student, parent,    │  /            → public help desk + login      │
   staff, public)      │  /verify/:code→ public verification           │
                       │  /app/...     → role-based portal             │
                       └───────────────┬──────────────────────────────┘
                                       │ HTTPS, same origin, cookie session
                       ┌───────────────▼──────────────────────────────┐
  Vercel               │  FastAPI (Python serverless function)         │
                       │  core/   auth, sessions, RBAC, audit, errors  │
                       │  modules/ setup, students, fees, receipts,    │
                       │          notices, attendance, exams, certs …  │
                       │  rag/    CollegeConnect AI                     │
                       └──────┬─────────────┬──────────────┬──────────┘
                              │             │              │
                  ┌───────────▼───┐  ┌──────▼──────┐  ┌────▼──────────────┐
                  │ MongoDB Atlas │  │ Vercel Blob │  │ External APIs      │
                  │ all records   │  │ PDFs, photos│  │ Claude, Voyage,    │
                  │ + audit log   │  │ documents   │  │ email/SMS/WhatsApp,│
                  └───────────────┘  └─────────────┘  │ payment gateway(P3)│
                                                      └────────────────────┘
  Vercel Cron → /api/cron/* (daily reminders, deadline radar, backups check)
```

### 2.1 Technology choices

| Concern | Choice | Why |
|---|---|---|
| Backend | **FastAPI** (existing) | Typed, fast, auto API docs, already deployed |
| Database | **MongoDB Atlas** (existing) | Already connected; flexible student records; multi-document **transactions** for money |
| Frontend | **React + TypeScript + Vite** (existing) + **React Router** | Replace the hash routing with real routes for role portals |
| Server state | **TanStack Query** | Caching, retries, loading states for every screen |
| Forms | **React Hook Form + Zod** | Validation that matches the backend's Pydantic models |
| Password hashing | **argon2-cffi** (Argon2id) | Current best practice |
| Sessions | Opaque random token in an **HttpOnly, Secure, SameSite=Lax cookie**; only its SHA-256 hash stored in MongoDB | Revocable (sign out everywhere, disable account) — unlike stateless JWTs |
| 2-step codes | **pyotp** (TOTP) + email OTP | Authenticator apps or email |
| PDFs | **fpdf2** (pure Python, Unicode fonts) | Small enough for serverless; receipts/certificates |
| QR codes | **segno** (pure Python) | No native dependencies |
| File storage | **Vercel Blob** (private) | Serverless functions have no persistent disk |
| Scheduled jobs | **Vercel Cron** → protected `/api/cron/*` endpoints | Reminders, digests. Hobby plan allows daily jobs only |
| Email | Transactional provider (e.g. Resend / Amazon SES) | P1 |
| SMS / WhatsApp | Indian provider with DLT registration (e.g. MSG91 / Gupshup) | P3 — needs DLT templates approved |
| Payments | Razorpay or similar (UPI, cards, net banking) with webhooks | P3 |
| AI | Claude (`claude-opus-5-5`) + Voyage embeddings (existing) | Already integrated |
| Tests | **pytest** + real MongoDB in CI; **Playwright** end-to-end | Money and marks need real transaction tests |
| CI | **GitHub Actions**: lint, type-check, tests, build on every PR | Nothing reaches `main` red |

### 2.2 Repository layout (target)

```
backend/
  app/
    main.py                 # app factory, routers
    core/
      config.py             # settings from env
      db.py                 # Mongo client, transactions helper, indexes
      security.py           # hashing, tokens, TOTP
      auth.py               # current_user dependency, sessions
      rbac.py               # roles → permissions, scope checks
      audit.py              # append-only audit writer
      errors.py             # consistent error responses
      i18n.py               # server-side translations for PDFs/messages
    modules/
      setup/                # academic years, programmes, subjects, categories
      users/                # accounts, roles, login, password reset
      students/             # SIS, import, promotion
      fees/                 # structures, demands, ledger, collection
      receipts/             # numbering, PDF, verify
      notices/
      attendance/           # P2
      exams/                # P2
      certificates/         # P2
      ...                   # library, hostel, placement, grievance (P3)
      each module: router.py, schemas.py (Pydantic), service.py (logic), repo.py (Mongo)
    rag/                    # existing CollegeConnect AI
  tests/                    # pytest, per module
  scripts/                  # ingest, seed demo data, create first admin
frontend/
  src/
    app/                    # router, layouts per role, auth context
    features/               # one folder per module (pages + components + api hooks)
    components/             # shared UI: Table, Form fields, Money, StatusBadge …
    i18n/                   # en/hi/mr strings
docs/erp/                   # this plan
```

### 2.3 Vercel constraints and how we handle them

| Constraint | Handling |
|---|---|
| Functions are stateless, no local disk | Files → Vercel Blob; state → MongoDB |
| Cold starts | Keep the backend bundle small (no pandas/numpy); one Mongo client per instance |
| Request time limits | No long jobs in requests; bulk imports processed in chunks with progress saved in Mongo |
| Hobby cron = once a day | Enough for reminders; Pro if hourly jobs are needed |
| Hobby is non-commercial | Move to **Vercel Pro** before the college uses it in production |
| Atlas free tier (M0) has no automated backups | Daily `mongodump` job to private storage until upgrading to a tier with backups |

---

## 3. Data model (MongoDB collections)

Conventions: every document has `_id`, `created_at`, `created_by`, `updated_at`; money is
**integer paise**; dates are UTC; soft status fields instead of deletes; every collection
has an `academic_year` where relevant.

| Collection | Key fields | Indexes |
|---|---|---|
| `users` | email or prn, phone, password_hash, roles[], scopes (dept ids, division ids), status, mfa, failed_logins, locked_until, must_change_password, linked_student_ids (parents) | unique email, unique prn, phone |
| `sessions` | token_hash, user_id, created_at, last_seen, expires_at, ip, user_agent | token_hash unique, TTL on expires_at |
| `audit_log` | at, actor_id, action, entity, entity_id, before, after, reason, ip | (entity, entity_id), at |
| `academic_years` | code "2026-27", start, end, is_current | code unique |
| `departments`, `programmes`, `subjects` | names, codes, credits, max marks | code unique |
| `divisions` | programme, year, name, academic_year, class_teacher | compound unique |
| `students` | prn, name parts, dob, gender, category, contacts, guardian, address, aadhaar_masked, apaar_id, programme/year/division/roll, status, photo_blob, documents[] | prn unique, (division, roll), text index on name |
| `fee_heads` | code, name, ledger_account | code unique |
| `fee_structures` | academic_year, programme, year, category, heads[{head, amount_paise}], installments[{due_date, heads}], late_fee_rule, version | compound unique |
| `ledger_entries` | student_id, academic_year, type (demand / payment / concession / scholarship / reversal / late_fee / refund), heads[{head, amount_paise}], amount_paise (signed), receipt_id, reference, reason, approved_by | (student_id, academic_year), receipt_id |
| `receipts` | number "R/2026-27/001234", student_id, amount_paise, heads[], mode, reference, collected_by, issued_at, status (valid / cancelled), verify_code, pdf_blob | number unique, verify_code unique |
| `counters` | _id "receipt:2026-27", seq | — |
| `approvals` | type (receipt_cancel, refund, concession, tc), payload, requested_by, status, decided_by | status, type |
| `notices` | title/body per language, pdf_blob, audience, publish_at, expires_at, indexed | publish_at, audience |
| `queries` | (existing help-desk log) | existing |
| P2: `timetable_slots`, `attendance_sessions`, `attendance_marks`, `assessments`, `marks`, `results`, `certificate_requests`, `certificates` | | |
| P3: `books`, `loans`, `rooms`, `allotments`, `outpasses`, `drives`, `applications`, `grievances`, `staff`, `leaves`, `payments_gateway` | | |

### 3.1 Money rules (enforced in code and tests)
1. A student's **balance = sum of their ledger entries** for the year. Never stored as an editable number.
2. **Collecting a fee is one Mongo transaction:** increment the receipt counter → insert the receipt → insert the payment ledger entry → write the audit entry. Either all succeed or none.
3. Receipt numbers come from `counters` with an atomic `$inc`, so they are **sequential and gap-free** even with two cashiers at once.
4. Receipts are **never edited or deleted.** Cancellation = an approved `reversal` ledger entry + receipt `status: cancelled`; the Verify page then shows "Cancelled".
5. Amounts are integers in paise; display formatting (₹1,25,000.00, amount in words in English/Hindi/Marathi) happens at the edge.

---

## 4. Authentication and authorisation design

### 4.1 Flows
- **Staff sign-in:** email + password → (if MFA required) code → session cookie.
- **Student sign-in:** PRN + password → if `must_change_password`, forced password change → privacy notice consent (first time) → portal.
- **Parent sign-in:** mobile + OTP (or password) → child switcher.
- **Password reset:** request → OTP/link (10-minute expiry, single use, hashed at rest) → new password → **all other sessions revoked**.
- **Sign out:** deletes the session; "sign out everywhere" deletes all of the user's sessions.

### 4.2 Protection
- Argon2id hashes; constant-time comparisons; generic "wrong PRN or password" messages.
- Rate limiting on sign-in, OTP and reset endpoints (per IP and per account, stored in Mongo).
- CSRF: SameSite=Lax cookie + a required custom header (`X-Requested-With`) on every state-changing request.
- Security headers: HSTS, CSP, X-Content-Type-Options, frame-ancestors none.
- The existing `ADMIN_TOKEN` admin page is replaced by real accounts in Phase 1.

### 4.3 Role-based access control
- `rbac.py` maps each role to permissions like `fees.collect`, `receipts.cancel.request`, `receipts.cancel.approve`, `students.read`, `marks.write`.
- Every endpoint declares its permission: `Depends(require("fees.collect"))`.
- **Scope checks** in the service layer: a student can only load `student_id == self`; a parent only linked children; faculty only their assigned divisions/subjects; HOD only their department. Tests cover every "can't see someone else's data" case.
- Separation of duties: requester ≠ approver for cancellations, refunds, concessions.

---

## 5. API outline (Phase 1)

All under `/api/v1`. JSON in/out; errors as `{ "error": { "code", "message", "field?" } }`.

| Method & path | Who | Purpose |
|---|---|---|
| `POST /auth/login` | all | Sign in (staff email / student PRN) |
| `POST /auth/logout`, `/auth/logout-all` | signed in | Sign out |
| `POST /auth/password/change`, `/auth/password/reset/request`, `/auth/password/reset/confirm` | all | Passwords |
| `POST /auth/mfa/setup`, `/auth/mfa/verify` | staff | Two-step verification |
| `GET /me` | signed in | Current user, roles, permissions, linked students |
| `GET/POST/PATCH /setup/academic-years`, `/programmes`, `/divisions`, `/subjects`, `/categories` | admin | Institution setup |
| `GET/POST/PATCH /users`, `POST /users/{id}/reset-password` | admin, office | Accounts |
| `GET /students?search=&division=`, `POST /students`, `PATCH /students/{id}` | office | SIS |
| `POST /students/import` (CSV) → `GET /imports/{id}` | office | Bulk import with validation report |
| `GET/POST /fees/heads`, `/fees/structures` | accounts | Fee setup |
| `POST /fees/demands/generate` | accounts | Create demands for a class/year |
| `GET /fees/students/{id}/ledger` | accounts, student (own), parent | Ledger and balance |
| `POST /fees/collect` | accounts | Collect → receipt (transaction) |
| `POST /receipts/{id}/cancel-request`, `POST /approvals/{id}/decide` | accounts / principal | Cancellation workflow |
| `GET /receipts/{id}/pdf` | accounts, student (own), parent | Download receipt |
| `GET /verify/{code}` | public | Verify receipt/certificate (masked) |
| `GET /reports/day-book?date=`, `/reports/outstanding?division=` | accounts, principal | Reports (+ `?format=xlsx`) |
| `GET/POST /notices`, `GET /notices/feed` | office / everyone | Notices |
| `POST /assistant/ask` | public or signed in | CollegeConnect (adds "my record" context when signed in as student/parent) |
| `GET /admin/stats` | principal, admin | Existing analytics, now behind real auth |
| `GET /audit?entity=&id=` | admin, principal | Audit log |

---

## 6. CollegeConnect AI inside the ERP

- **Public:** unchanged pipeline (`backend/app/rag/`).
- **Ask my record (P1 fees):** when the caller is a signed-in student or parent, the backend builds a short, structured **"Your fee account" excerpt** from the ledger (structure, paid, concessions, balance, next due date) and passes it to Claude together with the retrieved document excerpts. Claude cites it like any other source ("Your fee account as of 4 Oct 2026").
  - The personal excerpt is built server-side from the **caller's own** records only; the model never gets database access or other students' data.
  - Personal excerpts are **not** written to the `queries` log; only the question, language and which documents answered.
- **P2:** add attendance and marks excerpts. **P4:** deadline radar and the staff assistant (aggregate queries with the numbers shown).
- **Notices → knowledge base:** publishing a notice chunks it, embeds it and adds it to the index stored in MongoDB (moving the index from `index.json` into a `kb_chunks` collection, with Atlas Vector Search when the corpus grows).

---

## 7. Frontend plan

- **Routes:** `/` (help desk + sign-in button), `/login`, `/verify/:code`, `/app` → redirects to the role's home, `/app/student/*`, `/app/parent/*`, `/app/office/*`, `/app/accounts/*`, `/app/exam/*`, `/app/faculty/*`, `/app/principal/*`, `/app/admin/*`.
- **Layouts:** student/parent = bottom tab bar on phones, sidebar on desktop; staff = sidebar + data tables.
- **Shared components:** `DataTable` (search, filter, paginate, export), `MoneyText` (₹ formatting), `StatusBadge`, `ConfirmDialog` (with reason field for money/marks actions), `EmptyState`, `FileUpload`, `PdfLink`.
- **Permissions in the UI** come from `GET /me`; hidden buttons are a convenience only — the API is the real gate.
- **i18n:** all student/parent strings in `en/hi/mr`; staff screens English first.
- **Offline attendance (P2):** service worker + IndexedDB queue, synced when back online.

---

## 8. Quality: testing and CI

| Layer | What | Where |
|---|---|---|
| Unit | Fee calculations, late fees, balance, receipt numbering, permissions matrix, amount-in-words | `backend/tests/` |
| Integration | API + **real MongoDB** (GitHub Actions service container, replica set for transactions): collect fee concurrency (no duplicate receipt numbers), cancellation flow, scope leaks (student A can't read B) | `backend/tests/` |
| End-to-end | Playwright: student first login → view fees → download receipt; cashier collects → receipt verifies publicly | `frontend/e2e/` |
| Static | ruff + mypy (backend), oxlint + `tsc` (frontend) | CI |
| Security | Dependency audit, OWASP checklist per phase, secrets scanning | CI + review |

**Definition of done for every PR:** CI green; tests for new logic; no secrets; docs updated
when behaviour changes; screenshots for UI changes; preview deployment checked.

---

## 9. Phases and pull requests

Estimates assume one developer working with Claude Code; they are for ordering, not promises.

### Phase 0 — Foundations (≈1 week)
| PR | Content |
|---|---|
| 0.1 | `CLAUDE.md` + these plan docs |
| 0.2 | GitHub Actions CI: backend lint/type/tests (Mongo service), frontend lint/type/build |
| 0.3 | Backend restructure into `core/` + `modules/`; settings; error format; `/api/v1` prefix (old routes kept as aliases) |
| 0.4 | Frontend: React Router, TanStack Query, layout shells, shared components skeleton |

**Exit:** CI runs on every PR; app behaves exactly as today.

### Phase 1 — Logins, students, fees, receipts, student portal (≈4–5 weeks)
| PR | Content |
|---|---|
| 1.1 | Users, sessions, Argon2 passwords, login/logout, `GET /me`, rate limiting, audit log; script to create the first System Admin |
| 1.2 | RBAC permissions + scope checks + tests; replace `ADMIN_TOKEN` with real roles |
| 1.3 | Institution setup module + admin screens |
| 1.4 | Student Information System: CRUD, search, CSV import with validation report, student account creation with temporary password |
| 1.5 | First-login flow: forced password change, privacy-notice consent, language choice; password reset by email OTP |
| 1.6 | Fee heads, fee structures, demand generation, concessions with approval |
| 1.7 | Fee collection transaction, receipt numbering, receipt PDF with QR (fpdf2 + segno), Vercel Blob storage |
| 1.8 | Public Verify page; receipt cancellation request/approval |
| 1.9 | Accounts reports: day book, outstanding by class, Excel export |
| 1.10 | Student portal: home ("needs attention"), profile, fees & ledger, receipts download, notices |
| 1.11 | Notices module (create, audience, expiry) + email notifications + auto-index into the help desk |
| 1.12 | "Ask my record" for fees in CollegeConnect |
| 1.13 | Demo seed data (1 programme, 3 years, 60 students, fee structures) + Playwright e2e |

**Exit criteria (acceptance):**
- Office imports 60 students from a CSV; each gets a login.
- A student signs in with PRN + temporary password, sets their own, and sees the correct fee balance.
- A cashier collects a fee; a receipt PDF with a sequential number is produced in < 3 s; two cashiers at once never get the same number (tested).
- Scanning the receipt QR on a phone shows "Genuine" with masked details; after an approved cancellation it shows "Cancelled".
- A student asks "How much fee do I still owe?" in Marathi and gets the correct amount with citations.
- A student can never open another student's data (tested for every endpoint).

### Phase 2 — Academics (≈4 weeks)
Timetable · attendance (10-second marking, offline queue) · subject-wise % and "can miss / must attend" · defaulter alerts · assessments and internal marks · HOD approval and Exam Cell lock · **University Upload Guard** · results import, SGPA/CGPA · certificate requests with promised dates, templates and QR · student portal additions · "Ask my record" for attendance and marks · notice auto-translation.

### Phase 3 — Payments, parents and campus (≈4–6 weeks)
Online fee payment with gateway webhooks and reconciliation · parent portal with consent controls · SMS/WhatsApp (DLT templates) · library · hostel · placement · grievance · staff records and leave · admissions module (online applications, merit lists).

### Phase 4 — Compliance and intelligence (≈3–4 weeks)
NAAC criterion tagging and AQAR tables · AISHE/NIRF exports · APAAR/ABC fields and export · DigiLocker readiness · early-warning scores with reasons · deadline radar · staff AI assistant · full data export and open API documentation.

---

## 10. Data migration and onboarding

1. **Templates:** downloadable Excel/CSV templates for students, fee structures, opening balances (fees already paid this year), staff.
2. **Validation report** before anything is saved: missing PRN, duplicate PRN, unknown category, bad dates — fix and re-upload.
3. **Opening balances:** imported as ledger entries of type `opening_balance` with the old receipt numbers kept as references.
4. **Pilot:** one programme (BCA) for one term alongside the existing process, then the whole college.
5. **Training:** 30-minute sessions per role; one-page guides; the AI help desk also answers "how do I…" questions about the ERP itself.

---

## 11. Operations

| Item | Plan |
|---|---|
| Environments | Production (`main`), Preview (every PR, separate database `collegeconnect_preview`), Local |
| Secrets | Vercel environment variables only; never in git; rotated when a person leaves |
| Required env vars | `MONGODB_URI`, `SESSION_SECRET`, `ANTHROPIC_API_KEY`, `VOYAGE_API_KEY`, `BLOB_READ_WRITE_TOKEN`, `EMAIL_API_KEY`, `CRON_SECRET` (+ SMS/payment keys in P3) |
| Backups | Daily dump, 30-day retention, restore drill each term |
| Monitoring | Vercel logs + error alerts; `/api/health` checks DB, AI and storage |
| Incident / breach | Written runbook; DPDP breach notification to the Data Protection Board and affected users within the prescribed time |

---

## 12. Risks

| Risk | Mitigation |
|---|---|
| Money bugs (wrong balances, duplicate receipt numbers) | Ledger-only balances, transactions, concurrency tests, reversals instead of edits |
| Data leak between students | Scope checks in the service layer + tests for every endpoint |
| Peak load on fee/result days | Indexed queries, cached reads, load test before go-live |
| Staff don't adopt it | 10-second flows, pilot with one programme, train champions in each office |
| Vendor/plan limits (Vercel Hobby, Atlas M0) | Upgrade plan before production; budget noted in D7 |
| Scope creep | Phases ship independently; anything new goes to the next phase's list |
| AI gives a wrong answer | Citations always shown; "no source → no answer"; knowledge-gap review weekly |

---

## 13. Immediate next steps

1. Confirm or change decisions **D1–D7** in the product spec.
2. Start **Phase 0** (CI + restructure), then **PR 1.1** (logins).
3. Add `ANTHROPIC_API_KEY` in Vercel so the help desk generates answers.
