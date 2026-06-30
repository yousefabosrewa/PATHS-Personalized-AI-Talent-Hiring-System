"""
PATHS Backend — Screening Agent API endpoints.

Routes under ``/api/v1/screening``:

  POST /screening/jobs/{job_id}/screen         — screen DB candidates
  POST /screening/jobs/{job_id}/screen-csv     — screen from uploaded CSV
  GET  /screening/runs/{run_id}                — run status + summary
  GET  /screening/runs/{run_id}/results        — ranked candidate list
  GET  /screening/runs/{run_id}/results/{id}   — detail for one candidate
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile, status

from app.core.dependencies import (
    OrgContext,
    get_current_hiring_org_context,
    require_active_org_status,
)
from app.core.database import SessionLocal
from app.db.models.bias_reports import BiasReport
from app.db.models.screening import ScreeningRun
from app.schemas.screening import (
    BiasReportEntry,
    BiasReportResponse,
    ScreeningResultDetail,
    ScreeningResultItem,
    ScreeningResultsListResponse,
    ScreeningRunResponse,
    ScreeningRunWithResults,
    ScreenJobRequest,
)
from app.services.screening.screening_service import ScreeningService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/screening", tags=["Screening Agent"])


def _parse_uuid(value: str, field: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field} UUID",
        ) from exc


# ── Screen from database ────────────────────────────────────────────────


@router.post(
    "/jobs/{job_id}/screen",
    response_model=ScreeningRunWithResults,
    summary="Screen all database candidates for a job — score and rank them.",
)
async def screen_job_from_database(
    job_id: str,
    body: ScreenJobRequest = Body(...),
    ctx: OrgContext = Depends(require_active_org_status),
):
    """
    Discover all relevant candidates in the database for the given job,
    score each one using the LLM + vector scoring pipeline, and produce
    a ranked shortlist.

    Tenant scope is the caller's JWT organization_id — not the request body.
    Any organization_id in the body is ignored.
    """
    jid = _parse_uuid(job_id, "job_id")
    org_id = ctx.organization_id

    service = ScreeningService()
    try:
        result = await service.screen_from_database(
            organization_id=org_id,
            job_id=jid,
            top_k=body.top_k,
            force_rescore=body.force_rescore,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Screening run crashed for job %s", jid)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"screening_failed: {exc}",
        ) from exc

    if not result.get("ok"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "screening_failed"),
        )

    return ScreeningRunWithResults(
        screening_run_id=result["screening_run_id"],
        organization_id=str(org_id),
        job_id=str(jid),
        source="database",
        top_k=body.top_k,
        status=result.get("status", "completed"),
        total_candidates_scanned=result.get("total_candidates_scanned", 0),
        candidates_passed_filter=result.get("candidates_passed_filter", 0),
        candidates_scored=result.get("candidates_scored", 0),
        candidates_failed=result.get("candidates_failed", 0),
        error_message=result.get("error"),
        results=[
            ScreeningResultItem(**r) for r in (result.get("results") or [])
        ],
    )


# ── Screen from CSV upload ──────────────────────────────────────────────


@router.post(
    "/jobs/{job_id}/screen-csv",
    response_model=ScreeningRunWithResults,
    summary="Screen candidates from an uploaded CSV file for a job.",
)
async def screen_job_from_csv(
    job_id: str,
    top_k: int = Form(10),
    csv_file: UploadFile = File(...),
    ctx: OrgContext = Depends(require_active_org_status),
):
    """
    Import candidates from the uploaded CSV file, then score and rank
    each one against the specified job.

    Tenant scope is the caller's JWT organization_id — not a form field.
    Any organization_id in the form is ignored.
    """
    jid = _parse_uuid(job_id, "job_id")
    org_id = ctx.organization_id

    raw = await csv_file.read()
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="empty_csv_file",
        )

    service = ScreeningService()
    try:
        result = await service.screen_from_csv(
            organization_id=org_id,
            job_id=jid,
            csv_file_bytes=raw,
            file_name=csv_file.filename or "candidates.csv",
            top_k=top_k,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("CSV screening crashed for job %s", jid)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"screening_failed: {exc}",
        ) from exc

    if not result.get("ok"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "screening_failed"),
        )

    return ScreeningRunWithResults(
        screening_run_id=result["screening_run_id"],
        organization_id=str(org_id),
        job_id=str(jid),
        source="csv_upload",
        top_k=top_k,
        status=result.get("status", "completed"),
        total_candidates_scanned=result.get("total_candidates_scanned", 0),
        candidates_passed_filter=result.get("candidates_passed_filter", 0),
        candidates_scored=result.get("candidates_scored", 0),
        candidates_failed=result.get("candidates_failed", 0),
        error_message=result.get("error"),
        results=[
            ScreeningResultItem(**r) for r in (result.get("results") or [])
        ],
    )


# ── Get screening run ──────────────────────────────────────────────────


@router.get(
    "/runs/{run_id}",
    response_model=ScreeningRunResponse,
    summary="Get the status and summary of a screening run.",
)
def get_screening_run(
    run_id: str,
    ctx: OrgContext = Depends(require_active_org_status),
):
    rid = _parse_uuid(run_id, "run_id")
    data = ScreeningService.get_run(rid)
    if data is None:
        raise HTTPException(status_code=404, detail="screening_run_not_found")
    if str(ctx.organization_id) != data.get("organization_id"):
        raise HTTPException(status_code=404, detail="screening_run_not_found")
    return ScreeningRunResponse(**data)


# ── Get results list ────────────────────────────────────────────────────


@router.get(
    "/runs/{run_id}/results",
    response_model=ScreeningResultsListResponse,
    summary="Get the ranked list of candidates for a screening run.",
)
def get_screening_results(
    run_id: str,
    ctx: OrgContext = Depends(require_active_org_status),
):
    rid = _parse_uuid(run_id, "run_id")
    run_data = ScreeningService.get_run(rid)
    if run_data is None:
        raise HTTPException(status_code=404, detail="screening_run_not_found")
    if str(ctx.organization_id) != run_data.get("organization_id"):
        raise HTTPException(status_code=404, detail="screening_run_not_found")

    results = ScreeningService.get_results(rid)
    return ScreeningResultsListResponse(
        screening_run_id=str(rid),
        job_id=run_data["job_id"],
        results=[ScreeningResultItem(**r) for r in results],
    )


# ── Get single result detail ───────────────────────────────────────────


@router.get(
    "/runs/{run_id}/results/{result_id}",
    response_model=ScreeningResultDetail,
    summary="Get the full detail for one candidate in a screening run.",
)
def get_screening_result_detail(
    run_id: str,
    result_id: str,
    ctx: OrgContext = Depends(require_active_org_status),
):
    rid = _parse_uuid(run_id, "run_id")
    res_id = _parse_uuid(result_id, "result_id")
    run_data = ScreeningService.get_run(rid)
    if run_data is None or str(ctx.organization_id) != run_data.get("organization_id"):
        raise HTTPException(status_code=404, detail="screening_run_not_found")
    detail = ScreeningService.get_result_detail(res_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="screening_result_not_found")
    return ScreeningResultDetail(**detail)


# -- Bias report ---------------------------------------------------------------


@router.get(
    "/runs/{run_id}/bias-report",
    response_model=BiasReportResponse,
    summary="Get the bias guardrail report for a screening run.",
)
def get_bias_report(
    run_id: str,
    ctx: OrgContext = Depends(require_active_org_status),
):
    """
    Returns per-attribute, per-group disparate-impact metrics for the
    screening run produced by the bias_guardrail_node (Phase 2.1).

    ``has_flags=True`` means at least one group's selection rate fell
    below the job's disparate-impact threshold.
    """
    rid = _parse_uuid(run_id, "run_id")

    db = SessionLocal()
    try:
        run: ScreeningRun | None = db.get(ScreeningRun, rid)
        if run is None:
            raise HTTPException(status_code=404, detail="screening_run_not_found")
        if str(run.organization_id) != str(ctx.organization_id):
            raise HTTPException(status_code=404, detail="screening_run_not_found")

        rows: list[BiasReport] = (
            db.query(BiasReport)
            .filter(BiasReport.screening_run_id == rid)
            .order_by(BiasReport.attribute_name, BiasReport.group_label)
            .all()
        )

        entries = [
            BiasReportEntry(
                attribute_name=r.attribute_name,
                group_label=r.group_label,
                selection_count=r.selection_count,
                total_count=r.total_count,
                selection_rate=r.selection_rate,
                disparate_impact_ratio=r.disparate_impact_ratio,
                threshold=r.threshold,
                passed=r.passed,
            )
            for r in rows
        ]

        flagged = list({e.attribute_name for e in entries if not e.passed})

        return BiasReportResponse(
            screening_run_id=str(rid),
            job_id=str(run.job_id),
            organization_id=str(run.organization_id),
            has_flags=bool(flagged),
            flagged_attributes=flagged,
            entries=entries,
        )
    finally:
        db.close()
