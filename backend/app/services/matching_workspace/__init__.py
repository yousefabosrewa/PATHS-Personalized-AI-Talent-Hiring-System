"""PATHS Matching Workspace services (fix7.md).

Adds two HR-side capabilities on top of the existing infrastructure
(Qdrant + embeddings + OpenRouter agent):

  * :pyfunc:`semantic_search` — natural-language candidate search using
    the existing one-vector-per-candidate Qdrant collection, with a
    per-result agent explanation grounded in real profile data.
  * :pyfunc:`run_rag_test` — RAG-grounded candidate-vs-requirement test:
    retrieves the most relevant evidence chunks from each candidate's
    profile, passes them to the LLM, returns a structured rubric.

Both endpoints respect org-scope, never bypass the de-anonymization
workflow, and degrade gracefully when Qdrant / Ollama / OpenRouter is
unavailable (numeric scores + a "could not be generated" message).
"""

from .semantic import semantic_search, SemanticSearchResult
from .rag_test import run_rag_test, RagTestResult

__all__ = [
    "semantic_search",
    "SemanticSearchResult",
    "run_rag_test",
    "RagTestResult",
]
