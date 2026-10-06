"""
In-memory search over the knowledge base.

The knowledge base lives in MongoDB (`kb_chunks`, managed in `app/modules/knowledge`); until the
college first adds a document there, it is the bundled app/data/index.json. Either is small
enough to load into every serverless instance and search with plain Python; each instance
reloads the chunks only when `kb_meta.version` changes. For many thousands of documents, move
the vector search to Atlas Vector Search behind the same `search` methods.

`allowed` (a chunk -> bool filter) keeps each caller to the chunks they may see: the public help
desk only public documents, a signed-in student also their own class's notices, and so on.
"""

import json
import logging
import math
import re
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

from pymongo.errors import PyMongoError

from app.core.db import db_available, get_db
from app.rag.config import INDEX_PATH

log = logging.getLogger(__name__)
Allowed = Callable[[dict], bool]

STOPWORDS = {
    "a",
    "an",
    "the",
    "is",
    "are",
    "was",
    "be",
    "to",
    "of",
    "and",
    "or",
    "in",
    "on",
    "for",
    "by",
    "with",
    "at",
    "from",
    "what",
    "when",
    "where",
    "which",
    "who",
    "how",
    "do",
    "does",
    "i",
    "my",
    "me",
    "can",
    "will",
    "there",
    "this",
    "that",
    "it",
    "any",
    "about",
    "tell",
    "need",
    "want",
    "know",
    "please",
    "get",
    "should",
    "much",
    "many",
}


def _normalize(token: str) -> str:
    # Light stemming so "exams"/"fees"/"documents" match "exam"/"fee"/"document".
    return token[:-1] if len(token) > 3 and token.endswith("s") and not token.endswith("ss") else token


def tokenize(text: str) -> list[str]:
    return [_normalize(t) for t in re.findall(r"\w+", text.lower()) if t not in STOPWORDS]


def _related(a: str, b: str) -> bool:
    """Same word, or one is a prefix of the other ("exam" ~ "examination")."""
    return a == b or (min(len(a), len(b)) >= 4 and (a.startswith(b) or b.startswith(a)))


class Index:
    def __init__(self, data: dict):
        self.embedding_model: str | None = data.get("embedding_model")
        self.chunks: list[dict] = data["chunks"]
        self.has_embeddings = bool(self.embedding_model) and all("embedding" in c for c in self.chunks)

        # BM25 statistics, always available as the keyword fallback.
        self._tokens = [tokenize(f"{c['title']} {c['section']} {c['text']}") for c in self.chunks]
        self._tf = [Counter(toks) for toks in self._tokens]
        self._avg_len = sum(map(len, self._tokens)) / max(len(self._tokens), 1)
        df = Counter(t for toks in self._tokens for t in set(toks))
        n = len(self.chunks)
        self._idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def _candidates(self, category: str | None, allowed: Allowed | None) -> list[int]:
        return [
            i
            for i, c in enumerate(self.chunks)
            if (not category or c["category"] == category) and (allowed is None or allowed(c))
        ]

    def vector_search(
        self, query_vec: list[float], k: int, category: str | None, allowed: Allowed | None = None
    ) -> list[tuple[dict, float]]:
        qn = math.sqrt(sum(x * x for x in query_vec)) or 1.0
        scored = []
        for i in self._candidates(category, allowed):
            v = self.chunks[i]["embedding"]
            vn = math.sqrt(sum(x * x for x in v)) or 1.0
            scored.append((self.chunks[i], sum(a * b for a, b in zip(query_vec, v, strict=True)) / (qn * vn)))
        scored.sort(key=lambda p: p[1], reverse=True)
        return scored[:k]

    def bm25_search(
        self,
        query: str,
        k: int,
        category: str | None,
        allowed: Allowed | None = None,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> list[tuple[dict, float]]:
        # Each query term counts once, through its best-matching related document term.
        expanded = [[v for v in self._idf if _related(t, v)] for t in tokenize(query)]
        scored = []
        for i in self._candidates(category, allowed):
            tf, length = self._tf[i], len(self._tokens[i])
            score = 0.0
            for variants in expanded:
                best = 0.0
                for v in variants:
                    if v in tf:
                        f = tf[v]
                        best = max(best, self._idf[v] * f * (k1 + 1) / (f + k1 * (1 - b + b * length / self._avg_len)))
                score += best
            if score > 0:
                scored.append((self.chunks[i], score))
        scored.sort(key=lambda p: p[1], reverse=True)
        return scored[:k]


@lru_cache(maxsize=1)
def file_index() -> Index:
    """The bundled index (built by scripts/ingest.py from knowledge/)."""
    with open(INDEX_PATH, encoding="utf-8") as f:
        return Index(json.load(f))


_cached: dict[str, Any] = {"version": None, "index": None}


def _embedding_model(chunks: list[dict]) -> str | None:
    """The one model every chunk was embedded with, else None (keyword search until re-indexed)."""
    models = {c.get("em") for c in chunks}
    return next(iter(models)) if len(models) == 1 and None not in models else None


def get_index() -> Index:
    if not db_available():
        return file_index()
    try:
        meta = get_db().kb_meta.find_one({"_id": "kb"})
        if not meta or not meta.get("bootstrapped"):
            return file_index()
        if _cached["version"] != meta.get("version"):
            chunks = list(get_db().kb_chunks.find({}, {"_id": 0, "doc_id": 0}))
            _cached["index"] = Index({"embedding_model": _embedding_model(chunks), "chunks": chunks})
            _cached["version"] = meta.get("version")
    except PyMongoError:
        log.exception("Knowledge base unavailable; answering from the last copy or the bundled index")
    return _cached["index"] or file_index()


def is_live(chunk: dict, now: datetime) -> bool:
    """A notice's chunks count only between its publish time and the end of its expiry day."""
    start, end = chunk.get("publish_at"), chunk.get("expires_at")
    return (start is None or start <= now) and (end is None or end >= now)


def public_only(now: datetime | None = None) -> Allowed:
    """The public help desk: documents marked public (the bundled ones, public uploads and notices)."""
    at = now or datetime.now(UTC)
    return lambda c: c.get("audience", {}).get("kind", "public") == "public" and is_live(c, at)
