import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent

try:  # local dev: read backend/.env (on Vercel, set these in Project Settings -> Environment Variables)
    from dotenv import load_dotenv

    load_dotenv(BACKEND_DIR / ".env")
except ImportError:
    pass
KNOWLEDGE_DIR = BACKEND_DIR / "knowledge"
INDEX_PATH = BACKEND_DIR / "app" / "data" / "index.json"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.getenv("RAG_CLAUDE_MODEL", "claude-opus-5-5")
# Short, grounded Q&A does well at low effort; raise to "medium"/"high" if answers need more reasoning.
CLAUDE_EFFORT = os.getenv("RAG_CLAUDE_EFFORT", "low")

VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY")
# Multilingual embedding model, so Hindi/Marathi questions match English documents.
EMBEDDING_MODEL = os.getenv("RAG_EMBEDDING_MODEL", "voyage-3.5")

TOP_K = int(os.getenv("RAG_TOP_K", "4"))
# Chunks below this cosine similarity are not passed to the LLM.
MIN_SIMILARITY = float(os.getenv("RAG_MIN_SIMILARITY", "0.3"))

CHUNK_MAX_CHARS = 1200
CHUNK_OVERLAP_CHARS = 150
