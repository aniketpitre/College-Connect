from pathlib import Path

import pytest

from app.rag import chunking
from app.rag.chunking import chunk_file, chunk_knowledge_base


def test_markdown_front_matter_and_sections(tmp_path: Path):
    doc = tmp_path / "fees" / "Notice.md"
    doc.parent.mkdir()
    doc.write_text(
        "---\ntitle: Fee Notice\ndocument: Fee.pdf\n---\n\nIntro text.\n\n## Deadlines\n\nPay by 10 Aug.\n",
        encoding="utf-8",
    )
    chunks = chunk_file(doc, tmp_path)
    assert [(c["section"], c["text"]) for c in chunks] == [("Overview", "Intro text."), ("Deadlines", "Pay by 10 Aug.")]
    assert {c["title"] for c in chunks} == {"Fee Notice"}
    assert {c["document"] for c in chunks} == {"Fee.pdf"}
    assert {c["category"] for c in chunks} == {"fees"}


def test_long_sections_are_split_with_overlap(monkeypatch):
    monkeypatch.setattr(chunking, "CHUNK_MAX_CHARS", 100)
    monkeypatch.setattr(chunking, "CHUNK_OVERLAP_CHARS", 20)
    paragraphs = "\n\n".join(f"Paragraph {i} " + "x" * 40 for i in range(6))
    pieces = chunking.split_long(paragraphs)
    assert len(pieces) > 1
    assert all(len(p) <= 100 for p in pieces)


def test_documents_must_sit_in_a_category_folder(tmp_path: Path):
    doc = tmp_path / "misc" / "x.md"
    doc.parent.mkdir()
    doc.write_text("## A\n\ntext", encoding="utf-8")
    with pytest.raises(ValueError, match="put documents under"):
        chunk_file(doc, tmp_path)


def test_bundled_knowledge_base_matches_committed_index():
    import json

    from app.rag.config import INDEX_PATH, KNOWLEDGE_DIR

    committed = json.loads(INDEX_PATH.read_text(encoding="utf-8"))["chunks"]
    fresh = chunk_knowledge_base(KNOWLEDGE_DIR)
    strip = lambda cs: [{k: v for k, v in c.items() if k != "embedding"} for c in cs]  # noqa: E731
    assert strip(fresh) == strip(committed), "knowledge/ changed: run `python -m scripts.ingest` and commit the index"
