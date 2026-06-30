"""
PATHS Backend — System / bootstrap endpoints.

These endpoints are for initial setup & testing only.
Protect or remove them before production.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.age_service import AGEService
from app.services.qdrant_service import QdrantService
from app.services.embedding_service import embed_query

router = APIRouter(prefix="/system", tags=["System"])


# ── Apache AGE ─────────────────────────────────────────────────────────

@router.post("/age/init-graph")
def age_init_graph():
    """Initialize the application graph in Apache AGE."""
    return AGEService.init_graph()


@router.get("/age/sample-query")
def age_sample_query():
    """Run a sample Cypher query to verify AGE is working."""
    return AGEService.sample_query()


# ── Qdrant ─────────────────────────────────────────────────────────────

@router.post("/qdrant/init-collections")
def qdrant_init_collections():
    """Create all configured Qdrant collections if missing."""
    svc = QdrantService()
    return svc.init_collections()


@router.get("/qdrant/collections")
def qdrant_list_collections():
    """List all existing Qdrant collections."""
    svc = QdrantService()
    return {"collections": svc.list_collections()}


@router.get("/qdrant/collections/{name}")
def qdrant_get_collection(name: str):
    """Get detailed info about a specific Qdrant collection."""
    svc = QdrantService()
    return svc.get_collection_info(name)


# ── RAG / Semantic search ───────────────────────────────────────────────

class VectorSearchRequest(BaseModel):
    collection: str
    query: str
    limit: int = 5


class VectorSearchHit(BaseModel):
    id: str
    score: float
    payload: dict


@router.post("/qdrant/search", response_model=list[VectorSearchHit])
def qdrant_search(body: VectorSearchRequest):
    """
    Embed *query* using the local Ollama model and run a similarity search
    against the specified Qdrant collection.

    Returns the top-*limit* nearest neighbours with their payloads.
    """
    if not body.query.strip():
        raise HTTPException(status_code=422, detail="query must not be empty")

    try:
        vector = embed_query(body.query)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Embedding service unavailable: {exc}",
        ) from exc

    svc = QdrantService()
    try:
        hits = svc.search_vectors(
            collection_name=body.collection,
            query_vector=vector,
            limit=max(1, min(body.limit, 20)),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Qdrant search failed: {exc}",
        ) from exc

    return [VectorSearchHit(id=h["id"], score=h["score"], payload=h["payload"]) for h in hits]
