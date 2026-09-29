from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import meta, query

app = FastAPI(
    title="CollegeConnect AI API",
    description="Backend skeleton for CollegeConnect AI. Retrieval currently runs on a small "
    "demo document set (app/data/documents.json) with keyword matching, not a live "
    "RAG pipeline. See app/services/retrieval.py for the integration point.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(query.router)
app.include_router(meta.router)
