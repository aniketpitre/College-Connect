"""
Load demo data into a development or preview database.

    cd backend
    python -m scripts.seed_demo            # add demo data
    python -m scripts.seed_demo --reset    # remove previously seeded demo data first
    python -m scripts.seed_demo --erp      # ERP demo: BCA, 60 students, fees, notices, staff logins

Refuses to touch the production database name ("collegeconnect") unless --force is given.
Each phase adds its own seeder to SEEDERS (Phase 1: academic year, BCA programme, students,
fee structures).
"""

import argparse
import random
import sys
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any

from pymongo.database import Database

from app.core.config import settings
from app.core.db import db_available, get_db

PRODUCTION_DB = "collegeconnect"
DEMO_TAG = {"demo": True}


def seed_helpdesk_queries(db: Database[dict[str, Any]], rng: random.Random) -> int:
    """A week of help-desk questions so the admin analytics page has something to show."""
    samples = [
        ("What's the hostel fee?", "en", "hostel", True),
        ("When are the odd semester exams?", "en", "examinations", True),
        ("प्रवेश के लिए कौन से दस्तावेज़ चाहिए?", "hi", "admissions", True),
        ("When is the next placement drive?", "en", "placements", True),
        ("वसतिगृह फी किती आहे?", "mr", "hostel", True),
        ("Is there a cricket tournament this month?", "en", None, False),
        ("Can I pay fees in installments?", "en", "fees", True),
        ("Is the canteen open on Sunday?", "en", None, False),
    ]
    now = datetime.now(UTC)
    docs: list[dict[str, Any]] = []
    for _ in range(60):
        question, language, category, grounded = rng.choice(samples)
        docs.append(
            {
                **DEMO_TAG,
                "created_at": now - timedelta(minutes=rng.randint(5, 7 * 24 * 60)),
                "question": question,
                "language": language,
                "category_filter": None,
                "category": category,
                "grounded": grounded,
                "confidence": round(rng.uniform(0.45, 0.9), 2) if grounded else 0.0,
                "sources": [],
                "latency_ms": rng.randint(300, 3500),
            }
        )
    db.queries.insert_many(docs)
    return len(docs)


SEEDERS: dict[str, Callable[[Database[dict[str, Any]], random.Random], int]] = {
    "queries": seed_helpdesk_queries,
}


def reset(db: Database[dict[str, Any]]) -> int:
    return sum(db[collection].delete_many(DEMO_TAG).deleted_count for collection in SEEDERS)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reset", action="store_true", help="delete previously seeded demo data first")
    parser.add_argument("--force", action="store_true", help=f"allow seeding the '{PRODUCTION_DB}' database")
    parser.add_argument("--erp", action="store_true", help="also load ERP demo data (needs an empty database)")
    parser.add_argument("--seed", type=int, default=2026, help="random seed (same seed = same data)")
    args = parser.parse_args(argv)

    if not db_available():
        print("MONGODB_URI is not set.", file=sys.stderr)
        return 1
    if settings.mongodb_db == PRODUCTION_DB and not args.force:
        print(
            f"Refusing to seed the production database '{PRODUCTION_DB}'. "
            "Set MONGODB_DB=collegeconnect_dev (or pass --force).",
            file=sys.stderr,
        )
        return 2

    db = get_db()
    if args.reset:
        print(f"Removed {reset(db)} demo documents")
    rng = random.Random(args.seed)  # noqa: S311 - demo data, not security
    for name, seeder in SEEDERS.items():
        print(f"Seeded {seeder(db, rng)} {name}")
    if args.erp:
        from scripts import seed_erp

        for name, count in seed_erp.seed(db, rng).items():
            print(f"Seeded {count} {name}")
        print("Demo sign-ins (password " + seed_erp.DEMO_PASSWORD + "):")
        for role, _name, email in seed_erp.STAFF:
            print(f"  {role:<13} {email}")
        print(
            "  students      PRN, e.g. "
            + str(date.today().year if date.today().month >= 6 else date.today().year - 1)
            + "BCA001"
        )
        print(f"  parent        mobile {seed_erp.PARENT_PHONE} (code by email, or the demo password)")
    print(f"Database: {settings.mongodb_db}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
