import logging
import uuid
import json
from io import BytesIO

from app.core.database import SessionLocal
from app.db.models.ingestion import IngestionJob
from app.agents.cv_ingestion.graph import ingestion_app
from app.agents.cv_ingestion.state import CVIngestionState

logger = logging.getLogger(__name__)

def process_cv_job(
    job_id: str,
    candidate_id: str,
    file_path: str,
    document_id: str | None = None,
):
    """Run CV ingestion for one job.

    Declared as a plain ``def`` (NOT ``async def``) on purpose: the body is
    fully blocking — ``ingestion_app.invoke()`` runs the LangGraph nodes,
    including synchronous LLM/embedding HTTP calls to Ollama that can take
    several minutes. FastAPI runs sync ``BackgroundTasks`` in a worker
    thread, so this keeps the asyncio event loop free. If this were
    ``async def`` it would run on the event loop and freeze the whole
    server (no requests served) for the duration of every ingestion.
    """
    db = SessionLocal()
    try:
        job = db.get(IngestionJob, uuid.UUID(job_id))
        if not job:
            return
            
        initial_state: CVIngestionState = {
            "job_id": job_id,
            "candidate_id": candidate_id,
            "document_id": document_id,
            "file_path": file_path,
            "raw_text": None,
            "structured_candidate": None,
            "normalized_candidate": None,
            "chunks": None,
            "embeddings": None,
            "errors": [],
            "status": "running",
            "stage": "started"
        }
        
        # Update job
        job.status = "running"
        db.commit()
        
        # Run graph
        final_state = ingestion_app.invoke(initial_state)
        
        # Update job completion
        job = db.get(IngestionJob, uuid.UUID(job_id)) # refresh
        job.status = final_state.get("status", "failed")
        job.stage = final_state.get("stage", "done")
        
        if final_state.get("errors"):
            job.error_message = "\n".join(final_state["errors"])
        
        # if newly created
        if final_state.get("candidate_id") and job.candidate_id is None:
            job.candidate_id = uuid.UUID(final_state["candidate_id"])
        if final_state.get("document_id"):
            job.document_id = uuid.UUID(final_state["document_id"])
            
        db.commit()
    except Exception as e:
        logger.exception("Job processing failed catastrophically.")
        job = db.get(IngestionJob, uuid.UUID(job_id))
        if job:
            job.status = "failed"
            job.error_message = str(e)
            db.commit()
    finally:
        db.close()
