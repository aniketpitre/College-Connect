"""
RAG pipeline for CollegeConnect AI: Ask -> Retrieve -> Answer -> Cite.

  ingest (offline, scripts/ingest.py)
    knowledge/**  ->  chunking.py  ->  embeddings.py  ->  app/data/index.json

  query (per request, pipeline.py)
    question -> store.py (vector or BM25 search) -> generator.py (Claude) -> answer + citations
"""
