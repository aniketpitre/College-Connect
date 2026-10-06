"""Turn knowledge-base files into citable chunks."""

import io
import re
from pathlib import Path

from app.rag.config import CHUNK_MAX_CHARS, CHUNK_OVERLAP_CHARS

CATEGORIES = {"admissions", "fees", "examinations", "placements", "hostel", "notices"}


def parse_front_matter(text: str) -> tuple[dict, str]:
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not match:
        return {}, text
    meta = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()
    return meta, text[match.end() :]


def split_sections(body: str) -> list[tuple[str, str]]:
    """Split markdown on '## ' headings -> [(section_title, text)]."""
    sections: list[tuple[str, str]] = []
    current_title = "Overview"
    current_lines: list[str] = []
    for line in body.splitlines():
        if line.startswith("## "):
            if "\n".join(current_lines).strip():
                sections.append((current_title, "\n".join(current_lines).strip()))
            current_title, current_lines = line[3:].strip(), []
        else:
            current_lines.append(line)
    if "\n".join(current_lines).strip():
        sections.append((current_title, "\n".join(current_lines).strip()))
    return sections


def split_long(text: str) -> list[str]:
    """Split text longer than CHUNK_MAX_CHARS on paragraph boundaries, with overlap."""
    if len(text) <= CHUNK_MAX_CHARS:
        return [text]
    pieces, current = [], ""
    for para in re.split(r"\n\s*\n", text):
        if current and len(current) + len(para) + 2 > CHUNK_MAX_CHARS:
            pieces.append(current.strip())
            current = current[-CHUNK_OVERLAP_CHARS:] + "\n\n"
        current += para + "\n\n"
    if current.strip():
        pieces.append(current.strip())
    # A single paragraph can still exceed the limit; hard-split it.
    out: list[str] = []
    for piece in pieces:
        step = CHUNK_MAX_CHARS - CHUNK_OVERLAP_CHARS
        out.extend(piece[i : i + CHUNK_MAX_CHARS] for i in range(0, len(piece), step))
    return out


def read_pdf(source: Path | bytes) -> list[tuple[str, str]]:
    """[("Page n", text)] for the pages that have text (a scanned PDF has none)."""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(source) if isinstance(source, bytes) else str(source))
    pages = [(f"Page {i}", page.extract_text() or "") for i, page in enumerate(reader.pages, start=1)]
    return [(section, text) for section, text in pages if text.strip()]


def chunk_file(path: Path, knowledge_dir: Path) -> list[dict]:
    category = path.relative_to(knowledge_dir).parts[0]
    if category not in CATEGORIES:
        raise ValueError(f"{path}: put documents under one of {sorted(CATEGORIES)}/")

    meta: dict[str, str] = {}
    if path.suffix.lower() == ".pdf":
        sections = read_pdf(path)
    else:
        meta, body = parse_front_matter(path.read_text(encoding="utf-8"))
        sections = split_sections(body)

    title = meta.get("title", path.stem.replace("_", " "))
    document = meta.get("document", path.name)

    chunks = []
    for section, text in sections:
        for n, piece in enumerate(split_long(text)):
            chunks.append(
                {
                    "id": f"{path.stem}::{section}::{n}",
                    "category": meta.get("category", category),
                    "title": title,
                    "document": document,
                    "section": section,
                    "text": piece,
                }
            )
    return chunks


def chunk_knowledge_base(knowledge_dir: Path) -> list[dict]:
    files = sorted(
        p for p in knowledge_dir.rglob("*") if p.suffix.lower() in {".md", ".txt", ".pdf"} and p.parent != knowledge_dir
    )
    return [chunk for f in files for chunk in chunk_file(f, knowledge_dir)]
