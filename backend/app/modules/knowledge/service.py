"""
The help desk's knowledge base in MongoDB (plan 5.1, 5.2).

- `kb_documents`: one row per document (bundled, uploaded, typed, or a notice) with who may see it.
- `kb_chunks`: the citable sections the help desk searches; each carries the document's
  audience, and a notice's publish and expiry times, so access is checked per chunk.
- `kb_meta` {_id: "kb"}: `bootstrapped` once the bundled documents have been copied in, and a
  `version` token that changes with every edit so each server instance reloads its copy.

The first change copies the bundled index (app/data/index.json) in, so the public help desk keeps
every answer it had. Notices index themselves when published, edited or given a PDF, and are
removed when withdrawn; they stop counting at their expiry without any job (the search checks
the dates). Embeddings are added when VOYAGE_API_KEY is set; until every chunk has one, search is
by keywords. `catch_up` (daily job, and "Re-index" on the page) embeds what is missing and indexes
notices changed while indexing was failing.
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.client_session import ClientSession
from pymongo.errors import PyMongoError

from app.core import audit, files
from app.core.auth import AuthContext
from app.core.db import get_db, register_indexes, run_in_transaction
from app.core.errors import AppError
from app.rag import chunking
from app.rag.config import EMBEDDING_MODEL
from app.rag.embeddings import embed, embeddings_available
from app.rag.pipeline import pipeline_status
from app.rag.store import file_index

log = logging.getLogger(__name__)

register_indexes("kb_chunks", [IndexModel([("doc_id", ASCENDING)])])
register_indexes(
    "kb_documents",
    [
        IndexModel([("notice_id", ASCENDING)], sparse=True),
        IndexModel([("status", ASCENDING), ("created_at", DESCENDING)]),
    ],
)

CATEGORIES = sorted(chunking.CATEGORIES)
MAX_TEXT = 200_000
EMBED_PER_RUN = 256  # chunks embedded per "Re-index" call, to keep each request short
LANGUAGE_SECTIONS = {"hi": "हिंदी", "mr": "मराठी"}


def oid(value: Any, what: str = "Document") -> ObjectId:
    try:
        return ObjectId(str(value))
    except Exception as e:
        raise AppError(404, f"{what} not found.") from e


def _bump(session: ClientSession | None = None) -> None:
    get_db().kb_meta.update_one(
        {"_id": "kb"},
        {"$set": {"version": uuid.uuid4().hex, "updated_at": datetime.now(UTC)}},
        upsert=True,
        session=session,
    )


def bootstrap() -> None:
    """Copies the bundled documents in, once; afterwards the database is the knowledge base."""
    db = get_db()
    meta = db.kb_meta.find_one({"_id": "kb"})
    if meta and meta.get("bootstrapped"):
        return
    bundled = file_index()
    model = bundled.embedding_model if bundled.has_embeddings else None
    by_document: dict[str, list[dict[str, Any]]] = {}
    for c in bundled.chunks:
        by_document.setdefault(c["document"], []).append(c)

    def work(s: ClientSession) -> None:
        meta = db.kb_meta.find_one({"_id": "kb"}, session=s)
        if meta and meta.get("bootstrapped"):
            return  # another request got there first
        now = datetime.now(UTC)
        for document, chunks in by_document.items():
            doc_id = db.kb_documents.insert_one(
                {
                    "title": chunks[0]["title"],
                    "document": document,
                    "category": chunks[0]["category"],
                    "audience": {"kind": "public"},
                    "source": "bundled",
                    "status": "active",
                    "chunks": len(chunks),
                    "created_at": now,
                },
                session=s,
            ).inserted_id
            rows = []
            for c in chunks:
                row = {**c, "doc_id": doc_id, "audience": {"kind": "public"}}
                if model and "embedding" in c:
                    row["em"] = model
                rows.append(row)
            db.kb_chunks.insert_many(rows, session=s)
        db.kb_meta.update_one(
            {"_id": "kb"},
            {"$set": {"bootstrapped": True, "version": uuid.uuid4().hex, "updated_at": now}},
            upsert=True,
            session=s,
        )

    run_in_transaction(work)


def _chunk_rows(doc: dict[str, Any], sections: list[tuple[str, str]], **extra: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for section, text in sections:
        for n, piece in enumerate(chunking.split_long(text.strip())):
            if not piece.strip():
                continue
            rows.append(
                {
                    "id": f"{doc['_id']}::{section}::{n}",
                    "doc_id": doc["_id"],
                    "category": doc["category"],
                    "title": doc["title"],
                    "document": doc["document"],
                    "section": section,
                    "text": piece,
                    "audience": doc["audience"],
                    **extra,
                }
            )
    return rows


def _embed_rows(rows: list[dict[str, Any]]) -> None:
    """Adds embeddings when a key is set; on any failure the rows stay keyword-only (catch_up retries)."""
    if not rows or not embeddings_available():
        return
    try:
        vectors = embed([f"{r['title']} - {r['section']}\n{r['text']}" for r in rows], input_type="document")
    except httpx.HTTPError:
        log.exception("Embedding failed; the document is indexed for keyword search until the next re-index")
        return
    for row, vector in zip(rows, vectors, strict=True):
        row["embedding"] = [round(x, 6) for x in vector]
        row["em"] = EMBEDDING_MODEL


# --- documents --------------------------------------------------------------------------------


def _view(d: dict[str, Any], names: dict[ObjectId, str] | None = None) -> dict[str, Any]:
    return {
        "id": str(d["_id"]),
        "title": d["title"],
        "document": d["document"],
        "category": d["category"],
        "audience": d["audience"]["kind"],
        "source": d["source"],
        "notice_id": str(d["notice_id"]) if d.get("notice_id") else None,
        "chunks": d.get("chunks", 0),
        "created_at": d["created_at"].isoformat(),
        "created_by": (names or {}).get(d["created_by"]) if d.get("created_by") else None,
    }


def list_documents() -> dict[str, Any]:
    bootstrap()
    db = get_db()
    docs = list(db.kb_documents.find({"status": "active"}).sort([("source", ASCENDING), ("created_at", DESCENDING)]))
    ids = {d["created_by"] for d in docs if d.get("created_by")}
    names = {u["_id"]: u["name"] for u in db.users.find({"_id": {"$in": list(ids)}}, {"name": 1})}
    total = db.kb_chunks.count_documents({})
    embedded = db.kb_chunks.count_documents({"em": EMBEDDING_MODEL})
    return {
        "documents": [_view(d, names) for d in docs],
        "status": {
            **pipeline_status(),
            "embeddings_configured": embeddings_available(),
            "chunks_total": total,
            "chunks_embedded": embedded,
        },
        "categories": CATEGORIES,
    }


def sections_from_upload(filename: str, data: bytes) -> list[tuple[str, str]]:
    name = filename.lower()
    if name.endswith(".pdf"):
        try:
            sections = chunking.read_pdf(data)
        except Exception as e:  # pypdf raises many kinds of error on a damaged file
            raise AppError(422, "That PDF could not be read.", field="file") from e
        if not sections:
            raise AppError(
                422, "No text found in that PDF (a scanned page has none): type the text instead.", field="file"
            )
        return sections
    if name.endswith((".md", ".txt")):
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as e:
            raise AppError(422, "Save the file as UTF-8 text.", field="file") from e
        return chunking.split_sections(chunking.parse_front_matter(text)[1])
    raise AppError(415, "Upload a PDF, a .md or a .txt file.", "unsupported_file", "file")


def add_document(
    ctx: AuthContext,
    *,
    title: str,
    category: str,
    audience: str,
    ip: str,
    text: str = "",
    filename: str = "",
    data: bytes | None = None,
) -> dict[str, Any]:
    title = title.strip()
    if len(title) < 3:
        raise AppError(422, "Give the document a title.", field="title")
    if category not in chunking.CATEGORIES:
        raise AppError(422, "Choose the office it belongs to.", field="category")
    if audience not in ("public", "everyone"):
        raise AppError(422, "Choose who may get answers from it.", field="audience")
    if data is not None:
        if len(data) > files.MAX_BYTES:
            raise AppError(413, "The file is too large.", field="file")
        sections = sections_from_upload(filename, data)
        document = filename
    else:
        if not text.strip():
            raise AppError(422, "Upload a file or type the text.", field="text")
        if len(text) > MAX_TEXT:
            raise AppError(422, "The text is too long; split it into several documents.", field="text")
        sections = chunking.split_sections(text)
        document = title
    bootstrap()
    now = datetime.now(UTC)
    doc: dict[str, Any] = {
        "_id": ObjectId(),
        "title": title,
        "document": document,
        "category": category,
        "audience": {"kind": audience},
        "source": "upload" if data is not None else "text",
        "status": "active",
        "created_at": now,
        "created_by": ctx.user_id,
    }
    rows = _chunk_rows(doc, sections)
    if not rows:
        raise AppError(422, "There is no text to index.", field="text")
    doc["chunks"] = len(rows)
    _embed_rows(rows)

    def work(s: ClientSession) -> None:
        get_db().kb_documents.insert_one(doc, session=s)
        get_db().kb_chunks.insert_many(rows, session=s)
        _bump(s)

    run_in_transaction(work)
    audit.record(
        "kb.document_added",
        actor_id=ctx.user_id,
        target_type="kb_document",
        target_id=doc["_id"],
        ip=ip,
        details={"title": title, "audience": audience, "sections": len(rows)},
    )
    return _view(doc)


def remove_document(ctx: AuthContext, doc_id: str, ip: str) -> dict[str, Any]:
    bootstrap()
    db = get_db()
    doc = db.kb_documents.find_one({"_id": oid(doc_id), "status": "active"})
    if not doc:
        raise AppError(404, "Document not found.")
    if doc["source"] == "notice":
        raise AppError(409, "This came from a notice: withdraw the notice or change its expiry instead.", "conflict")

    def work(s: ClientSession) -> None:
        db.kb_chunks.delete_many({"doc_id": doc["_id"]}, session=s)
        db.kb_documents.update_one(
            {"_id": doc["_id"]},
            {"$set": {"status": "removed", "removed_at": datetime.now(UTC), "removed_by": ctx.user_id}},
            session=s,
        )
        _bump(s)

    run_in_transaction(work)
    audit.record(
        "kb.document_removed",
        actor_id=ctx.user_id,
        target_type="kb_document",
        target_id=doc["_id"],
        ip=ip,
        details={"title": doc["title"]},
    )
    return {"ok": True}


# --- notices ----------------------------------------------------------------------------------


def _notice_audience(n: dict[str, Any]) -> dict[str, Any]:
    if n.get("public"):
        return {"kind": "public"}
    return {k: (str(v) if isinstance(v, ObjectId) else v) for k, v in n["audience"].items()}


def _notice_sections(n: dict[str, Any]) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    if n.get("body", "").strip():
        sections.append(("Notice", n["body"]))
    if n.get("attachment_file_id"):
        try:
            pdf = files.load(str(n["attachment_file_id"]))
            sections += [(f"PDF {page}", text) for page, text in chunking.read_pdf(bytes(pdf["data"]))]
        except Exception:  # an unreadable PDF still leaves the typed text answerable
            log.warning("Could not read the PDF of notice %s", n["_id"])
    for lang, label in LANGUAGE_SECTIONS.items():
        t = n.get(lang)
        if t and (t.get("title") or t.get("body")):
            sections.append((label, f"{t.get('title', '')}\n\n{t.get('body', '')}"))
    if not sections:
        sections.append(("Notice", n["title"]))
    return sections


def index_notice(notice_id: ObjectId) -> None:
    """(Re)indexes one notice, or removes it if it is withdrawn. Never raises: publishing must not fail."""
    try:
        _index_notice(notice_id)
    except (PyMongoError, AppError):
        log.exception("Could not index notice %s; the daily job will retry", notice_id)


def _index_notice(notice_id: ObjectId) -> None:
    bootstrap()
    db = get_db()
    n = db.notices.find_one({"_id": notice_id})
    if not n:
        return
    rows: list[dict[str, Any]] = []
    doc: dict[str, Any] | None = None
    if n["status"] == "published":
        published = n["publish_at"].astimezone(UTC)
        doc = {
            "_id": ObjectId(),
            "title": n["title"],
            "document": f"Notice, {published:%d %b %Y}",
            "category": "notices",
            "audience": _notice_audience(n),
            "source": "notice",
            "notice_id": n["_id"],
            "status": "active",
            "created_at": datetime.now(UTC),
            "created_by": n.get("author_id"),
        }
        rows = _chunk_rows(
            doc,
            _notice_sections(n),
            publish_at=n["publish_at"],
            expires_at=n.get("expires_at"),
            link=f"/app/notices/{n['_id']}",
        )
        doc["chunks"] = len(rows)
        _embed_rows(rows)
    indexed_at = datetime.now(UTC)

    def work(s: ClientSession) -> None:
        old = [d["_id"] for d in db.kb_documents.find({"notice_id": n["_id"]}, {"_id": 1}, session=s)]
        db.kb_chunks.delete_many({"doc_id": {"$in": old}}, session=s)
        db.kb_documents.delete_many({"_id": {"$in": old}}, session=s)
        if doc is not None:
            db.kb_documents.insert_one(doc, session=s)
            if rows:
                db.kb_chunks.insert_many(rows, session=s)
        db.notices.update_one({"_id": n["_id"]}, {"$set": {"kb_indexed_at": indexed_at}}, session=s)
        _bump(s)

    run_in_transaction(work)


# --- re-index ---------------------------------------------------------------------------------


def catch_up(limit: int = EMBED_PER_RUN) -> dict[str, Any]:
    """Indexes notices changed since they were last indexed, then embeds chunks that have none."""
    bootstrap()
    db = get_db()
    stale = db.notices.find(
        {
            "$or": [
                {"kb_indexed_at": {"$exists": False}},
                {"$expr": {"$gt": [{"$ifNull": ["$updated_at", "$created_at"]}, "$kb_indexed_at"]}},
            ]
        },
        {"_id": 1},
    ).limit(50)
    notices = 0
    for n in stale:
        index_notice(n["_id"])
        notices += 1
    embedded = 0
    if embeddings_available():
        todo = list(db.kb_chunks.find({"em": {"$ne": EMBEDDING_MODEL}}).limit(limit))
        if todo:
            _embed_rows(todo)
            done = [r for r in todo if r.get("em") == EMBEDDING_MODEL]
            for r in done:
                db.kb_chunks.update_one({"_id": r["_id"]}, {"$set": {"embedding": r["embedding"], "em": r["em"]}})
            embedded = len(done)
            if done:
                _bump()
    remaining = db.kb_chunks.count_documents({"em": {"$ne": EMBEDDING_MODEL}}) if embeddings_available() else 0
    return {"notices": notices, "embedded": embedded, "remaining": remaining}


def reindex(ctx: AuthContext, ip: str) -> dict[str, Any]:
    result = catch_up()
    audit.record("kb.reindexed", actor_id=ctx.user_id, target_type="kb", ip=ip, details=result)
    return result
