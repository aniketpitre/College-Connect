"""The Gemini provider (the free alternative to Claude), with Google's API replaced by a fake."""

import json

import httpx
import pytest

from app.rag import generator
from app.rag.generator import GeneratedAnswer, StaffPlan


@pytest.fixture
def gemini(monkeypatch):
    monkeypatch.setattr(generator, "ANTHROPIC_API_KEY", None)
    monkeypatch.setattr(generator, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(generator, "_gemini_endpoint", [0])
    calls: list[dict] = []

    def reply(text: str, status: int = 200, finish: str = "STOP", only: str | None = None):
        def post(url, json, headers, timeout):
            calls.append({"url": url, "body": json, "headers": headers})
            if only and only not in url:
                return httpx.Response(404, text="not found")
            body = {"candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": finish}]}
            return httpx.Response(status, json=body if status == 200 else {"error": "x"})

        monkeypatch.setattr(generator.httpx, "post", post)

    reply.calls = calls  # type: ignore[attr-defined]
    return reply


def test_provider_choice(monkeypatch):
    monkeypatch.setattr(generator, "ANTHROPIC_API_KEY", None)
    monkeypatch.setattr(generator, "GEMINI_API_KEY", None)
    assert generator.provider() is None and not generator.llm_available()
    monkeypatch.setattr(generator, "GEMINI_API_KEY", "g")
    assert generator.provider() == "gemini" and generator.model_name() == generator.GEMINI_MODEL
    monkeypatch.setattr(generator, "ANTHROPIC_API_KEY", "a")
    assert generator.provider() == "anthropic"


def test_answers_come_back_in_the_expected_shape(gemini):
    gemini(json.dumps({"answer": "₹45,000 a year.", "answerable": True, "on_topic": True, "cited_chunk_ids": ["c1"]}))
    chunk = {"id": "c1", "title": "Hostel", "document": "hostel.md", "section": "Fees", "text": "Rs. 45,000"}
    result = generator.generate_answer("hostel fee?", "hi", [chunk])
    assert result == GeneratedAnswer(answer="₹45,000 a year.", answerable=True, on_topic=True, cited_chunk_ids=["c1"])
    call = gemini.calls[0]
    assert call["headers"]["x-goog-api-key"] == "test-key"
    assert "friendly" in call["body"]["systemInstruction"]["parts"][0]["text"]
    assert "Hindi" in call["body"]["contents"][0]["parts"][0]["text"]
    schema = call["body"]["generationConfig"]["responseSchema"]
    assert schema["type"] == "object" and schema["properties"]["cited_chunk_ids"]["items"] == {"type": "string"}


def test_optional_fields_and_choices_become_gemini_schema():
    schema = generator._gemini_schema(StaffPlan)
    assert schema["properties"]["tool"]["enum"][0] == "fees_outstanding"
    assert schema["properties"]["year"] == {"type": "integer", "nullable": True}
    assert schema["required"] == ["tool"]
    nested = generator._gemini_schema(generator.ExtractedDeadlines)
    assert nested["properties"]["deadlines"]["items"]["properties"]["date"]["type"] == "string"


def test_a_vertex_key_is_tried_on_the_second_endpoint_and_remembered(gemini):
    gemini("Hello", only="aiplatform")
    assert generator._text("system", "hi", 100) == "Hello"
    assert generator._text("system", "hi", 100) == "Hello"
    urls = [c["url"] for c in gemini.calls]
    assert "generativelanguage" in urls[0] and "aiplatform" in urls[1] and "aiplatform" in urls[2]


def test_a_declined_answer_is_none_and_errors_are_llm_errors(gemini):
    gemini("", finish="SAFETY")
    assert generator._text("system", "hi", 100) is None
    gemini("", status=429)
    with pytest.raises(generator.LLM_ERRORS):
        generator._text("system", "hi", 100)
    gemini("not json")
    with pytest.raises(generator.GeminiError):
        generator.plan_staff_query("who owes fees?")
