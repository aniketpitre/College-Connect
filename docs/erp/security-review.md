# Security review (Phase 4, plan 4.7)

Reviewed against the OWASP Top 10 (2021) on the code as of Phase 4C, October 2026. Each item
says what protects the system today, what this review changed, and what remains for the
college to do. Fixes are in the "Phase 4D" pull request.

## Summary of changes made in this review

| # | Finding | Risk | Fix |
|---|---|---|---|
| 1 | The client address for rate limits and the audit log was read from `X-Forwarded-For`, which a client can set to anything: per-IP limits on sign-in, OTP, password reset and enquiries could be dodged by changing the header on each request. | Medium | `client_ip` uses `X-Real-IP` (set by Vercel, not the client) or the socket address; `X-Forwarded-For` is ignored. |
| 2 | CORS allowed any `http://localhost:*` page to call the API with the user's cookies, in production too. A page served from a person's own machine could read their records. | Low–medium | Localhost origins are allowed only off Vercel (`ALLOW_LOCALHOST_ORIGINS`, default on locally, off when `VERCEL` is set). |
| 3 | No Content-Security-Policy on the web app; a script injected through any future bug could load code from anywhere. | Medium (defence in depth) | Production builds carry a CSP: own code and API, Google Fonts, Razorpay checkout only; `object-src 'none'`, `base-uri 'self'`, `form-action 'self'`. Checked in a browser on the built app (student, office, HOD pages, help desk): no blocked resources. |
| 4 | API JSON had no CSP or HSTS; no Permissions-Policy. | Low | JSON responses: `default-src 'none'; frame-ancestors 'none'`. All responses: `Strict-Transport-Security` (when cookies are secure, i.e. HTTPS) and `Permissions-Policy` (no camera, microphone, location). PDFs are left alone so the browser's viewer still opens receipts and certificates. |
| 5 | NAAC intake settings took any text as a key of a stored document (keys become MongoDB field names). | Low | Only programme ids (24 hex characters) and non-negative numbers are accepted. |
| 6 | A development-only build dependency (`source-map-js`, via Vite) had a high-severity advisory (denial of service with crafted source maps). Not shipped to users. | Low | Updated in `package-lock.json`; `npm audit` and `pip-audit` now report no known vulnerabilities. |
| 7 | (Found during the load-test work in Phase 4B) 30 sign-ins per IP per 15 minutes would lock out a whole lab or campus Wi‑Fi. | Availability | `LOGIN_LIMIT_PER_IP`, default 300; wrong passwords are still limited per account. |

## OWASP Top 10 walk-through

**A01 Broken access control.** Every route declares a permission (`require(P.X)`) or checks
scope in the service layer (department, mentees, own record, linked child). Students and
parents reach only their own (or child's) data; parents through an allow-list (`parents/guard.py`)
and applicants through `admissions/guard.py`. Confidential areas have tests that the wrong people
get 403/404: sensitive grievances (ICC only), early warning (mentor/HOD/Principal only, never the
student or their data export), anonymous grievances (no name even in the audit log). API keys are
read-only and scoped. *No change needed.*

**A02 Cryptographic failures.** Passwords: Argon2id. Session, reset and API-key tokens: 256-bit
random, stored only as SHA-256 hashes. 2-step secrets: encrypted with `APP_SECRET_KEY`. Session
cookie: `HttpOnly`, `Secure`, `SameSite=Lax`. Aadhaar: only the last 4 digits are stored. Full
exports leave out password hashes and 2-step secrets. *Changed: HSTS header (item 4).*

**A03 Injection.** All request bodies are typed Pydantic models, so a body can't smuggle MongoDB
operators into a query. Every search that builds a regular expression escapes the input
(`re.escape`). No raw query strings or `eval`. React escapes all text; there is no
`dangerouslySetInnerHTML`. Uploaded files are served with `Content-Security-Policy: sandbox`.
*Changed: item 5.*

**A04 Insecure design.** Money is an append-only ledger with reversal entries; receipt numbers
are gap-free under concurrency (tested); approvals need a second person (the Principal). Rate
limits on sign-in, OTP, password reset, MFA, payments, enquiries and API keys. *No change needed.*

**A05 Security misconfiguration.** Errors never return stack traces (`{"error": {...}}` with a
generic message for 500s). Default demo data refuses the production database name. *Changed:
items 2, 3, 4.*

**A06 Vulnerable and outdated components.** `npm audit` (production and dev) and `pip-audit`
clean after item 6. Keep running both before each release.

**A07 Identification and authentication failures.** Same error and timing for unknown accounts
and wrong passwords; account lockout after repeated failures; forced password change on first
sign-in; 2-step verification required for Principal, Accounts, Exam Cell and System Admin;
password reset links expire in 30 minutes and only the newest works; reset requests answer the
same whether or not the account exists. *Changed: item 1 (per-IP limits can no longer be dodged).*

**A08 Software and data integrity failures.** Razorpay webhooks are checked with the HMAC
signature; the daily job needs `CRON_SECRET`; receipts and certificates carry verify codes. Full
export/restore keeps exact types (Extended JSON). *No change needed.*

**A09 Security logging and monitoring failures.** Every change of record goes through
`audit.record` (who, what, when, from where); sign-in failures, exports, API-key creation and
revocation are logged; the Principal can read the audit log. Confidential text (counselling
notes, anonymous grievance authors) is deliberately kept out of it.

**A10 Server-side request forgery.** The server calls only fixed hosts (Open Library, the email
and SMS providers, Razorpay, the embeddings API); no user-supplied URL is fetched.

## For the college to do (outside the code)

1. **Set `APP_BASE_URL`** in Vercel to the college's address. Password-reset links are built from
   it; without it they come from the request's host, which a misconfigured proxy elsewhere could
   let a caller choose.
2. **Set `APP_SECRET_KEY`** (long random) and **`CRON_SECRET`**; rotate the MongoDB Atlas password
   (pending from earlier) and restrict Atlas network access to Vercel if the plan allows.
3. Turn on 2-step verification for every staff account, not only the required roles.
4. Run `npm audit` and `pip-audit` before each release; review the audit log for exports and
   API keys each month.
