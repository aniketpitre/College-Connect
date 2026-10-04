"""Voyage AI embeddings (Anthropic's recommended embeddings provider), called over plain HTTPS."""

import httpx

from app.rag.config import EMBEDDING_MODEL, VOYAGE_API_KEY

VOYAGE_URL = "https://api.voyageai.com/v1/embeddings"
BATCH_SIZE = 64


def embeddings_available() -> bool:
    return bool(VOYAGE_API_KEY)


def embed(texts: list[str], input_type: str, model: str = EMBEDDING_MODEL) -> list[list[float]]:
    """input_type is "document" for indexing and "query" for search."""
    vectors: list[list[float]] = []
    with httpx.Client(timeout=30) as client:
        for i in range(0, len(texts), BATCH_SIZE):
            res = client.post(
                VOYAGE_URL,
                headers={"Authorization": f"Bearer {VOYAGE_API_KEY}"},
                json={"input": texts[i : i + BATCH_SIZE], "model": model, "input_type": input_type},
            )
            res.raise_for_status()
            data = sorted(res.json()["data"], key=lambda d: d["index"])
            vectors.extend(d["embedding"] for d in data)
    return vectors
