"""
Load test (plan 4.7): many students signing in at once and opening their pages, as on a results
or fee day. Never run it against production.

    cd backend
    # 1. accounts to sign in with (a demo or test database only)
    MONGODB_DB=collegeconnect_load python -m scripts.loadtest prepare --students 2000
    # 2. the server, with the per-IP sign-in limit raised (every simulated student comes from this machine)
    MONGODB_DB=collegeconnect_load LOGIN_LIMIT_PER_IP=1000000 COOKIE_SECURE=false \\
        uvicorn app.main:app --port 8000 --workers 4
    # 3. the test: 2,000 students within 15 minutes, 50 at a time
    python -m scripts.loadtest run --url http://localhost:8000 --students 2000 --concurrency 50

Each simulated student signs in, loads their home page, fees, attendance and results, and signs
out. The report gives requests, errors and response times (median, 95th percentile, slowest) per
step and the total time; it passes when nothing failed and everyone was served within the
target time.
"""

import argparse
import asyncio
import statistics
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.config import settings
from app.core.db import get_db
from app.core.security import hash_password

PASSWORD = "Load@Test2026"  # noqa: S105 - test accounts in a test database only
PREFIX = "LT"
PRODUCTION_DB = "collegeconnect"
STEPS = [
    ("home", "/api/v1/me/home"),
    ("fees", "/api/v1/me/fees"),
    ("attendance", "/api/v1/me/attendance"),
    ("results", "/api/v1/me/results"),
]


def prepare(n: int) -> int:
    """Creates n student records and sign-ins (PRN LT00001…) with one password; reuses existing ones."""
    if settings.mongodb_db == PRODUCTION_DB:
        raise SystemExit("Refusing to create load-test accounts in the production database.")
    db = get_db()
    year = db.academic_years.find_one({"is_current": True})
    programme = db.programmes.find_one({})
    hashed = hash_password(PASSWORD)  # one hash for all: preparing 2,000 accounts stays quick
    now = datetime.now(UTC)
    made = 0
    for i in range(1, n + 1):
        prn = f"{PREFIX}{i:05d}"
        if db.users.find_one({"prn": prn}):
            continue
        user_id = db.users.insert_one(
            {"kind": "student", "name": f"Load Test {i}", "prn": prn, "roles": ["student"], "status": "active",
             "password_hash": hashed, "must_change_password": False, "password_changed_at": now, "failed_logins": 0,
             "locked_until": None, "mfa": {"enabled": False}, "onboarded_at": now, "created_at": now, "updated_at": now}
        ).inserted_id  # fmt: skip
        db.students.insert_one(
            {"prn": prn, "name": f"Load Test {i}", "user_id": user_id, "status": "active", "year_of_study": 1,
             "programme_id": programme["_id"] if programme else None, "academic_year_id": year["_id"] if year else None,
             "created_at": now, "updated_at": now, "load_test": True}
        )  # fmt: skip
        made += 1
    return made


async def one_student(
    client: httpx.AsyncClient, prn: str, timings: dict[str, list[float]], errors: dict[str, int]
) -> None:
    async def step(name: str, method: str, url: str, **kw: Any) -> httpx.Response | None:
        start = time.perf_counter()
        try:
            r = await client.request(method, url, **kw)
        except httpx.HTTPError:
            errors[name] += 1
            return None
        timings[name].append(time.perf_counter() - start)
        if r.status_code >= 400:
            errors[name] += 1
            return None
        return r

    if await step("sign_in", "POST", "/api/v1/auth/login", json={"identifier": prn, "password": PASSWORD}) is None:
        return
    for name, url in STEPS:
        await step(name, "GET", url)
    await step("sign_out", "POST", "/api/v1/auth/logout")


async def run(url: str, n: int, concurrency: int) -> dict[str, Any]:
    timings: dict[str, list[float]] = defaultdict(list)
    errors: dict[str, int] = defaultdict(int)
    queue: asyncio.Queue[str] = asyncio.Queue()
    for i in range(1, n + 1):
        queue.put_nowait(f"{PREFIX}{i:05d}")

    async def worker() -> None:
        while not queue.empty():
            prn = queue.get_nowait()
            # One client per student: their own session cookie.
            async with httpx.AsyncClient(base_url=url, timeout=30, headers={"X-Requested-With": "XMLHttpRequest"}) as c:
                await one_student(c, prn, timings, errors)

    start = time.perf_counter()
    await asyncio.gather(*(worker() for _ in range(concurrency)))
    return {"seconds": time.perf_counter() - start, "timings": timings, "errors": errors}


def report(result: dict[str, Any], n: int, target_minutes: float) -> bool:
    print(f"\n{n} students in {result['seconds']:.0f} s ({n / result['seconds']:.1f} sign-ins a second)\n")
    print(f"{'step':<12}{'requests':>10}{'errors':>8}{'median ms':>11}{'p95 ms':>9}{'max ms':>9}")
    total_errors = 0
    for name in ["sign_in", *(s for s, _ in STEPS), "sign_out"]:
        t = sorted(result["timings"].get(name, []))
        e = result["errors"].get(name, 0)
        total_errors += e
        if t:
            p95 = t[min(len(t) - 1, int(len(t) * 0.95))]
            median = statistics.median(t) * 1000
            print(f"{name:<12}{len(t):>10}{e:>8}{median:>11.0f}{p95 * 1000:>9.0f}{t[-1] * 1000:>9.0f}")
        else:
            print(f"{name:<12}{0:>10}{e:>8}")
    ok = total_errors == 0 and result["seconds"] <= target_minutes * 60
    print(
        f"\n{'PASS' if ok else 'FAIL'}: {total_errors} errors; target {n} students within {target_minutes:g} minutes."
    )
    return ok


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--students", type=int, default=2000)
    go = sub.add_parser("run")
    go.add_argument("--url", required=True)
    go.add_argument("--students", type=int, default=2000)
    go.add_argument("--concurrency", type=int, default=50)
    go.add_argument("--target-minutes", type=float, default=15)
    args = p.parse_args(argv)
    if args.cmd == "prepare":
        print(f"Created {prepare(args.students)} load-test students ({PREFIX}00001…, password {PASSWORD}).")
        return 0
    if "collegeconnect.vercel.app" in args.url:
        print("Refusing to load-test production.", file=sys.stderr)
        return 2
    result = asyncio.run(run(args.url, args.students, args.concurrency))
    return 0 if report(result, args.students, args.target_minutes) else 1


if __name__ == "__main__":
    sys.exit(main())
