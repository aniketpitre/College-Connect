"""
Private file storage for student photos and documents, and notice attachments.

Files are kept in MongoDB (`files` collection) and served only through an authenticated
endpoint that checks who may see them. The type is decided from the file's first bytes, not
from the name or the browser's claim. A different backend (e.g. Vercel Blob with short-lived
links) can replace this module without changing its callers.
"""

import hashlib
from datetime import UTC, datetime
from typing import Any

from bson import Binary, ObjectId
from bson.errors import InvalidId
from pymongo import ASCENDING, IndexModel

from app.core.db import get_db, register_indexes
from app.core.errors import AppError

register_indexes("files", [IndexModel([("student_id", ASCENDING)])])

MAX_BYTES = 2 * 1024 * 1024
_SIGNATURES = {
    b"\xff\xd8\xff": ("image/jpeg", "jpg"),
    b"\x89PNG\r\n\x1a\n": ("image/png", "png"),
    b"%PDF-": ("application/pdf", "pdf"),
}


def sniff(data: bytes) -> tuple[str, str] | None:
    for signature, kind in _SIGNATURES.items():
        if data.startswith(signature):
            return kind
    return None


def save(
    data: bytes,
    *,
    filename: str,
    student_id: ObjectId | None,
    purpose: str,
    created_by: ObjectId,
    images_only: bool = False,
) -> dict[str, Any]:
    if not data:
        raise AppError(422, "The file is empty.", field="file")
    if len(data) > MAX_BYTES:
        raise AppError(413, "The file is too large (2 MB at most).", "file_too_large", "file")
    kind = sniff(data)
    allowed = "a JPG or PNG photo" if images_only else "a PDF, JPG or PNG file"
    if kind is None or (images_only and not kind[0].startswith("image/")):
        raise AppError(415, f"Upload {allowed}.", "unsupported_file", "file")
    content_type, ext = kind
    safe_name = "".join(c for c in filename if c.isalnum() or c in "._- ")[:80].strip() or f"file.{ext}"
    doc = {
        "data": Binary(data),
        "size": len(data),
        "content_type": content_type,
        "filename": safe_name,
        "sha256": hashlib.sha256(data).hexdigest(),
        "student_id": student_id,
        "purpose": purpose,
        "created_at": datetime.now(UTC),
        "created_by": created_by,
    }
    doc["_id"] = get_db().files.insert_one(doc).inserted_id
    return doc


def load(file_id: str) -> dict[str, Any]:
    try:
        oid = ObjectId(file_id)
    except (InvalidId, TypeError) as e:
        raise AppError(404, "File not found.") from e
    doc = get_db().files.find_one({"_id": oid})
    if not doc:
        raise AppError(404, "File not found.")
    return doc
