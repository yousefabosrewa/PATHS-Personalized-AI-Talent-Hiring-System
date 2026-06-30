"""Company knowledge file ingestion + RAG indexing (fix2_1.md Feature 1)."""

from app.services.company_knowledge.service import (
    COMPANY_KNOWLEDGE_COLLECTION,
    extract_text,
    index_company_file,
    process_company_file_job,
    remove_company_file_vectors,
    search_company_knowledge,
)

__all__ = [
    "COMPANY_KNOWLEDGE_COLLECTION",
    "extract_text",
    "index_company_file",
    "process_company_file_job",
    "remove_company_file_vectors",
    "search_company_knowledge",
]
