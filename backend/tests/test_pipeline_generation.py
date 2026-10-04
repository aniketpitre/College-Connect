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
