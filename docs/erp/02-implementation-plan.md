# CollegeConnect — Implementation Plan

> **Status:** Draft v2 · **Last updated:** 2026-10-04
>
> How we build the product described in [01-product-spec.md](01-product-spec.md).
>
> **Build order (decided):** the **core ERP first**, then the **other features** — including the
> ones existing college ERPs lack — and **CollegeConnect AI last**. Every phase ships as small
> pull requests; each PR leaves `main` deployable.

---

## 1. Phase overview

| Phase | Name | What it delivers | Est. |
|---|---|---|---|
| **0** | Foundations | CI, code structure, routing, design system, test database | 1 wk |
| **1** | Core ERP — people & money | Logins & roles, institution setup, student records, fees, **QR-verifiable receipts**, student portal, notices, audit log | 5 wk |
| **2** | Core ERP — academics | Timetable, **10-second offline attendance**, internal marks with the **University Upload Guard**, results, **certificates with a promised date** | 5 wk |
| **3** | Campus operations | Parent portal (with DPDP consent), online fee payment, SMS/WhatsApp/email, admissions, library, hostel, placement, grievance, staff & leave | 7 wk |
| **4** | Control, compliance & openness | **NAAC-ready by default**, AISHE/NIRF/APAAR, dashboards, **rule-based early warning**, **scholarship eligibility checker**, **full export + open API** | 4 wk |
| **5** | CollegeConnect AI | AI help desk inside the ERP, **Ask my record**, auto-translated and **self-publishing notices**, **deadline radar**, **knowledge-gap loop**, staff AI assistant | 4 wk |

Estimates assume one developer working with Claude Code; they set the order, not a promise.
**Total ≈ 26 weeks.**

### 1.1 Where the "what other ERPs lack" features land

| Unique feature (spec §5) | Phase | Needs AI? |
|---|---|---|
| U2 QR-verifiable receipts & certificates + public Verify page | 1 (receipts), 2 (certificates) | No |
| U9 10-second attendance that works offline | 2 | No |
| U7 University Upload Guard | 2 | No |
| U6 Certificates with a promised date + escalation | 2 | No |
| U12 No lock-in: full export + open API | 1 (export basics), 4 (API) | No |
| U8 NAAC-ready by default | 4 | No |
| U10 Explainable early warning (rule-based) | 4 | No (ML upgrade optional in 5) |
| U11 Scholarship eligibility checker (rule-based) | 4 | No |
| U4 Self-publishing notices (auto-translate + auto-index) | 5 | Yes |
| U1 Ask my record | 5 | Yes |
| U3 Deadline radar | 5 | Yes |
| U5 Knowledge-gap loop (inside the ERP) | 5 | Yes |

### 1.2 The existing AI help desk until Phase 5
The public CollegeConnect help desk that is live today **keeps running unchanged** (same URL,
same `/api/query`). We do not extend it until Phase 5; in Phase 0 it moves under the new
routing so it sits at `/` next to the **Sign in** button.

### 1.3 Minimum for the BCA project submission
If time is short, **Phases 0–2 plus the existing help desk** make a complete, demonstrable
system: logins for every core role, student records, fees with verifiable receipts,
attendance, marks, results and certificates, and a cited multilingual AI help desk.

---

## 2. Architecture

```
                       ┌──────────────────────────────────────────────┐
  Browser / phone      │  React SPA (Vite + TypeScript)               │
  (student, parent,    │  /              public help desk + Sign in   │
   staff, public)      │  /verify/:code  public document verification │
                       │  /app/...       role-based portals           │
                       └───────────────┬──────────────────────────────┘
                                       │ HTTPS, same origin, cookie session
                       ┌───────────────▼──────────────────────────────┐
  Vercel               │  FastAPI (Python serverless function)         │
                       │  core/    auth, sessions, RBAC, audit, errors │
                       │  modules/ setup, students, fees, receipts,    │
                       │           notices, attendance, exams, …       │
                       │  rag/     CollegeConnect AI (Phase 5)          │
                       └──────┬─────────────┬──────────────┬──────────┘
                              │             │              │
                  ┌───────────▼───┐  ┌──────▼──────┐  ┌────▼──────────────┐
                  │ MongoDB Atlas │  │ Vercel Blob │  │ External services  │
                  │ records +     │  │ PDFs, photos│  │ email (P1), SMS/   │
                  │ audit log     │  │ documents   │  │ WhatsApp & payments│
                  └───────────────┘  └─────────────┘  │ (P3), Claude/Voyage│
                                                      │ (P5)               │
  Vercel Cron → /api/cron/*  (reminders, escalations, backups check)      └────────────────────┘
```

### 2.1 Technology choices

| Concern | Choice | Why |
|---|---|---|
| Backend | **FastAPI** (existing) | Typed, fast, auto-generated API docs |
| Database | **MongoDB Atlas** (existing) | Flexible records; multi-document **transactions** for money |
| Frontend | **React + TypeScript + Vite** (existing), **React Router**, **TanStack Query**, **React Hook Form + Zod** | Real routes per role, cached server data, validated forms |
| Passwords | **argon2-cffi** (Argon2id) | Current best practice |
| Sessions | Random token in an **HttpOnly, Secure, SameSite=Lax cookie**; only its SHA-256 hash stored | Revocable: sign out everywhere, disable on TC |
| 2-step codes | **pyotp** (TOTP) + one-time recovery codes | Authenticator app; email OTP deferred (see 1.3) |
| PDFs / QR | **fpdf2** + **segno** (pure Python) | Small, no native libraries — fits serverless |
| Files | **Vercel Blob** (private) | Functions have no persistent disk |
| Scheduled jobs | **Vercel Cron** → secret-protected `/api/cron/*` | Reminders and escalations (Hobby = daily) |
| Offline attendance | Service worker + IndexedDB queue | Works with no signal in the classroom |
| Email | Resend or Amazon SES | Phase 1 |
| SMS / WhatsApp | Indian provider with DLT-approved templates (e.g. MSG91 / Gupshup) | Phase 3 |
| Payments | Razorpay or similar, verified webhooks | Phase 3 |
| AI | Claude (`claude-opus-5-5`) + Voyage embeddings (existing code) | Phase 5 |
| Tests | **pytest** with a real MongoDB replica set in CI; **Playwright** end-to-end | Money and marks need real transaction tests |
| CI | **GitHub Actions** on every PR | Nothing reaches `main` red |

### 2.2 Repository layout (target)

```
backend/app/
  main.py
  core/        config, db (client, transactions, indexes), security, auth, rbac, audit, errors, i18n, pdf
  modules/     one package per module: router.py · schemas.py · service.py · repo.py
               setup/ users/ students/ fees/ receipts/ notices/ audit/ export/        (P1)
               timetable/ attendance/ exams/ results/ certificates/                    (P2)
               parents/ payments/ messaging/ admissions/ library/ hostel/
               placement/ grievance/ staff/                                            (P3)
               accreditation/ analytics/ earlywarning/ scholarships/ api_keys/         (P4)
  rag/         existing help desk; extended in P5
backend/tests/ one folder per module
backend/scripts/ create_admin.py, seed_demo.py, ingest.py
frontend/src/
  app/         router, auth context, role layouts
  features/    one folder per module (pages, components, API hooks)
  components/  DataTable, MoneyText, StatusBadge, ConfirmDialog, FileUpload, PdfLink …
  i18n/        en / hi / mr
docs/erp/      product spec and this plan
```

### 2.3 Vercel and Atlas constraints

| Constraint | Handling |
|---|---|
| Stateless functions, no disk | Files in Vercel Blob; state in MongoDB |
| Request time limits | Bulk imports processed in chunks with progress saved; no long jobs in requests |
| Hobby cron runs daily, Hobby is non-commercial | Fine for development; **Vercel Pro before the college goes live** |
| Atlas M0 has no automated backups | Daily dump job until moving to a tier with backups (before go-live) |

---

## 3. Cross-cutting rules (apply from Phase 1)

### 3.1 Data conventions
- Every document: `_id`, `created_at`, `created_by`, `updated_at`; times in UTC; `academic_year` where relevant.
- Statuses instead of deletes. Corrections are new records that reference the old one, with a reason.

### 3.2 Money rules
1. Amounts are **integer paise**. Formatting (₹1,25,000.00 and amount in words) happens only at display time.
2. A student's balance is **the sum of their ledger entries**; never stored as an editable number.
3. **Collecting a fee is one transaction:** increment the receipt counter → insert receipt → insert ledger entry → write audit entry.
4. Receipt numbers come from an atomic counter: **sequential and gap-free per academic year**, even with several cashiers.
5. Receipts are never edited or deleted; cancellation is an approved reversal entry and the receipt shows "Cancelled" on the Verify page.

### 3.3 Security
- Argon2id hashing; generic login errors; 5 failures → 15-minute lock; rate limits on login/OTP/reset.
- 2-step verification required for System Admin, Principal, Accounts, Exam Cell.
- CSRF protection: SameSite cookie + required custom header on state-changing requests. Security headers (HSTS, CSP, no framing).
- **Permission + scope on every endpoint:** `Depends(require("fees.collect"))` plus service-layer scope checks (student → self; parent → linked children; faculty → assigned classes; HOD → department).
- Separation of duties: requester ≠ approver for cancellations, refunds, concessions, marks unlock.
- Append-only **audit log** for every change to money, marks, records and roles.

### 3.4 Privacy (DPDP Act 2023 / Rules 2025)
Privacy notice and consent at first login; parental consent for under-18s; Aadhaar stored masked;
documents private with short-lived links; student "download my data"; retention schedule;
breach runbook.

### 3.5 Quality bar for every PR
CI green (ruff, mypy, pytest; oxlint, tsc, build) · tests for new logic, including "cannot see
another student's data" tests for every new endpoint · no secrets · screenshots for UI ·
preview deployment checked · plan/spec updated if behaviour differs.

---

## 4. Phase 0 — Foundations (≈1 week)

**Goal:** a safe base to build on; the app behaves exactly as today.

> **Delivery note:** development runs from a single branch, so only one pull request can be open
> at a time. Phase 0 therefore ships as **one PR with one commit per item (0.1–0.4)**; later
> phases follow the same pattern (one PR per phase or per group of items, one commit per item).

| PR | Content | Done when |
|---|---|---|
| 0.1 | **CI:** GitHub Actions — backend ruff + mypy + pytest against a MongoDB replica-set service container; frontend oxlint + `tsc` + build | Runs on every PR; branch protection on `main` |
| 0.2 | **Backend restructure:** `core/` (config, db with transaction helper and index bootstrap, errors) and `modules/`; `/api/v1` prefix; existing `/api/query`, `/api/health`, `/api/admin/stats` kept as aliases | Existing tests pass; help desk unchanged |
| 0.3 | **Frontend shell:** React Router (`/`, `/login`, `/verify/:code`, `/app/*`), TanStack Query, role layout skeletons, shared components (`DataTable`, `MoneyText`, `StatusBadge`, `ConfirmDialog`, `EmptyState`), i18n folder | Help desk at `/`; `/#/admin` redirected to `/app/admin` |
| 0.4 | **Dev tooling:** `scripts/seed_demo.py` skeleton, `.env.example` updated, separate preview database name | One command gives a local app with demo data |

---

## 5. Phase 1 — Core ERP: people and money (≈5 weeks)

**Goal:** the college can run admissions-to-fee-receipt for real students, and students can sign in and see their fees.

### 5.1 Features

**Identity & access**
- Staff login (email + password), student login (PRN + temporary password → forced change), password reset (emailed one-time link), 2-step verification for sensitive roles, sessions with "sign out everywhere", lockout, login history.
- Roles R1–R9 and R13 from the spec, with the permission matrix and scope checks.
- First-login flow for students: set password → confirm contact → accept privacy notice → choose language.

**Institution setup**
- Academic years (current-year switch), departments, programmes, years, divisions, semesters, subjects (credits, max internal/external), categories and quotas, numbering formats, holidays.

**Student Information System**
- Student master record (personal, guardian, contact, category, masked Aadhaar, APAAR ID field, previous education, photo, documents).
- Academic placement (programme/year/division/roll/PRN/status).
- **Excel/CSV import with a validation report** (nothing saved until clean), bulk account creation with printable temporary passwords, bulk promotion at year end.
- Student change requests → office approval, with full history.

**Fees & accounts**
- Fee heads; fee structures per year × programme × year-of-study × category, with installments, due dates and late-fee rules; versioned per academic year.
- Fee demand generation per student; concessions with approval; scholarship tracking (expected → sanctioned → received).
- **Counter collection** (cash, UPI, card, cheque/DD, bank transfer + reference).
- **Receipts:** gap-free numbers (`R/2026-27/000123`), PDF on letterhead with head-wise breakup, amount in words, collector, **QR code → public Verify page**; reprints marked "Duplicate"; send by email.
- Cancellation/refund requests → Principal approval → reversal entries.
- Opening balances import (fees already paid this year before go-live).
- Reports: day book, head-wise, mode-wise, outstanding by class, defaulters; Excel export.

**Student portal (v1)**
- Home with "needs your attention" cards (fee due, unpaid installment, new notice).
- Profile (view + request correction, upload photo/documents).
- Fees: structure, installments, paid, concessions, scholarships, **balance**, history, **download receipts**, fee statement PDF.
- Notices for their class.
- Help desk link (existing AI, unchanged).

**Notices (v1)**
- Create (text or PDF), audience (all / programme / year / division / staff), publish time, expiry, pin.
- Optional Hindi/Marathi versions **typed by staff** (automatic translation comes in Phase 5).
- Email notification to the audience.

**Audit & export (v1)**
- Audit log viewer (admin, principal).
- Student "download my data" (JSON/PDF); admin full export of students and fees (CSV).

### 5.2 Data (collections added)
`users`, `sessions`, `login_events`, `audit_log`, `academic_years`, `departments`, `programmes`,
`divisions`, `subjects`, `categories`, `students`, `student_change_requests`, `imports`,
`fee_heads`, `fee_structures`, `ledger_entries`, `receipts`, `counters`, `approvals`, `notices`.

### 5.3 API (under `/api/v1`)
`/auth/*` (login, logout, logout-all, password change/reset, mfa) · `/me` · `/setup/*` ·
`/users` · `/students` (+ `/import`, `/promote`, `/{id}/change-requests`) · `/fees/heads` ·
`/fees/structures` · `/fees/demands/generate` · `/fees/concessions` ·
`/fees/students/{id}/ledger` · `/fees/collect` · `/receipts/{id}/pdf` ·
`/receipts/{id}/cancel-request` · `/approvals/{id}/decide` · `/verify/{code}` (public) ·
`/reports/*` · `/notices` · `/audit` · `/export/*` · `/me/data-export`.

### 5.4 Screens
Login, first-login wizard, forgot password · Admin: users & roles, setup · Office: student list,
student form, import wizard, change-request queue · Accounts: fee setup, collect fee,
receipt view, cancellations, reports · Principal: approvals inbox · Student: home, profile,
fees, receipts, notices · Public: Verify page.

### 5.5 Pull requests
| PR | Content |
|---|---|
| 1.1 | Users, Argon2 passwords, sessions, login/logout, `/me`, lockout, rate limits, audit log, `create_admin` script |
| 1.2 | RBAC permissions + scope checks + permission tests; replace `ADMIN_TOKEN` with real roles |
| 1.3 | 2-step verification (TOTP + recovery codes; admin reset for lost phones); password reset by emailed link; "My account" page (devices, login history) |
| 1.4 | Institution setup module + admin screens |
| 1.5 | Student records: CRUD, search, change requests, documents in Vercel Blob |
| 1.6 | Excel/CSV import with validation report; bulk student accounts; bulk promotion |
| 1.7 | Student first-login wizard + privacy consent |
| 1.8 | Fee heads, structures, demand generation, concessions (with approval), scholarships tracking |
| 1.9 | Fee collection transaction, receipt numbering, receipt PDF + QR, email receipt |
| 1.10 | Public Verify page; cancellation/refund approval with reversals |
| 1.11 | Opening balances import; accounts reports + Excel export |
| 1.12 | Student portal v1 (home, profile, fees, receipts, notices) |
| 1.13 | Notices v1 + email delivery |
| 1.14 | Audit viewer, data exports; demo seed (BCA, 3 years, 60 students); Playwright e2e |

**Delivered in the "Phase 1A" PR (1.1–1.3):** first System Admin is created at `/setup` with the
`SETUP_TOKEN` environment variable (instead of a `create_admin` script). Email OTP as a second
factor is deferred: TOTP plus one-time recovery codes covers the required roles, and email is not
a strong second factor when the same mailbox can reset the password. Students without an email
address on record reset through the office (temporary password). Reset emails need
`EMAIL_API_KEY`; without it the link is only written to the server log.

**Delivered in the "Phase 1B" PR (1.4–1.7):**
- Student photos and documents are stored in MongoDB (`files` collection, 2 MB per file, type
  checked from the file's bytes) behind `app/core/files.py`, instead of Vercel Blob. Files are
  served only through `/api/v1/files/{id}` to staff with `students.read` or the student
  themselves. **Before go-live:** move to Vercel Blob (private) or a bigger Atlas tier, since
  Atlas M0 has 512 MB in total.
- A student login is always created with the student record (Students screen or import); the
  Users API refuses `kind: student`, and student name/contact are edited only in the record.
- `students.read`: Principal, Office, Accounts, Admission Cell, Exam Cell. HOD / Faculty / Mentor
  get scoped access with class assignments in Phase 2; Admission Cell creates students through
  the Admissions module (Phase 3). The System Admin has no access to student records (spec §2.3).
- Import validates and creates in chunks of 50 (one transaction each); temporary passwords are
  returned once per chunk and never stored. Promotion moves a student at most once per academic
  year.
- The first-login steps (contact → privacy notice → language) are enforced by the frontend;
  consent is stored in `consents` with the notice version. Portal menu and home are translated.
- Collections added: `files`, `consents`, `imports` (expires after a day).

**Delivered in the "Phase 1C" PR (1.8–1.11):**
- Ledger types: demand, charge, opening_due, refund (owe more) and payment, concession,
  scholarship, opening_paid (owe less), plus reversal. Each entry has per-head lines; a
  student's balance and head-wise outstanding are always computed from entries.
- Fee structures are per (academic year, programme, year, category) with a default for "all
  other categories"; they lock once fees are charged from them. Late fee: one flat amount per
  overdue installment, applied by Accounts from the student's account (no automatic job yet —
  Vercel Cron reminders come with notices).
- All concessions, receipt cancellations and refunds go to the Principal (no "above a limit"
  threshold yet); the requester can never approve. A scholarship sanctioned after full payment
  leaves the student in credit, refunded through an approved refund.
- Receipt numbers come from `counters` (`receipt:<year>`) inside the collection transaction;
  tested with 12 concurrent cashiers. PDF uses fpdf2's built-in font, so it prints "Rs." rather
  than the rupee sign; first print ORIGINAL, later prints DUPLICATE, cancelled ones CANCELLED.
- Emailing a receipt sends a summary with the verify link (no PDF attachment yet).
- Verify page shows first name + initials and a partly hidden PRN, never the full record.
- Collections added: `fee_heads`, `fee_structures`, `ledger_entries`, `receipts`, `counters`,
  `approvals`, `scholarships`.

### 5.6 Acceptance criteria
- Office imports 60 students from Excel; errors are reported row by row; each student gets a login.
- A student signs in with PRN + temporary password, sets their own, accepts the privacy notice and sees the **correct balance**.
- A cashier collects a fee and gets a receipt PDF with a sequential number in < 3 s; **two cashiers collecting at the same moment never get the same number** (automated test).
- Scanning the receipt QR on a phone shows **Genuine** with masked details; after an approved cancellation it shows **Cancelled**.
- A student cannot open another student's profile, ledger or receipt through any endpoint (automated tests).
- Every money action appears in the audit log with who, when and why.

---

## 6. Phase 2 — Core ERP: academics (≈5 weeks)

**Goal:** the daily academic work — timetable, attendance, marks, results and certificates — runs in CollegeConnect.

### 6.1 Features

**Timetable**
- Weekly timetable per division; clash checks (faculty, room, division); substitutions and cancellations shown to students.

**Attendance — the 10-second flow (unique U9)**
- Faculty open "Today", tap the lecture, the class list opens with **everyone present**, tap the absentees, save. Target: < 10 s for 60 students.
- **Works offline:** saved to the phone and synced when back online, with conflict handling.
- Edits for 48 hours, then only via HOD approval (audited).
- Exemptions (medical, official duty) entered by the office.
- Student view: subject-wise %, day calendar, and **"you can miss N more / must attend the next N"**.
- Defaulter lists; automatic alerts to the student at 80% (warning) and 75% (critical), by email (SMS/WhatsApp in Phase 3).

**Internal marks & exams**
- Assessment scheme per subject (e.g. 2 unit tests + assignment + practical = 40).
- Grid entry by faculty with max-mark checks → publish to students → HOD approval → **Exam Cell lock** at the deadline.
- **University Upload Guard (unique U7):** before the university's deadline, a per-subject checklist of missing marks, marks above maximum, absent-but-marked and exam-form-ineligible students; export in the university's upload format; a dashboard of completion by department.
- Exam forms: which students must fill them, exam-fee status (from the fees ledger).
- Hall tickets: upload per student (from the university) or generate internal ones.

**Results**
- Import university results (CSV), publish, SGPA/CGPA, backlogs (ATKT) and revaluation tracking; result PDF in the student portal.

**Certificates (unique U2 + U6)**
- Student requests bonafide, character, fee-paid letter, TC, migration, NOC.
- Workflow: Requested → Verified → Signed → Ready, with a **promised date per type** (e.g. bonafide 2 working days, TC 7) shown to the student; **automatic escalation** to the Principal when overdue (daily cron).
- **No-dues check** before TC (fees in Phase 2; library/hostel added in Phase 3).
- Issued as PDF with certificate number and **QR → Verify page**.
- On TC: the student account becomes read-only.

**Portals**
- Student: attendance, timetable, marks, results, hall ticket, certificates.
- Faculty home (today's lectures, take attendance, marks tasks), HOD dashboard, Exam Cell console.

### 6.2 Data
`timetable_slots`, `substitutions`, `attendance_sessions`, `attendance_marks`, `exemptions`,
`assessment_schemes`, `marks`, `marks_locks`, `exam_forms`, `hall_tickets`, `results`,
`certificate_types`, `certificate_requests`, `certificates`.

### 6.3 Pull requests
| PR | Content |
|---|---|
| 2.1 | Timetable + clash detection + substitutions |
| 2.2 | Attendance API + faculty "take attendance" screen |
| 2.3 | Offline attendance (service worker + IndexedDB sync) |
| 2.4 | Attendance analytics, student view with "can miss / must attend", defaulters, email alerts |
| 2.5 | Assessment schemes + marks entry grid + publish + HOD approval + lock |
| 2.6 | University Upload Guard + university-format export |
| 2.7 | Exam forms + hall tickets |
| 2.8 | Results import, SGPA/CGPA, backlogs, revaluation |
| 2.9 | Certificate types, templates, request workflow, promised dates, escalation cron |
| 2.10 | Certificate PDFs + QR on the Verify page; TC → read-only account |
| 2.11 | Faculty home, HOD dashboard, Exam Cell console, student portal additions; e2e tests |

### 6.4 Acceptance criteria
- A faculty member marks attendance for 60 students in under 10 seconds, including in airplane mode, and it syncs when back online.
- A student sees exactly how many lectures they can miss in each subject.
- Two days before a mock university deadline, the Upload Guard lists every missing mark; after fixing, the export file passes the university format check.
- A bonafide certificate request shows its promised date, escalates automatically when late, and the issued PDF verifies by QR.

---

## 7. Phase 3 — Campus operations (≈7 weeks)

**Goal:** everything else the office runs, plus parents and online payments.

### 7.1 Features
- **Parent portal:** OTP login, child switcher, read-only fees/receipts/attendance/results/notices, certificate requests for the child. **Consent controls:** for students 18+, the student chooses what parents see; for under-18s, parental consent recorded at admission.
- **Online fee payment:** gateway checkout (UPI/cards/net banking), webhook verification, automatic receipt on success, daily reconciliation report, refund handling.
- **Messaging:** SMS and WhatsApp (DLT-approved templates) alongside email for fee reminders, attendance alerts, results, certificate ready; per-user preferences; delivery log.
- **Admissions:** enquiries, online application with documents and application fee, scrutiny, category-wise merit lists and rounds, confirmation → student record + login + first fee demand in one step, cancellation with refund rules.
- **Library:** catalogue (ISBN lookup), barcode issue/return, due dates, fines into the student ledger, reservations, overdue reminders.
- **Hostel:** blocks/rooms/beds, allotment, hostel fees into the ledger, out-pass requests with warden approval and parent notification, complaints.
- **Placement:** drives, eligibility rules (CGPA, backlogs, programme), student registration and resume, rounds, offers, statistics.
- **Grievance:** categories, optional anonymity, **SLA with escalation**, confidential handling for sensitive cases, closure feedback.
- **Staff & leave:** staff records and qualifications, leave types and balances, apply/approve, workload view. (Payroll is a later, separate project.)
- **No-dues** extended to library and hostel for TCs.

### 7.2 Pull requests
| PR | Content |
|---|---|
| 3.1 | Parent accounts, OTP login, linking, consent controls, parent portal |
| 3.2 | Payment gateway checkout + webhooks + automatic receipts + reconciliation |
| 3.3 | Messaging service (SMS/WhatsApp/email), templates, preferences, delivery log |
| 3.4 | Admissions: enquiry, application, documents, application fee |
| 3.5 | Admissions: merit lists, rounds, confirmation → student + login + fee demand |
| 3.6 | Library |
| 3.7 | Hostel + out-pass |
| 3.8 | Placement |
| 3.9 | Grievance with SLA |
| 3.10 | Staff records and leave |
| 3.11 | No-dues across modules; e2e tests |

### 7.3 Acceptance criteria
- A parent signs in with OTP and sees both of their children; an 18+ student turning off "marks" hides marks from the parent.
- A student pays online by UPI; the receipt appears automatically and the day book reconciles to the gateway report.
- Confirming an admission creates the student, their login and their fee demand with no re-typing.
- An overdue library book appears in the student's no-dues check and blocks a TC until cleared.

---

## 8. Phase 4 — Control, compliance and openness (≈4 weeks)

**Goal:** management sees the whole college; accreditation and government reporting come out of the system; the college owns its data.

### 8.1 Features
- **NAAC-ready by default (unique U8):** every record type is mapped to the NAAC criterion/metric it evidences; AQAR/SSR tables generated for a chosen year; evidence file links; gaps report ("Metric 2.4.1: 3 faculty records missing qualification proof").
- **Government reporting:** AISHE data sheet, NIRF data points, **APAAR/ABC ID** validation and credit export, DigiLocker/NAD-ready signed documents.
- **Dashboards:** Principal (admissions vs target, collection vs demand, attendance health, marks completion, certificate turnaround, pending approvals), HOD (department), Accounts (collections, receivables).
- **Early warning — rule-based and explainable (unique U10):** configurable rules (attendance trend, marks below threshold, fee overdue) produce a risk level **with the reasons listed**; visible only to the mentor, HOD and Principal; mentor counselling notes; never an automatic penalty.
- **Scholarship eligibility checker (unique U11):** rules for common scholarships (e.g. MahaDBT/NSP schemes: category, income limit, course, attendance) tell each student which ones they may qualify for and which documents are missing.
- **No lock-in (unique U12):** full data export (all collections, CSV/JSON, with a data dictionary), **open REST API** with API keys and scopes, published OpenAPI docs.
- **Operations hardening:** load test for fee/result days, backup restore drill, security review (OWASP Top 10).

### 8.2 Pull requests
| PR | Content |
|---|---|
| 4.1 | NAAC criterion mapping + AQAR tables + gaps report |
| 4.2 | AISHE / NIRF exports; APAAR/ABC validation and export |
| 4.3 | Principal / HOD / Accounts dashboards |
| 4.4 | Rule-based early warning + mentor workspace and notes |
| 4.5 | Scholarship eligibility rules + student view |
| 4.6 | Full export + data dictionary; API keys + OpenAPI docs |
| 4.7 | Load test, restore drill, security review fixes |

### 8.3 Acceptance criteria
- The AQAR tables for a year are generated in minutes, with a list of missing evidence.
- A mentor sees each at-risk mentee with the specific reasons, and the student never sees the risk label.
- The college can export all of its data in one click and re-import it into a fresh database.
- The system handles 2,000 students logging in within 15 minutes without errors.

---

## 9. Phase 5 — CollegeConnect AI (≈4 weeks)

**Goal:** the AI layer on top of a complete ERP — answers that use official documents **and** the user's own records, with citations, in three languages.

### 9.1 Features
- **Help desk inside the ERP:** the existing public help desk (`backend/app/rag/`) becomes the assistant panel in every portal; public mode unchanged.
- **Knowledge base in MongoDB:** move `index.json` into a `kb_chunks` collection (Atlas Vector Search when large); documents managed from the admin portal.
- **Self-publishing notices (unique U4):** publishing a notice **auto-translates** it to Hindi and Marathi (staff can edit before publishing) and **auto-indexes** it into the help desk; expiry removes it.
- **Ask my record (unique U1):** a signed-in student or parent asks "How much fee do I still owe?", "What is my attendance in DBMS?", "Is my bonafide ready?". The backend builds short, structured excerpts from **the caller's own records only** (fees, attendance, marks, certificates) and passes them with the document excerpts; the answer cites both ("Your fee account as of 4 Oct 2026"). The model never gets database access; personal excerpts are never logged.
- **Deadline radar (unique U3):** dates extracted from new notices ("exam form closes 15 Oct for SY BCA") become personal reminders for the students they apply to, checked by staff before going out.
- **Knowledge-gap loop (unique U5):** the existing analytics move into the Principal/Office dashboards; one click turns an unanswered question into a draft FAQ/notice.
- **Staff assistant:** "How many SY BCA students owe more than ₹10,000?" answered by running **pre-defined, permission-checked queries** and showing the numbers and the list behind them — never free-form database access.
- **Optional:** ML-based risk score alongside the Phase 4 rules (only if it measurably beats the rules, and with reasons shown); WhatsApp AI channel.

### 9.2 Pull requests
| PR | Content |
|---|---|
| 5.1 | Knowledge base in MongoDB + admin document management |
| 5.2 | Notices → auto-translation + auto-indexing |
| 5.3 | Assistant panel in all portals |
| 5.4 | Ask my record — fees and certificates |
| 5.5 | Ask my record — attendance and marks |
| 5.6 | Deadline radar |
| 5.7 | Knowledge-gap loop in dashboards |
| 5.8 | Staff assistant with permission-checked query tools |
| 5.9 | Evaluation set (cited-answer accuracy in EN/HI/MR) + privacy tests |

### 9.3 Acceptance criteria
- A student asks in Marathi "मला अजून किती फी भरायची आहे?" and gets the exact balance from their ledger, citing their fee account and the fee notice.
- No question, however phrased, returns another student's data (automated red-team tests).
- Publishing an English notice makes it answerable in Hindi and Marathi within a minute.
- Synopsis targets: ≥ 90% correct answers and 100% citation coverage on the evaluation set; answers in < 5 s.

---

## 10. Data migration and rollout

1. **Templates** for students, fee structures, opening balances and staff (Excel/CSV), each with a validation report before saving.
2. **Opening balances** imported as ledger entries of type `opening_balance`, keeping old receipt numbers as references.
3. **Pilot:** BCA for one term alongside the current process; then the whole college.
4. **Training:** 30-minute session per role, one-page guides, a "champion" in each office.

## 11. Operations

| Item | Plan |
|---|---|
| Environments | Production (`main`), Preview (every PR, separate database), Local |
| Secrets | Vercel environment variables only; rotated when someone leaves |
| Env vars | `MONGODB_URI`, `SESSION_SECRET`, `BLOB_READ_WRITE_TOKEN`, `EMAIL_API_KEY`, `CRON_SECRET` (P1); SMS/WhatsApp and payment keys (P3); `ANTHROPIC_API_KEY`, `VOYAGE_API_KEY` (P5, already used by the help desk) |
| Backups | Daily, 30-day retention, restore drill each term |
| Monitoring | Vercel logs and alerts; `/api/health` checks database, storage and (P5) AI |
| Incidents | Written runbook incl. DPDP breach notification |

## 12. Risks

| Risk | Mitigation |
|---|---|
| Money errors | Ledger-only balances, transactions, concurrency tests, reversals instead of edits |
| One student seeing another's data | Scope checks in the service layer, tests on every endpoint |
| Peak load on fee/result days | Indexes, caching, load test in Phase 4 |
| Staff don't adopt it | 10-second flows, BCA pilot, champions per office |
| Free-tier limits | Vercel Pro and an Atlas tier with backups before go-live |
| Scope creep | Each phase ships on its own; new ideas go to the next phase's list |
| AI mistakes (Phase 5) | Citations always shown, "no source → no answer", evaluation set, weekly gap review |

## 13. Next steps

1. Confirm decisions **D1–D7** in the product spec.
2. Start **Phase 0** (PR 0.1 CI → 0.4), then **PR 1.1** (logins).
