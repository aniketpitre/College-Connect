"""
Load a CollegeConnect full export (the ZIP from Data export → "Everything") into a database.

    cd backend
    MONGODB_URI=... python -m scripts.restore_export collegeconnect-full-20261006.zip --db collegeconnect_restored

The target database must be empty (use a new name). Documents are inserted exactly as exported
(ids, dates and files keep their types), then the indexes are created. Passwords and 2-step
secrets are never in an export: after a restore everyone sets a new password with "Forgot
password" (the restore marks each account so).
"""

import argparse
import io
import json
import sys
import zipfile
from typing import Any

from bson import json_util
from pymongo import MongoClient
from pymongo.database import Database

from app.core.config import settings
from app.core.db import ensure_indexes

BATCH = 500


def restore(data: bytes, db: Database[dict[str, Any]]) -> dict[str, int]:
    if db.list_collection_names():
        raise SystemExit(f"The database '{db.name}' is not empty. Restore into a new database.")
    counts: dict[str, int] = {}
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        manifest = json.loads(z.read("manifest.json"))
        for entry in manifest["collections"]:
            name = entry["collection"]
            docs: list[dict[str, Any]] = []
            counts[name] = 0
            for line in z.read(f"collections/{name}.jsonl").decode("utf-8").splitlines():
                if not line.strip():
                    continue
                doc = json_util.loads(line)
                if name == "users":
                    doc.update(password_hash=None, mfa={"enabled": False}, must_change_password=True)
                docs.append(doc)
                if len(docs) >= BATCH:
                    db[name].insert_many(docs, ordered=False)
                    counts[name] += len(docs)
                    docs = []
            if docs:
                db[name].insert_many(docs, ordered=False)
                counts[name] += len(docs)
    ensure_indexes(db)
    return counts


def check(data: bytes, db: Database[dict[str, Any]]) -> list[str]:
    """After a restore: each collection against the count the export listed, and money totals.

    The listed count is taken when the export starts; a busy college may add a few records (the
    audit log always grows) while it downloads, so a small surplus is a warning, a shortfall an error.
    """
    problems: list[str] = []
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        manifest = json.loads(z.read("manifest.json"))
    for entry in manifest["collections"]:
        name, listed = entry["collection"], entry.get("count")
        got = db[name].count_documents({})
        if listed is not None and got < listed:
            problems.append(f"{name}: {got} restored, {listed} listed in the export (missing records)")
        elif listed is not None and got > listed and name != "audit_log":
            problems.append(f"{name}: {got} restored, {listed} listed (added while exporting; check)")
    return problems


def ledger_total(db: Database[dict[str, Any]]) -> int:
    """Sum of every ledger entry, in paise: compare between the live and the restored database."""
    rows = list(db.ledger_entries.aggregate([{"$group": {"_id": None, "t": {"$sum": "$amount"}}}]))
    return int(rows[0]["t"]) if rows else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("zip", help="The full export ZIP")
    parser.add_argument("--db", required=True, help="An empty database to restore into")
    args = parser.parse_args(argv)
    if not settings.mongodb_uri:
        print("Set MONGODB_URI first.", file=sys.stderr)
        return 2
    with open(args.zip, "rb") as f:
        data = f.read()
    client: MongoClient[dict[str, Any]] = MongoClient(settings.mongodb_uri, tz_aware=True)
    counts = restore(data, client[args.db])
    for name, n in sorted(counts.items()):
        print(f"  {name:<28} {n}")
    print(f"Restored {sum(counts.values())} records into '{args.db}'.")
    print(f"Ledger total: {ledger_total(client[args.db])} paise (compare with the live database).")
    problems = check(data, client[args.db])
    for p in problems:
        print(f"  ! {p}")
    print("Check: " + ("records match the export." if not problems else f"{len(problems)} difference(s) above."))
    return 1 if any("missing" in p for p in problems) else 0


if __name__ == "__main__":
    sys.exit(main())
