"""
PATHS Backend — Admin endpoints for the hourly Job_Scraper-main pipeline.

Routes:
  POST /admin/job-import/run-once    — trigger one import run
  GET  /admin/job-import/status      — scheduler + last-run summary
  GET  /admin/job-import/history     — recent `job_import_runs` rows

All endpoints require account_type='platform_admin' (tightened during the
platform-admin / RBAC overhaul; was previously unauthenticated).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.dependencies import require_platform_admin
from app.db.repositories import job_scraper_repo as repo
from app.schemas.job_scraper import (
    JobImportResult,
    JobImportRunRequest,
    JobImportRunSummary,
    JobImportStatus,
)
from app.services.job_scraper.job_import_service import JobImportService
from app.services.job_scraper.scheduler import scheduler as job_scheduler

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin/job-import",
    tags=["Admin — Job Import"],
    dependencies=[Depends(require_platform_admin)],
)
settings = get_settings()


def _to_summary(run) -> JobImportRunSummary:
    return JobImportRunSummary(
        id=str(run.id),
        source_platform=run.source_platform,
        started_at=run.started_at,
        finished_at=run.finished_at,
        requested_limit=run.requested_limit,
        scraped_count=run.scraped_count or 0,
        valid_count=run.valid_count or 0,
        inserted_count=run.inserted_count or 0,
        updated_count=run.updated_count or 0,
        skipped_count=run.skipped_count or 0,
        failed_count=run.failed_count or 0,
        graph_synced_count=run.graph_synced_count or 0,
        vector_synced_count=run.vector_synced_count or 0,
        status=run.status,
        error_message=run.error_message,
    )


@router.post(
    "/run-once",
    response_model=JobImportResult,
    summary="Trigger one immediate Job_Scraper-main import run.",
)
async def run_once(
    body: JobImportRunRequest = Body(default_factory=JobImportRunRequest),
):
    """Run the scraper → normalize → PG → AGE → Qdrant pipeline once.

    Batch size is capped by ``JOB_SCRAPER_BATCH_SIZE`` / ``LINKEDIN_JOBS_PER_HOUR``
    unless ``admin_override`` is used inside the service.
    """
    service = JobImportService()
    try:
        result = await service.run_import(
            limit=body.limit,
            source=body.source,
            admin_override=False,
            keyword=body.keyword,
            location=body.location,
        )
    except Exception as exc:
        logger.exception("Manual job-import run failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"job_import_failed: {exc}",
        ) from exc
    return result


@router.get(
    "/status",
    response_model=JobImportStatus,
    summary="Scheduler config + last run summary.",
)
def get_status(db: Session = Depends(get_db)) -> JobImportStatus:
    last = repo.get_latest_import_run(db)
    return JobImportStatus(
        enabled=settings.job_scraper_enabled,
        interval_minutes=settings.job_scraper_interval_minutes,
        batch_size=settings.job_scraper_batch_size,
        source=settings.job_scraper_source,
        last_run=_to_summary(last) if last is not None else None,
        next_run_at=job_scheduler.next_run_at,
        scheduler_active=job_scheduler.is_active,
        metadata={
            "stub": settings.job_scraper_stub,
            "headless": settings.job_scraper_headless,
            "module_path": settings.job_scraper_module_path,
            "data_file": settings.job_scraper_data_file,
            "enable_scheduler": settings.enable_scheduler,
            "linkedin_scraper_enabled_env": settings.linkedin_scraper_enabled,
            "linkedin_jobs_per_hour_env": settings.linkedin_jobs_per_hour,
        },
    )


@router.get(
    "/history",
    response_model=list[JobImportRunSummary],
    summary="Recent import runs (most recent first).",
)
def get_history(
    limit: int = 25,
    db: Session = Depends(get_db),
) -> list[JobImportRunSummary]:
    runs = repo.list_import_runs(db, limit=max(1, min(limit, 200)))
    return [_to_summary(r) for r in runs]
