"""
PATHS Backend — Company Knowledge File endpoints (fix2_1.md Feature 1).

Mounted under /api/v1:

  POST   /organizations/{org_id}/knowledge-files          upload + index
  GET    /organizations/{org_id}/knowledge-files          list
  POST   /organizations/{org_id}/knowledge-files/{id}/reindex
  DELETE /organizations/{org_id}/knowledge-files/{id}

All routes are org-scoped via ``get_current_hiring_org_context`` so only
organisation staff can upload/list/delete, and one org never sees another's
files. Legal/compliance files are flagged read-only context.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime
from typing import Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.dependencies import (
    OrgContext,
    get_current_hiring_org_context,
    require_active_org_status,
)
from app.db.models.company_knowledge import (
    COMPANY_FILE_CATEGORIES,
    LEGAL_CATEGORY,
    CompanyKnowledgeFile,
)
from app.services.company_knowledge import (
    process_company_file_job,
    remove_company_file_vectors,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Company Knowledge"])
_settings = get_settings()

_MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB
_ALLOWED_EXTENSIONS = {"pdf", "docx", "doc", "txt", "md", "markdown", "csv"}


# ── Schemas ──────────────────────────────────────────────────────────────


class CompanyFileOut(BaseModel):
    id: str
    file_name: str
    file_type: str
    file_size: int
    category: str
    description: Optional[str] = None
    status: str
    is_legal_or_compliance_context: bool
    chunk_count: int
    error_message: Optional[str] = None
    uploaded_by_user_id: Optional[str] = None
    created_at: datetime
    indexed_at: Optional[datetime] = None


class CompanyFileListOut(BaseModel):
    total: int
    items: list[CompanyFileOut]


class CategoryOut(BaseModel):
    categories: list[str] = Field(default_factory=lambda: list(COMPANY_FILE_CATEGORIES))


# ── Helpers ──────────────────────────────────────────────────────────────


def _serialize(row: CompanyKnowledgeFile) -> CompanyFileOut:
    return CompanyFileOut(
        id=str(row.id),
        file_name=row.file_name,
        file_type=row.file_type,
        file_size=row.file_size,
        category=row.category,
        description=row.description,
        status=row.status,
        is_legal_or_compliance_context=row.is_legal_or_compliance_context,
        chunk_count=row.chunk_count,
        error_message=row.error_message,
        uploaded_by_user_id=str(row.uploaded_by_user_id) if row.uploaded_by_user_id else None,
        created_at=row.created_at,
        indexed_at=row.indexed_at,
    )


def _check_org(org_id: uuid.UUID, ctx: OrgContext) -> None:
    if org_id != ctx.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage your own organisation's company files.",
        )


# ── Routes ───────────────────────────────────────────────────────────────


@router.get(
    "/organizations/{organization_id}/knowledge-files/categories",
    response_model=CategoryOut,
)
def list_categories(
    organization_id: uuid.UUID,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    _: OrgContext = Depends(require_active_org_status),
) -> CategoryOut:
    _check_org(organization_id, ctx)
    return CategoryOut()


@router.get(
    "/organizations/{organization_id}/knowledge-files",
    response_model=CompanyFileListOut,
)
def list_company_files(
    organization_id: uuid.UUID,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    _: OrgContext = Depends(require_active_org_status),
    db: Session = Depends(get_db),
) -> CompanyFileListOut:
    _check_org(organization_id, ctx)
    rows = db.execute(
        select(CompanyKnowledgeFile)
        .where(CompanyKnowledgeFile.organization_id == organization_id)
        .order_by(CompanyKnowledgeFile.created_at.desc())
    ).scalars().all()
    return CompanyFileListOut(total=len(rows), items=[_serialize(r) for r in rows])


@router.post(
    "/organizations/{organization_id}/knowledge-files",
    response_model=CompanyFileOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_company_file(
    organization_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    category: str = Form("other"),
    description: Optional[str] = Form(None),
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    _: OrgContext = Depends(require_active_org_status),
    db: Session = Depends(get_db),
) -> CompanyFileOut:
    _check_org(organization_id, ctx)

    file_name = file.filename or "company-file"
    ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=(
                "Unsupported file type. Allowed: PDF, DOCX, TXT, MD, CSV."
            ),
        )

    data = await file.read()
    if len(data) > _MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large (max {_MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB).",
        )

    if category not in COMPANY_FILE_CATEGORIES:
        category = "other"

    upload_dir = os.path.join(
        _settings.upload_dir, "company_knowledge", str(organization_id),
    )
    os.makedirs(upload_dir, exist_ok=True)
    file_id = uuid.uuid4()
    storage_path = os.path.join(upload_dir, f"{file_id}_{file_name}")
    with open(storage_path, "wb") as fh:
        fh.write(data)

    row = CompanyKnowledgeFile(
        id=file_id,
        organization_id=organization_id,
        uploaded_by_user_id=ctx.user.id,
        file_name=file_name,
        file_type=ext,
        file_size=len(data),
        storage_path=storage_path,
        category=category,
        description=(description or "").strip() or None,
        status="uploaded",
        is_legal_or_compliance_context=(category == LEGAL_CATEGORY),
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    background_tasks.add_task(process_company_file_job, str(row.id))
    return _serialize(row)


@router.post(
    "/organizations/{organization_id}/knowledge-files/{file_id}/reindex",
    response_model=CompanyFileOut,
)
def reindex_company_file(
    organization_id: uuid.UUID,
    file_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    _: OrgContext = Depends(require_active_org_status),
    db: Session = Depends(get_db),
) -> CompanyFileOut:
    _check_org(organization_id, ctx)
    row = db.get(CompanyKnowledgeFile, file_id)
    if row is None or row.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="File not found")
    row.status = "processing"
    row.error_message = None
    db.commit()
    db.refresh(row)
    background_tasks.add_task(process_company_file_job, str(row.id))
    return _serialize(row)


@router.delete(
    "/organizations/{organization_id}/knowledge-files/{file_id}",
    status_code=status.HTTP_200_OK,
)
def delete_company_file(
    organization_id: uuid.UUID,
    file_id: uuid.UUID,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    _: OrgContext = Depends(require_active_org_status),
    db: Session = Depends(get_db),
) -> dict:
    _check_org(organization_id, ctx)
    row = db.get(CompanyKnowledgeFile, file_id)
    if row is None or row.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="File not found")

    # Remove vectors, then the stored file, then the DB row.
    remove_company_file_vectors(row.id)
    try:
        if row.storage_path and os.path.exists(row.storage_path):
            os.remove(row.storage_path)
    except OSError as exc:
        logger.warning("Could not remove company file %s: %s", row.storage_path, exc)

    db.delete(row)
    db.commit()
    return {"deleted": True, "id": str(file_id)}
