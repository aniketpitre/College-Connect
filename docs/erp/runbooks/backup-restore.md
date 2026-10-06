# Backup and restore drill (plan 4.7)

The free MongoDB Atlas tier (M0) has **no automatic backups** and no point-in-time restore. The
college's backup is the CollegeConnect full export, taken regularly and kept off-site.

## Taking a backup (every month, and before each semester's results and fee season)

1. System Admin: **Data export → Everything**, with a reason ("Monthly backup, October").
2. Principal: approve it under **Approvals** (the request is valid for 24 hours).
3. System Admin: **Download ZIP**. The browser reads every collection in pages and saves
   `collegeconnect-full-<date>.zip` (`manifest.json`, `data-dictionary.md`, `collections/*.jsonl`).
4. Keep the ZIP in two places (e.g. the college's Google Drive and an encrypted USB drive in the
   office safe). It holds personal data: share it with nobody. Keep at least the last three.

Not in the export, by design: passwords and 2-step secrets, sign-in sessions, one-time codes,
reset links, rate-limit counters, the message queue and API keys. Uploaded files (photos,
documents) live in Vercel Blob and are not in the ZIP; the records keep their links.

## Restoring

```bash
cd backend
MONGODB_URI="<connection string of the target cluster>" \
    python -m scripts.restore_export collegeconnect-full-20261006.zip --db collegeconnect_restored
```

- The target database must be empty (use a new name); the script refuses otherwise.
- Every record comes back with the same ids, dates and nested fields; indexes are created.
- After loading, the script checks every collection against the count listed in the export
  (a shortfall is an error and the script exits with 1; a few extra audit entries written while
  the export ran are normal) and prints the ledger total in paise, to compare with the live
  database (or with the total on the last fee report).
- To go live on the restored data, set `MONGODB_DB` in Vercel to the new name and redeploy.
  Everyone then signs in with **Forgot password**, because passwords are not exported; staff
  with 2-step verification set it up again. Create new API keys for other systems.

## Drill (do it once a term, on a copy, never on the live database)

1. Take a full export as above.
2. Restore it into a new database (`collegeconnect_drill_<date>`) on a free test cluster or locally.
3. Confirm the script says "records match the export" and the ledger total matches.
4. Start the app against the restored database (`MONGODB_DB=collegeconnect_drill_<date>`), reset
   one staff and one student password, and open a student's fee statement and results.
5. Note the date, the counts and the time taken below; drop the drill database.

## Drill log

| Date | Data | Records | ZIP | Restore time | Check | Ledger total |
|---|---|---|---|---|---|---|
| 2026-10-06 | Demo college (68 collections) | 1,484 | 0.1 MB | 1.2 s | records match | matches (₹10,53,214.00) |
| 2026-10-06 | Load-test copy, 2,000 extra students | 9,371 | 0.2 MB | 1.2 s | records match | matches (₹10,25,700.00) |

Both drills ran locally (MongoDB 7 replica set). A real college of 2,000 students with a few
years of attendance will be larger (attendance is the biggest collection); the export pages
keep each download under Vercel's response limit whatever the size.
