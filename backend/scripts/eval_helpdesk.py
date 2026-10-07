"""
Evaluation of CollegeConnect AI (plan 5.9) against `eval/helpdesk_eval.json`: questions in
English, Hindi and Marathi over the bundled documents, each with the document that must be cited
(or none: the help desk must say it has no source) and the numbers the answer must contain.

    cd backend
    python -m scripts.eval_helpdesk                # what the server is set up with (AI and embeddings if keys are set)
    python -m scripts.eval_helpdesk --language en  # one language
    python -m scripts.eval_helpdesk --json         # machine-readable

Synopsis targets: at least 90% correct answers, 100% citation coverage (every answer given cites a
source), under 5 seconds an answer. Without an AI key or embeddings, the keyword search cannot match
Hindi/Marathi questions to the English documents: those cases are reported as "needs AI" and left
out of the score instead of counting as wrong.
"""

import argparse
import json
import re
import statistics
import sys
import time
from pathlib import Path
from typing import Any

from app.rag import generator
from app.rag.embeddings import embeddings_available
from app.rag.pipeline import answer_question
from app.rag.store import file_index, public_only

CASES = Path(__file__).resolve().parent.parent / "eval" / "helpdesk_eval.json"
TARGET_CORRECT = 0.90
TARGET_CITED = 1.0
TARGET_SECONDS = 5.0


def load_cases(language: str | None = None) -> list[dict[str, Any]]:
    cases = json.loads(CASES.read_text(encoding="utf-8"))["cases"]
    return [c for c in cases if language is None or c["language"] == language]


def _digits(text: str) -> str:
    return re.sub(r"(?<=\d)[,\s](?=\d)", "", text)


def multilingual() -> bool:
    """Hindi/Marathi questions can find English documents (query translation or multilingual embeddings)."""
    return generator.llm_available() or (embeddings_available() and file_index().has_embeddings)


def judge(case: dict[str, Any], result: dict[str, Any]) -> tuple[bool, str]:
    sources = [s["document"] for s in result["sources"]]
    if case["document"] is None:
        return (not result["grounded"], "" if not result["grounded"] else f"answered from {sources}")
    if not result["grounded"]:
        return False, "said it had no source"
    if case["document"] not in sources:
        return False, f"cited {sources}"
    missing = [f for f in case["facts"] if f not in _digits(result["answer"])]
    return (not missing, f"missing {missing}" if missing else "")


def run(cases: list[dict[str, Any]]) -> dict[str, Any]:
    can_translate = multilingual()
    rows = []
    for c in cases:
        if c["language"] != "en" and c["document"] is not None and not can_translate:
            rows.append({**c, "status": "needs AI", "seconds": None, "note": ""})
            continue
        started = time.perf_counter()
        result = answer_question(c["question"], c["language"], None, public_only())
        seconds = time.perf_counter() - started
        ok, note = judge(c, result)
        cited = bool(result["sources"]) if result["grounded"] else None
        rows.append({**c, "status": "correct" if ok else "wrong", "seconds": seconds, "note": note, "cited": cited})
    scored = [r for r in rows if r["status"] != "needs AI"]
    answered = [r for r in scored if r.get("cited") is not None]
    times = [r["seconds"] for r in scored]
    summary: dict[str, Any] = {
        "mode": {
            "generation": generator.model_name() if generator.llm_available() else "extractive (no AI key)",
            "retrieval": "vector" if embeddings_available() and file_index().has_embeddings else "keywords",
        },
        "cases": len(rows),
        "scored": len(scored),
        "needs_ai": len(rows) - len(scored),
        "correct": sum(r["status"] == "correct" for r in scored) / len(scored) if scored else 0.0,
        "citation_coverage": sum(bool(r["cited"]) for r in answered) / len(answered) if answered else 1.0,
        "median_seconds": statistics.median(times) if times else 0.0,
        "max_seconds": max(times) if times else 0.0,
        "by_language": {
            lang: {
                "scored": sum(1 for r in scored if r["language"] == lang),
                "correct": sum(1 for r in scored if r["language"] == lang and r["status"] == "correct"),
            }
            for lang in ("en", "hi", "mr")
        },
    }
    summary["passed"] = (
        summary["correct"] >= TARGET_CORRECT
        and summary["citation_coverage"] >= TARGET_CITED
        and summary["median_seconds"] < TARGET_SECONDS
    )
    return {"summary": summary, "rows": rows}


def report(out: dict[str, Any]) -> None:
    s = out["summary"]
    print(f"Mode: answers {s['mode']['generation']}, search by {s['mode']['retrieval']}\n")
    for r in out["rows"]:
        took = f"{r['seconds']:.2f}s" if r["seconds"] is not None else ""
        print(f"  {r['id']:<10} {r['status']:<9} {took:>7}  {r['question'][:60]}  {r['note']}")
    print(
        f"\n{s['scored']} of {s['cases']} cases scored ({s['needs_ai']} need an AI key or embeddings).\n"
        f"Correct: {s['correct']:.0%} (target {TARGET_CORRECT:.0%}) · citation coverage: "
        f"{s['citation_coverage']:.0%} (target 100%) · median {s['median_seconds']:.2f}s, "
        f"slowest {s['max_seconds']:.2f}s (target < {TARGET_SECONDS:g}s)"
    )
    for lang, v in s["by_language"].items():
        print(f"  {lang}: {v['correct']} of {v['scored']}")
    print("PASS" if s["passed"] else "FAIL")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--language", choices=["en", "hi", "mr"])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    out = run(load_cases(args.language))
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        report(out)
    return 0 if out["summary"]["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
