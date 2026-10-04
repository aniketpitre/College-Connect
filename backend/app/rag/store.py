"""
In-memory vector store over app/data/index.json.

The index is small enough to load into every serverless instance and search with
plain Python. For thousands of documents, swap this module for a hosted vector DB
(e.g. Postgres + pgvector, Upstash Vector) behind the same `search()` signature.
"""
import json
import math
import re
from collections import Counter
from functools import lru_cache

from app.rag.config import INDEX_PATH

STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "be", "to", "of", "and", "or", "in", "on", "for",
    "by", "with", "at", "from", "what", "when", "where", "which", "who", "how", "do", "does",
    "i", "my", "me", "can", "will", "there", "this", "that", "it", "any", "about", "tell",
}


def tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"\w+", text.lower()) if t not in STOPWORDS]


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

    def _candidates(self, category: str | None) -> list[int]:
        return [i for i, c in enumerate(self.chunks) if not category or c["category"] == category]

    def vector_search(self, query_vec: list[float], k: int, category: str | None) -> list[tuple[dict, float]]:
        qn = math.sqrt(sum(x * x for x in query_vec)) or 1.0
        scored = []
        for i in self._candidates(category):
            v = self.chunks[i]["embedding"]
            vn = math.sqrt(sum(x * x for x in v)) or 1.0
            scored.append((self.chunks[i], sum(a * b for a, b in zip(query_vec, v)) / (qn * vn)))
        scored.sort(key=lambda p: p[1], reverse=True)
        return scored[:k]

    def bm25_search(self, query: str, k: int, category: str | None, k1: float = 1.5, b: float = 0.75) -> list[tuple[dict, float]]:
        q_terms = tokenize(query)
        scored = []
        for i in self._candidates(category):
            tf, length = self._tf[i], len(self._tokens[i])
            score = 0.0
            for t in q_terms:
                if t in tf:
                    f = tf[t]
                    score += self._idf[t] * f * (k1 + 1) / (f + k1 * (1 - b + b * length / self._avg_len))
            if score > 0:
                scored.append((self.chunks[i], score))
        scored.sort(key=lambda p: p[1], reverse=True)
        return scored[:k]


@lru_cache(maxsize=1)
def get_index() -> Index:
    with open(INDEX_PATH, encoding="utf-8") as f:
        return Index(json.load(f))
