# CollegeConnect — Product Specification

> **Status:** Draft v2 · **Owner:** Aniket Pitre · **Last updated:** 2026-10-04
>
> CollegeConnect is a college ERP (Enterprise Resource Planning) system for an Indian
> undergraduate college, with an AI help desk built in. This document describes **what** we
> are building: who logs in, what each person can do, and every module's features.
> **How** we build it is in [02-implementation-plan.md](02-implementation-plan.md).

---

## 1. Vision

Students should never have to stand in a queue to find out something the college already
knows. Office staff should never type the same data twice. Accreditation should be a report,
not a project.

CollegeConnect does what college ERPs already do (admissions, fees, attendance, exams,
certificates, accounts) and adds three things they don't:

1. **An AI help desk that answers from official documents *and* the student's own record**, with
   a citation for every answer, in English, Hindi and Marathi.
2. **Self-service with proof:** every receipt and certificate carries a QR code that anyone can
   scan to verify it is genuine, and every request has a visible deadline.
3. **Built for how Indian colleges actually work:** semesters, an affiliating university's
   calendar and deadlines, category-wise fees and scholarships, NAAC/AISHE reporting, the
   DPDP Act 2023 — on a phone, not just on the office PC.

### 1.1 Design principles

| Principle | What it means in practice |
|---|---|
| **Mobile first** | Every student and faculty screen works on a ₹10,000 Android phone on 4G. Office screens are desktop-first but still usable on a tablet. |
| **Three languages** | Every student- and parent-facing screen is available in English, Hindi and Marathi. Staff screens are English first. |
| **Enter once** | Data typed once (e.g. a student's category) flows everywhere it's needed (fees, scholarships, AISHE). |
| **Nothing is deleted silently** | Money and marks are never edited in place; corrections are new entries that reference the old one, with a reason. Everything is in the audit log. |
| **Least privilege** | Each login sees only what its role needs; a student only ever sees their own data. |
| **Cited, not guessed** | The AI never answers without a source; if there is no source it says so. |
| **Your data is yours** | The college can export all of its data at any time in open formats (CSV/JSON). |

### 1.2 Out of scope (for now)

- A full LMS (course content, video lectures, online tests). We link out to Google Classroom / Moodle.
- Multi-college groups and multiple campuses (designed for, not built in v1).
- Full statutory payroll (PF/ESI/TDS returns). v1 keeps staff records and leave; payroll comes later.
- Running the university's own examinations (setting papers, central assessment). We handle the
  **college's** side: internal marks, exam forms, hall-ticket distribution and results display.

---

## 2. Users and logins

### 2.1 Login methods (all roles)

| Item | Decision |
|---|---|
| **Staff login** | Email + password. Accounts are created by the System Admin; no self sign-up. |
| **Student login** | **PRN / enrolment number + password.** The office creates the account at admission with a one-time temporary password, printed on the admission slip or sent by SMS/email. The student must set their own password at first login. *(Default — see Decision D3.)* |
| **Parent login** | Mobile number + OTP, or mobile number + password. A parent account is linked to one or more students by the office; one parent can see all their children. |
| **Public (no login)** | The home page (sign-in panels for each kind of user, admission link, what CollegeConnect AI does) and the **Verify** page for receipts/certificates. CollegeConnect AI itself needs a sign-in (decision of October 2026). |
| **Password rules** | At least 10 characters; checked against a list of common passwords; no forced periodic expiry (per current NIST guidance). |
| **Two-step verification** | Required for any role that can touch money, marks or user accounts (System Admin, Principal, Accounts, Exam Cell). Email or authenticator-app code. Optional for everyone else. |
| **Forgot password** | Student/parent: OTP to registered mobile or email. Staff: reset link to registered email. If neither is on file, the office resets it in person after checking ID. |
| **Lockout** | 5 wrong passwords → 15-minute lock and an alert to the user. |
| **Sessions** | Students/parents stay signed in for 30 days on their own device; staff for 12 hours. "Sign out of all devices" is available to everyone. |
| **Account lifecycle** | Student accounts become **read-only** when a TC is issued or the student graduates (they can still download receipts and certificates for 2 years), then are archived. Staff accounts are disabled the day they leave. |
| **Audit** | Every sign-in, failed sign-in, password reset and permission change is logged with time, IP and device. |

### 2.2 Roles at a glance

A person can hold more than one role (e.g. a faculty member who is also a Mentor and the
Hostel Warden); their dashboard combines them.

| # | Role | Who | Scope of data |
|---|---|---|---|
| R1 | **System Admin** | IT in-charge | Whole system configuration; no access to marks/fees edits without the matching role |
| R2 | **Principal / Management** | Principal, Vice-Principal, Trustees | Read everything, approve high-impact actions |
| R3 | **Office Admin (Registrar)** | Office superintendent, clerks | Student records, admissions, certificates, notices |
| R4 | **Accounts** | Accountant, cashier | Fees, receipts, refunds, scholarships, day book |
| R5 | **Admission Cell** | Admission in-charge | Enquiries, applications, merit lists, admission confirmation |
| R6 | **Exam Cell** | Exam in-charge | Exam forms, internal marks lock, university upload, results, hall tickets |
| R7 | **HOD** | Head of each department | Their department's classes, faculty, attendance and marks |
| R8 | **Faculty** | Teaching staff | Their own timetable, the classes/subjects they teach |
| R9 | **Mentor** | Faculty assigned ~20 mentees | Their mentees' attendance, marks, fee status and alerts |
| R10 | **Librarian** | Library staff | Library catalogue, issue/return, fines |
| R11 | **Hostel Warden** | Warden | Hostel rooms, allotments, hostel fees status, leave/out-pass |
| R12 | **Placement Officer** | T&P officer | Drives, eligibility, registrations, offers |
| R13 | **Student** | Enrolled students | **Only their own** data |
| R14 | **Parent / Guardian** | Parent of an enrolled student | Their linked children's data (subject to DPDP rules, §4.2) |
| R15 | **Public** | Anyone | Home page, admission application, Verify page (the AI help desk needs a sign-in) |

### 2.3 What each login can do

Legend: **C** create · **R** read · **U** update · **A** approve · **—** no access. "Own" =
only the user's own records; "Dept" = only their department; "Assigned" = only classes they
teach or mentees assigned to them.

| Capability | Sys Admin | Principal | Office | Accounts | Admission | Exam | HOD | Faculty | Mentor | Student | Parent |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Institution setup (years, programmes, fee heads) | CRU | R/A | R | R (fees) | R | R | R | — | — | — | — |
| User accounts & roles | CRU | R/A | C (students) | — | — | — | — | — | — | — | — |
| Admissions & applications | — | R/A | R | R | CRU | — | R (Dept) | — | — | Own (applicant) | — |
| Student master record | — | R | CRU | R | CR | R | R (Dept) | R (Assigned) | R (Assigned) | R Own + request change | R (child) |
| Fee structure & concessions | — | A | R | CRU | R | — | — | — | — | R Own | R (child) |
| Collect fee & issue receipt | — | R | — | C | — | — | — | — | — | — | — |
| Cancel receipt / refund | — | **A** | — | C (request) | — | — | — | — | — | — | — |
| View fee ledger & receipts | — | R | R | R | — | — | — | — | R (Assigned, status only) | R Own | R (child) |
| Timetable | — | R | CRU | — | — | R | CRU (Dept) | R | R | R Own | R (child) |
| Attendance | — | R | R | — | — | R | R (Dept) / U | CU (Assigned) | R (Assigned) | R Own | R (child) |
| Internal marks | — | R | — | — | — | R / lock / A | R / A (Dept) | CU (Assigned, until locked) | R (Assigned) | R Own (after publish) | R (child) |
| Results & marksheets | — | R | R | — | — | CRU / publish | R (Dept) | R (Assigned) | R (Assigned) | R Own | R (child) |
| Certificate requests | — | A (TC) | CRU / issue | R (no-dues) | — | — | A (some) | — | — | C / R Own | C / R (child) |
| Notices | CRU | CRU | CRU | C (fee notices) | C | C | C (Dept) | C (own class) | — | R | R |
| AI help desk | config | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ + "Ask my record" | ✓ + child's record |
| Admin analytics / knowledge gaps | R | R | R | — | — | — | R (Dept) | — | — | — | — |
| Audit log | R | R | — | — | — | — | — | — | — | — | — |
| Data export | C | A | — | — | — | — | — | — | — | Own data | — |

Library, hostel and placement roles have full rights inside their module and read-only access
to the student fields they need (name, class, photo, contact).

### 2.4 Each login in detail

#### R13 — Student (the most important login)

**First login:** PRN + temporary password → set new password → confirm mobile/email →
accept the privacy notice (what data the college holds and why, per DPDP Act) → pick language.

**Home screen (phone):**
- Greeting, photo, programme / year / division, academic year.
- **"Needs your attention" cards**, ordered by urgency: fee due in 5 days, attendance below 75%
  in Maths, exam form closes Friday, bonafide certificate ready to collect.
- Today's timetable.
- Latest 3 notices for *their* class.
- The **Ask CollegeConnect** box, always visible.

**Menu:**

| Section | What the student can do |
|---|---|
| **My profile** | View personal, academic, contact and category details; request a correction (goes to the office with a reason; the office approves); upload/replace photo and documents. |
| **Fees** | See fee structure for their year; installments with due dates; amount paid, concessions and scholarships applied, **balance due**; full payment history; download every **receipt (PDF with QR)**; download a **fee statement** for a date range (for scholarships or loans); later: pay online. |
| **Attendance** | Subject-wise percentage, with a clear "you can miss N more lectures and stay above 75%" / "you must attend the next N lectures" figure; day-by-day calendar view. |
| **Timetable** | Weekly timetable; today's changes and cancelled lectures. |
| **Exams & results** | Internal marks per subject (after the teacher publishes them); exam form status; hall ticket download; semester results and SGPA/CGPA; revaluation request window. |
| **Certificates** | Request bonafide, character, fee-paid letter, TC, migration, etc.; see status like a parcel tracker (Requested → Verified → Signed → Ready) with a promised date; download the signed PDF with QR. |
| **Notices** | All notices for their class/programme/college, searchable, in their language. |
| **Library** | Books issued, due dates, fines. *(Phase 3)* |
| **Hostel** | Room, roommates, hostel fee status, apply for out-pass. *(Phase 3)* |
| **Placement** | Upcoming drives they are eligible for, register, upload resume. *(Phase 3)* |
| **Grievance** | Raise a complaint (optionally anonymous to the department), track it. *(Phase 3)* |
| **Ask CollegeConnect** | Ask anything about rules and notices (available from day one: the existing help desk). **Phase 5:** also about their own record — "How much fee do I still owe?", "What is my attendance in DBMS?", "When is my exam form due?" — each answer cites the notice and/or "Your fee account as of 4 Oct". |
| **My data** | Download a copy of all their personal data (DPDP Act right to access); manage parent access consent (§4.2). |

**A student can never:** see another student's data, edit marks/attendance/fees, or see staff-only notes.

#### R14 — Parent / Guardian

- Same layout as the student, read-only, with a **child switcher** if they have more than one child at the college.
- Sees: fees and receipts, attendance, published marks and results, notices, certificate status.
- Can: download receipts, raise certificate requests on behalf of the child, and (Phase 5) ask CollegeConnect about the child's record.
- Receives: fee-due reminders, low-attendance alerts, result publication alerts (SMS/WhatsApp/email).
- For a student **aged 18+**, the student controls what the parent sees (default: fees + attendance + results on; can be changed). For a student **under 18**, the parent account is required and parental consent is recorded at admission (DPDP Act §9).

#### R8 — Faculty

**Home:** today's lectures with a one-tap **Take attendance** button on each; pending tasks
("Internal marks for BCA-SY-A DBMS due in 3 days"); notices.

| Feature | Detail |
|---|---|
| **Attendance in ~10 seconds** | Opens the class list with everyone marked present; tap absentees; save. Works offline and syncs later. Can mark for a substitute lecture. Edits allowed for 48 hours, after that only via HOD. |
| **Internal marks** | Enter marks per assessment (unit test, assignment, practical) in a grid; the system validates max marks and flags missing students; publish to students; marks lock on the Exam Cell's deadline. |
| **My classes** | Student list with photo, attendance %, marks; export to Excel. |
| **Timetable** | Own weekly timetable; request a swap. |
| **Notices** | Post a notice to their own class (auto-translated from Phase 5). |
| **Leave** | Apply for leave; see balance. *(Phase 3)* |

#### R9 — Mentor (a faculty member with mentees)

- **Mentee list** with a traffic light per student: attendance, marks trend, fee dues.
- **Early-warning alerts** with plain reasons ("Attendance dropped from 82% to 61% in 3 weeks; 2 internal tests below 40%").
- Record a counselling note (private to mentor, HOD and Principal; never visible to the student's classmates; student can see that a meeting happened, not the private notes).
- Alerts are suggestions for a human, never automatic penalties.

#### R7 — HOD

- Everything a faculty member sees, for the whole department.
- Department dashboard: attendance by class/subject, defaulters list (<75%), internal-marks completion by subject, faculty workload.
- Approves: attendance edits after 48 hours, internal marks before they are locked, department-level certificates.
- Builds the department timetable.

#### R3 — Office Admin (Registrar / clerks)

**Home:** work queue — new certificate requests, profile-correction requests, documents to verify, today's admissions.

| Feature | Detail |
|---|---|
| **Student records** | Create/edit student master records; bulk import from CSV/Excel; promote a whole class to the next year; divisions and roll numbers; mark TC/left/graduated. |
| **Student accounts** | Create login, reset password, link parent. |
| **Documents** | Verify uploaded documents (marksheets, caste certificate, Aadhaar-masked copy); mark verified/rejected with a reason. |
| **Certificates** | Process requests: auto-filled from the student record → check → send for signature → issue (PDF with QR) or print. Fixed formats for bonafide, character, TC, migration, fee-paid letter, NOC. |
| **Notices** | Publish notices (upload PDF or type), choose audience (all / programme / year / division / staff), set expiry. Hindi/Marathi versions typed by staff; from Phase 5 the system translates them and adds the notice to the AI help desk automatically. |
| **Reports** | Class lists, category-wise counts, gender/age statistics, AISHE data sheet. |

#### R4 — Accounts

**Home:** today's collection by mode (cash / UPI / card / bank), receipts issued, pending cancellations, overdue students count.

| Feature | Detail |
|---|---|
| **Fee structures** | Define fee heads (tuition, development, exam, library, gymkhana, hostel…), amounts per programme × year × category (Open / OBC / SC / ST / EWS…), installments with due dates, late-fee rule. Versioned per academic year. |
| **Concessions & scholarships** | Apply a concession (staff ward, sibling, merit) with approval; record government scholarships (e.g. MahaDBT / NSP) as expected → sanctioned → received, and adjust what the student owes. |
| **Collect fee** | Search student by PRN/name → see dues → enter amount, mode and reference (UPI ref, cheque no.) → **receipt generated instantly** (sequential number per year, PDF with QR) → print or send by SMS/email/WhatsApp. |
| **Cancel / refund** | Never edit a receipt. Cancellation creates a reversal entry with a reason and needs Principal approval; refunds the same. |
| **Day book & reports** | Day book, head-wise collection, mode-wise collection, outstanding dues by class, scholarship receivables; export to Excel/Tally. |
| **Reminders** | Bulk fee reminders to defaulters (SMS/WhatsApp/email) with their exact balance. |
| **Online payments** | Reconcile gateway payments automatically. *(Phase 3)* |

#### R5 — Admission Cell

- Enquiries (walk-in, phone, website, the AI help desk) with follow-up status.
- Online application form → document upload → application fee.
- Merit list per programme with category-wise seats (reservation rules configurable).
- Confirm admission → creates the student record, the student login and the first fee demand in one step.
- Admission reports (applications vs confirmed by programme/category).

#### R6 — Exam Cell

- Exam calendar (internal and university).
- **Internal marks control:** deadlines per subject, completion dashboard, lock marks, and the **University Upload Guard** (§3.8) before the university's deadline.
- Exam forms: which students must fill them, who has paid exam fees, export for the university portal.
- Hall tickets: upload the university's hall tickets or generate internal ones; distribute to students.
- Results: import university results (CSV), publish to students, compute SGPA/CGPA, track backlogs and revaluation.

#### R2 — Principal / Management

- **Dashboard:** admissions vs target, fee collection vs demand, attendance health, internal-marks completion, pending approvals, certificate turnaround time, help-desk usage and knowledge gaps.
- Approves: receipt cancellations/refunds, concessions above a limit, TCs, data exports.
- Reads everything; edits nothing directly (by design).

#### R1 — System Admin

- Users and roles, two-step verification enforcement, password resets for staff.
- Institution settings: college name/logo/address, academic years, programmes, departments, divisions, numbering formats, SMS/email/WhatsApp credentials.
- AI help desk configuration: knowledge base documents, re-index.
- Audit log viewer, data export, backups status.
- **Cannot** change marks or money (separation of duties): those need the Exam Cell / Accounts roles.

#### R10–R12 — Librarian, Hostel Warden, Placement Officer *(Phase 3)*

Each gets a self-contained workspace: library catalogue and circulation; hostel rooms,
allotment, out-pass approvals; placement drives, eligibility rules, registrations and offers.
Their data feeds the student portal and the AI help desk ("Is my library book overdue?").

#### R15 — Public (no login)

- **Home page**: sign-in panels for students, parents and staff, the admission link, and what CollegeConnect AI does. Asking CollegeConnect needs a sign-in (October 2026).
- **Verify a document:** scan the QR on a receipt or certificate → see "Genuine: Receipt R/2026-27/001234, ₹25,000, 12 Aug 2026, issued to A•••• P•••• (PRN ••••5678)" or "Not found / cancelled". Shows only masked details.
- **Apply for admission** (Phase 3).

---

## 3. Modules and features

Each module lists its features, its rules, and the phase it ships in (see the implementation
plan). Build order: **core ERP first (P1–P2), then other features (P3–P4), CollegeConnect AI
last (P5)**. **P1** = Phase 1 … **P5** = Phase 5.

### 3.1 Institution setup — P1
- Academic years (e.g. 2026-27) with start/end and the "current year" switch.
- Departments, programmes (BCA, BCom, BSc…), years (FY/SY/TY), divisions (A/B), semesters.
- Subjects per programme-semester with credits, type (theory/practical), max internal/external marks.
- Student categories (Open, OBC, SC, ST, VJ/NT, SBC, EWS…) and quotas.
- Numbering formats (PRN, receipt number, certificate number).
- Holidays calendar.

### 3.2 Admissions — P3
- Enquiry capture (incl. from the AI help desk: "Leave your number and we'll call you").
- Online application with document upload; application fee.
- Scrutiny and document verification.
- Merit lists by programme and category; rounds; waiting list.
- Confirmation → creates student, login and first fee demand automatically.
- Cancellation of admission with refund rules.

### 3.3 Student Information System (SIS) — P1
- Student master: personal, contact, guardian, address, category, Aadhaar (stored **masked**; full number only if legally required), ABC/APAAR ID, previous education, photo, documents.
- Academic placement: programme, year, division, roll number, PRN, admission date, status (active / TC / graduated / dropped / detained).
- Bulk import from Excel/CSV with validation report; bulk promotion at year end.
- Change requests from students, approved by the office, with history.
- Full history: every change who/when/why.

### 3.4 Fees and accounts — P1 (online payment P3)
- **Fee heads and structures** per academic year × programme × year × category, with installments, due dates and late-fee rules.
- **Fee demand**: generated per student from the structure, minus concessions.
- **Concessions** with approval workflow and reason.
- **Scholarships**: expected / sanctioned / received tracking; student owes the difference.
- **Collection** at the counter (cash, UPI, card, cheque/DD, bank transfer) with reference numbers.
- **Receipts**: sequential, gap-free number per academic year; PDF with college letterhead, student details, head-wise breakup, amount in words, mode, collector, **QR verify link**; reprints are marked "Duplicate".
- **Ledger**: each student's running account (demands, payments, concessions, scholarships, reversals). Money stored in **paise** as whole numbers; never floating point.
- **Cancellations and refunds** only via reversal entries with Principal approval.
- **Reports**: day book, head-wise, mode-wise, class-wise outstanding, defaulters, scholarship receivable; Excel/Tally export.
- **Reminders** to defaulters with exact balance.
- **Online payment** via a payment gateway (UPI/cards/net banking) with automatic reconciliation — P3.

### 3.5 Student portal — P1 (grows each phase)
See §2.4 R13. P1 ships: profile, fees, receipts, notices, and a link to the existing help desk. P2 adds attendance, timetable, marks, results, certificates. P3 adds library, hostel, placement, grievance, online payment. P5 adds "Ask my record".

### 3.6 Parent portal — P3
See §2.4 R14.

### 3.7 Timetable and attendance — P2
- Weekly timetable per division; faculty and room clash detection; substitutions.
- Lecture-wise attendance (faculty), daily rollups, subject-wise percentage.
- Rules: minimum % (default 75%), medical/official-duty exemptions entered by the office.
- Defaulter lists; automatic alerts to student, parent and mentor at configurable thresholds (e.g. 80% warning, 75% critical).
- "Lectures you can miss / must attend" calculator for students.

### 3.8 Examinations and results — P2
- Assessment schemes per subject (e.g. 2 unit tests + assignment + practical = 40 internal marks).
- Marks entry by faculty, approval by HOD, lock by Exam Cell.
- **University Upload Guard:** before the affiliating university's internal-marks deadline, a checklist per subject shows: students with missing marks, marks above maximum, absent-but-marked, and students not eligible for the exam form. Exports in the university's format.
- Exam forms and exam fee tracking.
- Hall tickets distribution.
- Result import (CSV from the university), publishing, SGPA/CGPA, backlogs (ATKT), revaluation tracking.

### 3.9 Certificates and documents — P2
- Request → verify → sign → issue workflow with a **promised date** (e.g. bonafide 2 working days, TC 7) and automatic escalation to the Principal when late.
- Templates: bonafide, character, fee-paid, TC, migration, NOC, internship letter.
- **No-dues check** before TC: fees, library, hostel, lab equipment.
- Issued as a PDF with QR verify code and certificate number; option to print on letterhead.
- Public **Verify** page (masked details).

### 3.10 Notices and communication — P1 (channels grow; AI in P5)
- Create notice (text or PDF), audience targeting, schedule, expiry, pin.
- **Auto-translation** to Hindi and Marathi (staff can edit the translation before publishing) — P5; until then staff type translations.
- **Auto-indexed into the AI help desk** the moment it is published; removed when it expires — P5.
- Channels: in-app (P1), email (P1), SMS and WhatsApp (P3).
- Read receipts for important notices.

### 3.11 CollegeConnect AI — for signed-in people only (since October 2026)
- **Help desk** (built): cited answers from official documents in 3 languages, in the Ask panel of every portal. It was public until October 2026; the home page now shows sign-in panels instead, and asking needs a sign-in (applicants get the documents marked for them).
- **Ask my record** (P5): when signed in, answers use the student's own data plus the documents, and cite both.
- **Deadline radar** (P5): extracts dates from notices and turns them into per-student reminders.
- **Knowledge gaps** (built as a separate admin page; moved into the ERP dashboards in P5): unanswered questions shown to the office.
- **Staff assistant** (P5): "How many SY BCA students have fees pending above ₹10,000?" answered from the ERP with the data behind it.
- **Guard-rails:** never reveals another person's data; never answers without a source; every question logged without personal data.

### 3.12 Library — P3
Catalogue (ISBN lookup), issue/return with barcode, due dates, fines into the student ledger, reservations, overdue reminders.

### 3.13 Hostel — P3
Blocks, rooms, beds; allotment; hostel fees into the ledger; out-pass/leave requests approved by the warden with parent notification; mess and complaints.

### 3.14 Placement — P3
Company drives, eligibility rules (CGPA, backlogs, programme), student registration and resumes, rounds, offers, placement statistics for NAAC/NIRF.

### 3.15 Grievance — P3
Categories (academic, fees, harassment, infrastructure), optional anonymity, SLA with escalation, Internal Complaints Committee confidentiality for sensitive cases, closure feedback.

### 3.16 HR and staff — P3 (payroll later)
Staff records, qualifications, appointments, leave types and balances, leave approval, workload. Payroll in a later phase.

### 3.17 Accreditation and compliance — P4
- Every record is tagged to the NAAC criterion it serves, so AQAR/SSR tables are generated, not compiled.
- AISHE data sheet, NIRF data points.
- APAAR/ABC ID capture and validation; credit data export.
- DigiLocker/NAD readiness (digitally signed documents).

### 3.18 Analytics and early warning — P4 (optional ML in P5)
- Principal and HOD dashboards.
- Early-warning level per student from **configurable rules** (attendance trend, marks trend, fee dues), **with the reasons shown**, visible only to mentor/HOD/Principal. No automated decisions. An ML score may be added in P5 only if it measurably beats the rules.
- **Scholarship eligibility checker:** rules for common schemes (e.g. MahaDBT/NSP) show each student which scholarships they may qualify for and which documents are missing.

### 3.19 Audit, privacy and data export — P1 onwards (open API in P4)
- Append-only audit log of every create/update/approve on money, marks, records and roles.
- DPDP Act: privacy notice and consent records, parental consent for minors, right to access/correct, data retention schedule, breach response plan.
- Full data export (CSV/JSON) for the college; personal data download for students.

---

## 4. Cross-cutting requirements

### 4.1 Non-functional

| Area | Target |
|---|---|
| Speed | Pages load in < 2 s on 4G; AI answers in < 5 s (synopsis target) |
| Peak load | Results day and fee deadline: 2,000 students in 15 minutes without errors |
| Availability | 99.5% during college hours |
| Devices | Android Chrome, iOS Safari, desktop Chrome/Edge; works at 360 px width |
| Accessibility | Keyboard usable, readable contrast, screen-reader labels |
| Languages | EN / HI / MR for student and parent screens and all generated notices |
| Backups | Daily database backup kept 30 days; restore tested every term |
| Security | HTTPS only; passwords hashed; 2-step verification for sensitive roles; OWASP Top 10 reviewed each phase |

### 4.2 Privacy (DPDP Act 2023 and Rules 2025)
- Collect only what is needed; say why in the privacy notice.
- Under-18 students: verifiable parental consent at admission; no behavioural profiling except for educational purposes and safety (as the rules permit for educational institutions).
- Students can download their data and request corrections.
- Aadhaar stored masked; documents in private storage, accessed through short-lived links.
- AI help desk logs never store personal record contents, only the question and which document answered it.
- Retention: student records per university/government norms; help-desk logs 1 year.

---

## 5. Unique features (what other college ERPs lack)

| # | Feature | Why it matters | Phase |
|---|---|---|---|
| U2 | **QR-verifiable receipts and certificates** with a public Verify page | Stops forged receipts and certificates | P1 (receipts), P2 (certificates) |
| U9 | **10-second attendance** that works offline | Faculty actually use it | P2 |
| U7 | **University Upload Guard** for internal marks | No student's result withheld because of a missing mark | P2 |
| U6 | **Certificates with a promised date** and automatic escalation | Visible accountability instead of "come tomorrow" | P2 |
| U12 | **No lock-in** — full export and open API | The college owns its data | P1 (export), P4 (API) |
| U8 | **NAAC-ready by default** | Accreditation becomes a report | P4 |
| U10 | **Explainable early warning** (rule-based), privacy-safe | Mentors act early, students aren't profiled | P4 |
| U11 | **Scholarship eligibility checker** | Fewer missed scholarships | P4 |
| U4 | **Self-publishing notices** — auto-translated and auto-indexed into the AI | One upload reaches everyone in their language | P5 |
| U1 | **Ask my record** — cited AI answers from the student's own data + official documents, in 3 languages | Replaces the most common office queue questions | P5 |
| U3 | **Deadline radar** — personal deadlines extracted from notices | Students stop missing exam-form and fee deadlines | P5 |
| U5 | **Knowledge-gap loop** — unanswered questions tell the office what to publish | The help desk improves itself | P5 (exists as a separate admin page today) |

---

## 6. Decisions (confirmed 2026-10-04)

Confirmed by the project owner on 2026-10-04. Changing one later means updating this table and the plan in the same PR.

| # | Question | Decision |
|---|---|---|
| D1 | Which university is the college affiliated to? | An affiliating state university (e.g. SPPU-style): internal marks uploaded to the university portal, semester pattern, ATKT rules |
| D2 | Which programmes first? | BCA (FY/SY/TY), then BCom and BSc |
| D3 | Student login method | PRN + password set at first login; OTP reset |
| D4 | Fees in Phase 1 | Counter collection recorded by Accounts (cash/UPI/cheque); online payment in Phase 3 |
| D5 | Receipt number format | `R/<YYYY-YY>/<6-digit sequence>`, gap-free per academic year |
| D6 | Minimum attendance | 75%, warning at 80% |
| D7 | Hosting | Vercel only (frontend and FastAPI backend as two services on one domain) + MongoDB Atlas. No separate backend host. Production needs Vercel Pro (Hobby is for non-commercial use) and an Atlas tier with backups |
