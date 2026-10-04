"""Keyword retrieval must find the right section for every suggested question in the UI."""

import pytest

from app.rag.pipeline import answer_question
from app.rag.store import _related, tokenize

CASES = [
    ("When are the odd semester exams?", None, "Section 1: Theory Exam Timetable"),
    ("What's the hostel fee?", None, "Section 2: Hostel Fees"),
    ("What documents do I need for admission?", None, "Section 3: Required Documents"),
    ("When is the next placement drive?", None, "Section 1: Upcoming Drives"),
    ("How do I apply for revaluation?", None, "Section 4: Revaluation & Backlog"),
    ("Is the college closed this week?", None, "Latest Announcements"),
    ("What scholarships are available?", None, "Section 5: Scholarships"),
    ("What is the last date to apply?", "admissions", "Section 1: Key Dates"),
    ("When is the semester fee due?", None, "Section 2: Payment Deadlines"),
    ("How are hostel fees paid?", None, "Section 2: Hostel Fees"),
    ("How do I register for placements?", None, "Section 1: Upcoming Drives"),
    ("What are the latest announcements?", None, "Latest Announcements"),
    ("How much is the single room fee?", None, "Section 2: Hostel Fees"),
]


@pytest.mark.parametrize(("question", "category", "section"), CASES)
def test_suggested_questions_find_the_right_section(question, category, section):
    result = answer_question(question, "en", category)
    assert result["grounded"] is True
    assert result["sources"][0]["section"] == section


@pytest.mark.parametrize(
    ("question", "category"),
    [("weather on mars", None), ("When are the odd semester exams?", "hostel")],
)
def test_unrelated_or_wrong_office_is_not_grounded(question, category):
    result = answer_question(question, "en", category)
    assert result["grounded"] is False
    assert result["sources"] == []
    assert result["confidence"] == 0.0


def test_not_found_message_is_in_the_requested_language():
    result = answer_question("weather on mars", "mr", None)
    assert "दस्तऐवज" in result["answer"]


def test_tokenizer_stems_plurals_and_drops_filler_words():
    assert tokenize("What documents do I need for exams?") == ["document", "exam"]


def test_related_words_match_by_prefix():
    assert _related("exam", "examination")
    assert not _related("fee", "feedback")  # prefixes shorter than 4 letters don't match
