"""
Retrieval stub for CollegeConnect AI.

This module simulates the "Retrieve" step of the Ask -> Retrieve -> Answer -> Cite
pipeline using simple keyword overlap against a small local JSON document set.

TODO (real RAG pipeline, not yet implemented):
  - Replace documents.json with an ingestion pipeline over approved college
    documents (PDF/DOCX circulars, notices) stored in a document repository.
  - Chunk documents and embed them (e.g. sentence-transformers / OpenAI / Bedrock
    embeddings) into a vector store (FAISS, Chroma, pgvector, etc).
  - Replace the keyword scorer below with vector similarity search.
  - Replace the canned `answer` field with an LLM call that generates a grounded
    answer from the retrieved chunks, still returning source citations.
"""
import json
from pathlib import Path

from app.models import Category, Language

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "documents.json"

with open(DATA_PATH, encoding="utf-8") as f:
    DOCUMENTS = json.load(f)

FALLBACK = {
    "en": "I couldn't find an approved document matching your question yet. Please rephrase, or contact the relevant department office. (Retrieval is currently running on a demo document set.)",
    "hi": "आपके प्रश्न से मेल खाता कोई स्वीकृत दस्तावेज़ अभी नहीं मिला। कृपया प्रश्न को दोबारा लिखें या संबंधित विभाग कार्यालय से संपर्क करें। (पुनर्प्राप्ति फिलहाल एक डेमो दस्तावेज़ सेट पर चल रही है।)",
    "mr": "तुमच्या प्रश्नाशी जुळणारा कोणताही मंजूर दस्तऐवज सध्या सापडला नाही. कृपया प्रश्न पुन्हा मांडा किंवा संबंधित विभाग कार्यालयाशी संपर्क साधा. (पुनर्प्राप्ती सध्या डेमो दस्तऐवज संचावर चालू आहे.)",
}


def _score(question: str, doc: dict) -> int:
    q = question.lower()
    return sum(1 for kw in doc["keywords"] if kw.lower() in q)


def retrieve_answer(question: str, language: Language, category: Category | None = None):
    candidates = DOCUMENTS
    if category:
        candidates = [d for d in candidates if d["category"] == category]

    scored = [(d, _score(question, d)) for d in candidates]
    scored = [pair for pair in scored if pair[1] > 0]
    scored.sort(key=lambda pair: pair[1], reverse=True)

    if not scored:
        return {
            "answer": FALLBACK[language],
            "category": category or "notices",
            "sources": [],
            "confidence": 0.0,
            "grounded": False,
        }

    best_doc, best_score = scored[0]
    confidence = min(0.95, 0.4 + 0.15 * best_score)

    return {
        "answer": best_doc["answer"][language],
        "category": best_doc["category"],
        "sources": [best_doc["source"]],
        "confidence": round(confidence, 2),
        "grounded": True,
    }
