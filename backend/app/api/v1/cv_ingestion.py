import os
import uuid
import shutil
from fastapi import APIRouter, Depends, File, Form, UploadFile, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.database import get_db
from app.db.models.candidate import Candidate
from app.db.models.cv_entities import CandidateDocument
from app.db.models.ingestion import IngestionJob
from app.services.cv_ingestion_service import process_cv_job
from app.core.config import get_settings

router = APIRouter(prefix="/cv-ingestion", tags=["CV Ingestion"])
settings = get_settings()

# Allowed MIME signatures (magic bytes) — PATHS-172
_ALLOWED_MIMES = {
    b"%PDF": "application/pdf",
    b"PK\x03\x04": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
    b"\xd0\xcf\x11\xe0": "application/msword",  # legacy .doc
}
_MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


def _sniff_mime(header: bytes) -> str | None:
    """Return MIME type if the magic bytes match an allowed type, else None."""
    for magic, mime in _ALLOWED_MIMES.items():
        if header.startswith(magic):
            return mime
    return None


@router.post("/upload")
async def upload_cv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    # `candidate_id` arrives as multipart form data alongside the file (both
    # frontend callers append it to FormData). It MUST be declared as Form(...)
    # — a bare param would be read as a query string and silently ignored,
    # leaving the uploaded CV unlinked from the candidate's profile.
    candidate_id: str | None = Form(None),
    db: Session = Depends(get_db)
):
    # Read first 8 bytes for MIME sniffing — PATHS-172
    header = await file.read(8)
    mime = _sniff_mime(header)
    if mime is None:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Only PDF and Word documents are accepted.",
        )

    # Read remainder and enforce size limit
    rest = await file.read()
    total_size = len(header) + len(rest)
    if total_size > _MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum allowed size is {_MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB.",
        )

    upload_dir = os.getenv("UPLOAD_DIR", "./uploads")
    os.makedirs(upload_dir, exist_ok=True)

    file_path = os.path.join(upload_dir, f"{uuid.uuid4()}_{file.filename}")
    with open(file_path, "wb") as buffer:
        buffer.write(header + rest)
        
    cand_uuid = uuid.UUID(candidate_id) if candidate_id else None

    job = IngestionJob(
        candidate_id=cand_uuid,
        status="pending",
        stage="uploaded"
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Create the document row up front (when the candidate already exists) so
    # the uploaded file appears in "Uploaded Files" immediately — independent
    # of whether the background extraction later succeeds. The pipeline's
    # persist step upserts this same row to add the extracted text.
    document_id: str | None = None
    if cand_uuid is not None and db.get(Candidate, cand_uuid) is not None:
        try:
            doc = CandidateDocument(
                candidate_id=cand_uuid,
                document_type="cv",
                original_filename=file.filename or os.path.basename(file_path),
                mime_type=mime,
                storage_path_or_url=file_path,
            )
            db.add(doc)
            db.commit()
            db.refresh(doc)
            document_id = str(doc.id)
            job.document_id = doc.id
            db.commit()
        except Exception:
            db.rollback()  # never block the upload on the early-doc convenience

    cand_id_str = str(cand_uuid) if cand_uuid else None

    background_tasks.add_task(
        process_cv_job, str(job.id), cand_id_str, file_path, document_id,
    )

    return {
        "job_id": str(job.id),
        "candidate_id": str(job.candidate_id) if job.candidate_id else None,
        "document_id": document_id,
        "status": "pending"
    }

@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str, db: Session = Depends(get_db)):
    job = db.get(IngestionJob, uuid.UUID(job_id))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    return {
        "job_id": str(job.id),
        "candidate_id": str(job.candidate_id) if job.candidate_id else None,
        "document_id": str(job.document_id) if job.document_id else None,
        "stage": job.stage,
        "status": job.status,
        "error_message": job.error_message
    }
