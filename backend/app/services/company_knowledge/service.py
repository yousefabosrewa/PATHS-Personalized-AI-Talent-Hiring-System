"""
PATHS Backend — Company knowledge ingestion + RAG indexing (fix2_1.md).

Pipeline for an uploaded company file:

  1. Extract text safely (PDF / DOCX / TXT / MD / CSV).
  2. Chunk the text.
  3. Embed chunks with the local Ollama model.
  4. Upsert into the org-scoped ``company_knowledge`` Qdrant collection,
     tagging each chunk with organization_id + file_id + category +
     legal/compliance flag so retrieval stays inside one organisation.

Failures never crash the request — the file row is marked ``failed`` with
an ``error_message`` and the recruiter can re-index from the UI.
"""

from __future__ import annotations

import csv
import logging
import uuid
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

from qdrant_client.http.models import Distance, VectorParams

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.db.models.company_knowledge import CompanyKnowledgeFile
from app.services.embedding_service import embed_documents, embed_query
from app.services.qdrant_service import QdrantService

logger = logging.getLogger(__name__)
_settings = get_settings()

COMPANY_KNOWLEDGE_COLLECTION = "company_knowledge"

_CHUNK_SIZE = 1200
_CHUNK_OVERLAP = 150


# ── Text extraction ──────────────────────────────────────────────────────


def extract_text(path: str | Path, file_type: str) -> str:
    """Extract plain text from a company file. Returns "" on unknown types."""
    p = Path(path)
    ext = (file_type or p.suffix.lstrip(".")).lower()

    if ext in ("txt", "md", "markdown"):
        return p.read_text(encoding="utf-8", errors="replace")

    if ext == "csv":
        rows = []
        with p.open("r", encoding="utf-8-sig", errors="replace", newline="") as fh:
            for row in csv.reader(fh):
                rows.append(", ".join(cell.strip() for cell in row if cell))
        return "\n".join(rows)

    if ext == "pdf":
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(p))
            parts = []
            for page in reader.pages:
                try:
                    parts.append(page.extract_text() or "")
                except Exception:  # noqa: BLE001
                    continue
            return "\n".join(parts)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[CompanyKnowledge] PDF extraction failed: %s", exc)
            return ""

    if ext in ("docx", "doc"):
        try:
            import docx  # python-docx

            document = docx.Document(str(p))
            return "\n".join(par.text for par in document.paragraphs if par.text)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[CompanyKnowledge] DOCX extraction failed: %s", exc)
            return ""

    # Fallback: try reading as text.
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return ""


def _chunk(text: str) -> list[str]:
    cleaned = " ".join(text.split())
    if not cleaned:
        return []
    chunks: list[str] = []
    start = 0
    n = len(cleaned)
    while start < n:
        end = min(start + _CHUNK_SIZE, n)
        chunks.append(cleaned[start:end])
        if end >= n:
            break
        start = end - _CHUNK_OVERLAP
    return chunks


# ── Qdrant helpers ───────────────────────────────────────────────────────


def _ensure_collection(qdrant: QdrantService) -> None:
    size = _settings.qdrant_collection_vector_size
    try:
        qdrant.client.get_collection(COMPANY_KNOWLEDGE_COLLECTION)
    except Exception:  # noqa: BLE001
        qdrant.client.create_collection(
            collection_name=COMPANY_KNOWLEDGE_COLLECTION,
            vectors_config=VectorParams(size=size, distance=Distance.COSINE),
        )
        logger.info(
            "[CompanyKnowledge] created Qdrant collection '%s' (dim=%d)",
            COMPANY_KNOWLEDGE_COLLECTION, size,
        )


def _point_id(file_id: uuid.UUID, idx: int) -> str:
    # Deterministic per (file, chunk) so re-indexing overwrites cleanly.
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"company-file:{file_id}:{idx}"))


def index_company_file(file_row: CompanyKnowledgeFile) -> int:
    """Extract → chunk → embed → upsert. Returns the chunk count indexed."""
    text = extract_text(file_row.storage_path, file_row.file_type)
    chunks = _chunk(text)
    if not chunks:
        return 0

    vectors = embed_documents(chunks)
    payloads = [
        {
            "organization_id": str(file_row.organization_id),
            "file_id": str(file_row.id),
            "file_name": file_row.file_name,
            "category": file_row.category,
            "is_legal_or_compliance_context": bool(
                file_row.is_legal_or_compliance_context
            ),
            "chunk_index": idx,
            "text": chunk,
            "source": file_row.file_name,
        }
        for idx, chunk in enumerate(chunks)
    ]
    ids = [_point_id(file_row.id, idx) for idx in range(len(chunks))]

    qdrant = QdrantService()
    _ensure_collection(qdrant)
    # Clear any previous vectors for this file before re-indexing.
    remove_company_file_vectors(file_row.id, qdrant=qdrant)
    qdrant.upsert_vectors(
        COMPANY_KNOWLEDGE_COLLECTION, vectors, payloads, ids=ids,
    )
    return len(chunks)


def remove_company_file_vectors(
    file_id: uuid.UUID, *, qdrant: QdrantService | None = None,
) -> None:
    """Delete all vectors belonging to a company file (best-effort)."""
    qdrant = qdrant or QdrantService()
    try:
        from qdrant_client.http.models import (
            FieldCondition,
            Filter,
            FilterSelector,
            MatchValue,
        )

        qdrant.client.delete(
            collection_name=COMPANY_KNOWLEDGE_COLLECTION,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[
                        FieldCondition(
                            key="file_id",
                            match=MatchValue(value=str(file_id)),
                        )
                    ]
                )
            ),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[CompanyKnowledge] could not delete vectors for file %s: %s",
            file_id, exc,
        )


def search_company_knowledge(
    organization_id: uuid.UUID,
    query: str,
    *,
    limit: int = 5,
    include_legal: bool = True,
) -> list[dict]:
    """Org-scoped semantic search over company knowledge for agents.

    Always filters by organization_id so one org never reads another's
    files. When ``include_legal`` is False, legal/compliance chunks are
    excluded (used by candidate-facing flows).
    """
    qdrant = QdrantService()
    try:
        vector = embed_query(query)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[CompanyKnowledge] query embedding failed: %s", exc)
        return []
    filters: dict = {"organization_id": str(organization_id)}
    if not include_legal:
        filters["is_legal_or_compliance_context"] = False
    try:
        return qdrant.search_vectors(
            COMPANY_KNOWLEDGE_COLLECTION, vector, limit=limit, filters=filters,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("[CompanyKnowledge] search failed: %s", exc)
        return []


# ── Background job ───────────────────────────────────────────────────────


def process_company_file_job(file_id: str) -> None:
    """Background task: index one uploaded company file."""
    db = SessionLocal()
    try:
        row = db.get(CompanyKnowledgeFile, uuid.UUID(file_id))
        if row is None:
            return
        row.status = "processing"
        db.commit()
        try:
            count = index_company_file(row)
        except Exception as exc:  # noqa: BLE001
            logger.exception("[CompanyKnowledge] indexing failed for %s", file_id)
            row.status = "failed"
            row.error_message = str(exc)[:500]
            db.commit()
            return
        row.chunk_count = count
        row.status = "indexed" if count > 0 else "failed"
        row.error_message = None if count > 0 else "No extractable text found."
        row.indexed_at = datetime.now(timezone.utc)
        db.commit()
        logger.info(
            "[CompanyKnowledge] indexed file %s (%d chunks)", file_id, count,
        )
    finally:
        db.close()
