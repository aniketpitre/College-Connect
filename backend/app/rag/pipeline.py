"""Ask -> Retrieve -> Answer -> Cite."""

import logging

import anthropic
import httpx

from app.rag import generator
from app.rag.config import EMBEDDING_MODEL, MIN_SIMILARITY, TOP_K
from app.rag.embeddings import embed, embeddings_available
from app.rag.store import Allowed, get_index

log = logging.getLogger(__name__)

NOT_FOUND = {
    "en": (
        "I couldn't find an approved document matching your question. "
        "Please rephrase, or contact the relevant department office."
    ),
    "hi": ("आपके प्रश्न से मेल खाता कोई स्वीकृत दस्तावेज़ नहीं मिला। कृपया प्रश्न को दोबारा लिखें या संबंधित विभाग कार्यालय से संपर्क करें।"),
    "mr": (
        "तुमच्या प्रश्नाशी जुळणारा कोणताही मंजूर दस्तऐवज सापडला नाही. "
        "कृपया प्रश्न पुन्हा मांडा किंवा संबंधित विभाग कार्यालयाशी संपर्क साधा."
    ),
}

EXTRACTIVE_MIN_CONFIDENCE = 0.3

EXTRACTIVE_NOTE = {
    "en": "",
    "hi": "\n\n(उत्तर जनरेशन अभी उपलब्ध नहीं है; मूल दस्तावेज़ का अंश दिखाया गया है।)",
    "mr": "\n\n(उत्तर निर्मिती सध्या उपलब्ध नाही; मूळ दस्तऐवजातील उतारा दाखवला आहे.)",
}


def pipeline_status() -> dict:
    index = get_index()
    return {
        "retrieval": "vector" if index.has_embeddings and embeddings_available() else "bm25",
        "embedding_model": index.embedding_model,
        "generation": generator.CLAUDE_MODEL if generator.llm_available() else "extractive",
        "chunks": len(index.chunks),
        "documents": len({c["document"] for c in index.chunks}),
    }


def _retrieve(
    question: str, language: str, category: str | None, allowed: Allowed | None
) -> tuple[list[tuple[dict, float]], float]:
    """Returns (hits, confidence)."""
    index = get_index()

    if index.has_embeddings and embeddings_available():
        try:
            query_vec = embed([question], input_type="query", model=index.embedding_model or EMBEDDING_MODEL)[0]
            hits = [h for h in index.vector_search(query_vec, TOP_K, category, allowed) if h[1] >= MIN_SIMILARITY]
            # Heuristic: map cosine similarity above the cut-off onto 0.5-0.95.
            confidence = min(0.95, 0.5 + 1.5 * (hits[0][1] - MIN_SIMILARITY)) if hits else 0.0
            return hits, confidence
        except httpx.HTTPError:
            log.exception("Query embedding failed; falling back to keyword search")

    query = question
    if language != "en" and generator.llm_available():
        try:
            query = generator.translate_query_to_english(question)
        except anthropic.APIError:
            log.exception("Query translation failed; searching with the original question")
    hits = index.bm25_search(query, TOP_K, category, allowed)
    # Heuristic: saturating map of the top BM25 score onto 0-0.95.
    confidence = min(0.95, hits[0][1] / (hits[0][1] + 3)) if hits else 0.0
    return hits, confidence


def _source(chunk: dict) -> dict:
    source = {"title": chunk["title"], "document": chunk["document"], "section": chunk["section"]}
    if chunk.get("link"):
        source["link"] = chunk["link"]
    return source


def _dedupe_sources(chunks: list[dict]) -> list[dict]:
    seen, out = set(), []
    for c in chunks:
        key = (c["document"], c["section"])
        if key not in seen:
            seen.add(key)
            out.append(_source(c))
    return out


def _extractive(language: str, hits: list[tuple[dict, float]], confidence: float) -> dict:
    top = hits[0][0]
    return {
        "answer": top["text"] + EXTRACTIVE_NOTE[language],
        "category": top["category"],
        "sources": [_source(top)],
        "confidence": round(confidence, 2),
        "grounded": True,
    }


def _record_answer(record: list[dict], hits: list[tuple[dict, float]], allowed: Allowed | None) -> dict:
    """The asker's own record, quoted (no AI needed: the excerpts are written in their language),
    with the document that explains it: from the search, or (a Hindi/Marathi question the keyword
    search can't match) found with the record's own English search hint."""
    related = {cat for r in record for cat in r.get("related", [])}
    doc = next((c for c, _ in hits if c["category"] in related), None)
    if doc is None:
        for r in record:
            found = get_index().bm25_search(r.get("hint", ""), 3, None, allowed)
            doc = next((c for c, _ in found if c["category"] in related), None)
            if doc:
                break
    return {
        "answer": "\n\n".join(r["text"] for r in record),
        "category": record[0]["category"],
        "sources": [_source(r) for r in record] + ([_source(doc)] if doc else []),
        "confidence": 0.9,
        "grounded": True,
    }


def answer_question(
    question: str,
    language: str,
    category: str | None = None,
    allowed: Allowed | None = None,
    record: list[dict] | None = None,
    personal: bool = False,
) -> dict:
    """`allowed` limits the documents to those the asker may see (None: every chunk in the index;
    the public help desk passes the public-only filter). `record`: excerpts of the asker's own
    record (Ask my record), cited like documents; `personal`: the question is about the asker
    ("my fees"), so without an AI the record itself is the answer."""
    hits, confidence = _retrieve(question, language, category, allowed)
    record = record or []

    if record and not generator.llm_available() and (personal or not hits):
        return _record_answer(record, hits, allowed)

    if not hits and not record:
        return {
            "answer": NOT_FOUND[language],
            "category": category or "notices",
            "sources": [],
            "confidence": 0.0,
            "grounded": False,
        }

    if not generator.llm_available():
        # Without an LLM to judge relevance, a weak keyword match is more likely wrong than right.
        if confidence < EXTRACTIVE_MIN_CONFIDENCE:
            return {
                "answer": NOT_FOUND[language],
                "category": category or "notices",
                "sources": [],
                "confidence": 0.0,
                "grounded": False,
            }
        return _extractive(language, hits, confidence)

    def fallback() -> dict:
        if record and (personal or not hits):
            return _record_answer(record, hits, allowed)
        return _extractive(language, hits, confidence)

    chunks = record + [c for c, _ in hits]
    try:
        result = generator.generate_answer(question, language, chunks)
    except anthropic.RateLimitError:
        log.warning("Claude rate limited; returning extractive answer")
        return fallback()
    except anthropic.APIStatusError as e:
        log.error("Claude API error %s: %s", e.status_code, e.message)
        return fallback()
    except anthropic.APIConnectionError:
        log.exception("Could not reach Claude; returning extractive answer")
        return fallback()

    if result is None or not result.answerable:
        return {
            "answer": result.answer if result else NOT_FOUND[language],
            "category": category or chunks[0]["category"],
            "sources": [],
            "confidence": 0.0,
            "grounded": False,
        }

    by_id = {c["id"]: c for c in chunks}
    cited = [by_id[i] for i in result.cited_chunk_ids if i in by_id] or chunks[:1]
    return {
        "answer": result.answer,
        "category": cited[0]["category"],
        "sources": _dedupe_sources(cited),
        "confidence": 0.9 if any(c.get("record") for c in cited) else round(confidence, 2),
        "grounded": True,
    }
