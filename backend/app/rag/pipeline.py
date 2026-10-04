"""Ask -> Retrieve -> Answer -> Cite."""
import logging

import anthropic
import httpx

from app.rag import generator
from app.rag.config import MIN_SIMILARITY, TOP_K
from app.rag.embeddings import embed, embeddings_available
from app.rag.store import get_index

log = logging.getLogger(__name__)

NOT_FOUND = {
    "en": "I couldn't find an approved document matching your question. Please rephrase, or contact the relevant department office.",
    "hi": "आपके प्रश्न से मेल खाता कोई स्वीकृत दस्तावेज़ नहीं मिला। कृपया प्रश्न को दोबारा लिखें या संबंधित विभाग कार्यालय से संपर्क करें।",
    "mr": "तुमच्या प्रश्नाशी जुळणारा कोणताही मंजूर दस्तऐवज सापडला नाही. कृपया प्रश्न पुन्हा मांडा किंवा संबंधित विभाग कार्यालयाशी संपर्क साधा.",
}

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


def _retrieve(question: str, language: str, category: str | None) -> tuple[list[tuple[dict, float]], float]:
    """Returns (hits, confidence)."""
    index = get_index()

    if index.has_embeddings and embeddings_available():
        try:
            query_vec = embed([question], input_type="query", model=index.embedding_model)[0]
            hits = [h for h in index.vector_search(query_vec, TOP_K, category) if h[1] >= MIN_SIMILARITY]
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
    hits = index.bm25_search(query, TOP_K, category)
    # Heuristic: saturating map of the top BM25 score onto 0-0.95.
    confidence = min(0.95, hits[0][1] / (hits[0][1] + 3)) if hits else 0.0
    return hits, confidence


def _source(chunk: dict) -> dict:
    return {"title": chunk["title"], "document": chunk["document"], "section": chunk["section"]}


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


def answer_question(question: str, language: str, category: str | None = None) -> dict:
    hits, confidence = _retrieve(question, language, category)

    if not hits:
        return {
            "answer": NOT_FOUND[language],
            "category": category or "notices",
            "sources": [],
            "confidence": 0.0,
            "grounded": False,
        }

    if not generator.llm_available():
        return _extractive(language, hits, confidence)

    chunks = [c for c, _ in hits]
    try:
        result = generator.generate_answer(question, language, chunks)
    except anthropic.RateLimitError:
        log.warning("Claude rate limited; returning extractive answer")
        return _extractive(language, hits, confidence)
    except anthropic.APIStatusError as e:
        log.error("Claude API error %s: %s", e.status_code, e.message)
        return _extractive(language, hits, confidence)
    except anthropic.APIConnectionError:
        log.exception("Could not reach Claude; returning extractive answer")
        return _extractive(language, hits, confidence)

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
        "confidence": round(confidence, 2),
        "grounded": True,
    }
