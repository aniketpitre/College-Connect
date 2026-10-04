# Knowledge base

Approved college documents that the RAG pipeline answers from. Put each file in
the folder for its category (`admissions/`, `fees/`, `examinations/`,
`placements/`, `hostel/`, `notices/`).

Supported formats:

- **Markdown / text** (`.md`, `.txt`): optional front matter with `title` and
  `document` (the name shown in the citation card). Each `## Heading` becomes a
  citable section.
- **PDF** (`.pdf`): text is extracted page by page; each page becomes a citable
  section ("Page N"). Scanned PDFs need OCR first.

After adding or changing documents, rebuild the index:

```
cd backend
python -m scripts.ingest            # chunks + embeddings (needs VOYAGE_API_KEY)
python -m scripts.ingest --no-embed # chunks only (keyword/BM25 retrieval)
```

Commit the regenerated `app/data/index.json` so the deployment picks it up.
