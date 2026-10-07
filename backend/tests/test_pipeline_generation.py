"""The answer path when an LLM is configured, with the model call replaced by a fake."""

import anthropic
import httpx
import pytest

from app.rag import generator, pipeline
from app.rag.generator import GeneratedAnswer


@pytest.fixture
def llm_on(monkeypatch):
    monkeypatch.setattr(generator, "llm_available", lambda: True)
    monkeypatch.setattr(generator, "translate_query_to_english", lambda q: q)


def _fake_answer(answer: GeneratedAnswer | None):
    def fake(question, language, chunks):
        fake.chunks = chunks
        if answer is not None and answer.cited_chunk_ids == ["FIRST"]:
            answer.cited_chunk_ids = [chunks[0]["id"]]
        return answer

    return fake


def test_cited_chunks_become_source_cards(llm_on, monkeypatch):
    monkeypatch.setattr(
        generator,
        "generate_answer",
        _fake_answer(GeneratedAnswer(answer="Rs. 60,000 per year.", answerable=True, cited_chunk_ids=["FIRST"])),
    )
    result = pipeline.answer_question("How much is the single room fee?", "en")
    assert result["answer"] == "Rs. 60,000 per year."
    assert result["grounded"] is True
    assert result["sources"][0]["section"] == "Section 2: Hostel Fees"


def test_unknown_citation_ids_fall_back_to_the_top_chunk(llm_on, monkeypatch):
    monkeypatch.setattr(
        generator,
        "generate_answer",
        _fake_answer(GeneratedAnswer(answer="Answer.", answerable=True, cited_chunk_ids=["made-up-id"])),
    )
    result = pipeline.answer_question("What's the hostel fee?", "en")
    assert len(result["sources"]) == 1


def test_model_says_not_answerable(llm_on, monkeypatch):
    monkeypatch.setattr(
        generator,
        "generate_answer",
        _fake_answer(GeneratedAnswer(answer="Not in the documents.", answerable=False, cited_chunk_ids=[])),
    )
    result = pipeline.answer_question("What's the hostel fee?", "en")
    assert result == {
        "answer": "Not in the documents.",
        "category": "hostel",
        "sources": [],
        "confidence": 0.0,
        "grounded": False,
        "chat": False,
    }


def test_model_refusal_returns_not_found(llm_on, monkeypatch):
    monkeypatch.setattr(generator, "generate_answer", _fake_answer(None))
    result = pipeline.answer_question("What's the hostel fee?", "hi")
    assert result["grounded"] is False
    assert result["answer"] == pipeline.NOT_FOUND["hi"]


def test_api_errors_fall_back_to_the_document_excerpt(llm_on, monkeypatch):
    def overloaded(*args, **kwargs):
        request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        raise anthropic.InternalServerError("overloaded", response=httpx.Response(529, request=request), body=None)

    monkeypatch.setattr(generator, "generate_answer", overloaded)
    result = pipeline.answer_question("What's the hostel fee?", "en")
    assert result["grounded"] is True
    assert result["answer"].startswith("Hostel accommodation fee is Rs. 45,000")


def test_greetings_and_thanks_get_a_friendly_reply_without_any_search_or_ai(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("no AI call for small talk")

    monkeypatch.setattr(generator, "generate_answer", boom)
    hello = pipeline.answer_question("Hi!", "en")
    assert hello["answer"].startswith("Hello!") and "fees" in hello["answer"] and hello["chat"] is True
    assert pipeline.answer_question("धन्यवाद", "mr")["answer"].startswith("तुमचे स्वागत आहे")
    assert pipeline.answer_question("नमस्ते", "hi")["answer"].startswith("नमस्ते!")
    assert pipeline.answer_question("what can you do?", "en")["chat"] is True
    # A real question that starts with "hi" is still a question.
    assert "chat" not in pipeline.answer_question("hi what is the hostel fee for a single room", "en")


def test_without_ai_an_unknown_question_gets_a_kind_reply_with_examples():
    result = pipeline.answer_question("Who won the cricket world cup in 2011?", "en")
    assert result["grounded"] is False
    assert result["answer"].startswith("Sorry, I couldn't find that") and "For example" in result["answer"]


def test_with_ai_an_unrelated_question_is_steered_back_and_not_logged_as_a_gap(llm_on, monkeypatch):
    fake = _fake_answer(
        GeneratedAnswer(
            answer="I'm the college help desk, so I can't help with cricket. You could ask about exam dates.",
            answerable=False,
            on_topic=False,
            cited_chunk_ids=[],
        )
    )
    monkeypatch.setattr(generator, "generate_answer", fake)
    result = pipeline.answer_question("Who won the cricket world cup in 2011?", "en")
    assert result["answer"].startswith("I'm the college help desk") and result["chat"] is True
    assert fake.chunks == [] or all("cricket" not in c["text"].lower() for c in fake.chunks)

    from app.modules.helpdesk import analytics

    monkeypatch.setattr(analytics, "db_available", lambda: True)
    monkeypatch.setattr(analytics, "_queries", lambda: (_ for _ in ()).throw(AssertionError("logged")))
    analytics.log_query("Who won?", "en", None, result, 10, "portal")  # returns without logging


def test_any_provider_error_falls_back(llm_on, monkeypatch):
    def down(*args, **kwargs):
        raise generator.GeminiError(503, "unavailable")

    monkeypatch.setattr(generator, "generate_answer", down)
    assert pipeline.answer_question("What's the hostel fee?", "en")["grounded"] is True
