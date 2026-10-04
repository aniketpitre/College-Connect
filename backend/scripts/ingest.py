"""
Build app/data/index.json from the documents in knowledge/.

    cd backend
    python -m scripts.ingest              # chunk + embed (requires VOYAGE_API_KEY)
    python -m scripts.ingest --no-embed   # chunk only; the API then uses keyword (BM25) retrieval
"""
import argparse
import json
import sys

from app.rag.chunking import chunk_knowledge_base
from app.rag.config import EMBEDDING_MODEL, INDEX_PATH, KNOWLEDGE_DIR
from app.rag.embeddings import embed, embeddings_available


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--no-embed", action="store_true", help="skip embeddings (BM25-only index)")
    args = parser.parse_args()

    chunks = chunk_knowledge_base(KNOWLEDGE_DIR)
    if not chunks:
        print(f"No documents found under {KNOWLEDGE_DIR}", file=sys.stderr)
        return 1
    print(f"Chunked {len(chunks)} sections from {len({c['document'] for c in chunks})} documents")

    embedding_model = None
    if not args.no_embed:
        if not embeddings_available():
            print("VOYAGE_API_KEY is not set. Set it, or pass --no-embed for a keyword-only index.", file=sys.stderr)
            return 1
        texts = [f"{c['title']} - {c['section']}\n{c['text']}" for c in chunks]
        for chunk, vector in zip(chunks, embed(texts, input_type="document")):
            chunk["embedding"] = [round(x, 6) for x in vector]
        embedding_model = EMBEDDING_MODEL
        print(f"Embedded {len(chunks)} chunks with {EMBEDDING_MODEL}")

    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump({"embedding_model": embedding_model, "chunks": chunks}, f, ensure_ascii=False, indent=1)
    print(f"Wrote {INDEX_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
