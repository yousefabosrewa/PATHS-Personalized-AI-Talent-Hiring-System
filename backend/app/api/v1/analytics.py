"""
PATHS Backend -- Analytics API endpoints (Phase 2.5).

Routes:
  GET /analytics/summary       -- general hiring funnel + event counts
  GET /analytics/bias-summary  -- disparate-impact metrics across jobs
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import OrgContext, get_current_hiring_org_context
from app.db.models.analytics_events import AnalyticsEvent
from app.db.models.application import Application
from app.db.models.bias_reports import BiasReport
from app.db.models.job import Job
from app.db.models.screening import ScreeningResult, ScreeningRun

router = APIRouter(prefix="/analytics", tags=["Analytics"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class EventCountItem(BaseModel):
    event_type: str
    count: int


class StageFunnelItem(BaseModel):
    stage: str
    count: int


class AnalyticsSummary(BaseModel):
    org_id: str
    period_days: int
    total_active_jobs: int
    total_applications: int
    total_screening_runs: int
    total_candidates_screened: int
    total_shortlisted: int
    event_counts: list[EventCountItem] = Field(default_factory=list)
    pipeline_funnel: list[StageFunnelItem] = Field(default_factory=list)
    generated_at: datetime


class BiasAttributeSummary(BaseModel):
    attribute_name: str
    total_groups_checked: int
    groups_flagged: int
    min_disparate_impact_ratio: float | None = None
    avg_disparate_impact_ratio: float | None = None


class BiasSummary(BaseModel):
    org_id: str
    period_days: int
    total_runs_checked: int
    runs_with_flags: int
    total_flags: int
    attributes: list[BiasAttributeSummary] = Field(default_factory=list)
    generated_at: datetime


# ---------------------------------------------------------------------------
# GET /analytics/summary
# ---------------------------------------------------------------------------

@router.get(
    "/summary",
    response_model=AnalyticsSummary,
    summary="General hiring analytics summary for the current organization.",
)
def get_analytics_summary(
    days: int = Query(default=30, ge=1, le=365, description="Look-back window in days"),
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
) -> AnalyticsSummary:
    org_id = ctx.organization_id
    since = datetime.now(timezone.utc) - timedelta(days=days)

    # -- Active jobs ----------------------------------------------------------
    active_jobs: int = db.execute(
        select(func.count())
        .select_from(Job)
        .where(
            Job.organization_id == org_id,
            Job.is_active == True,  # noqa: E712
        )
    ).scalar_one()

    # -- Applications (total, within period) ----------------------------------
    total_apps: int = db.execute(
        select(func.count())
        .select_from(Application)
        .join(Job, Application.job_id == Job.id)
        .where(
            Job.organization_id == org_id,
            Application.created_at >= since,
        )
    ).scalar_one()

    # -- Screening runs --------------------------------------------------------
    total_runs: int = db.execute(
        select(func.count())
        .select_from(ScreeningRun)
        .where(
            ScreeningRun.organization_id == org_id,
            ScreeningRun.created_at >= since,
            ScreeningRun.status == "completed",
        )
    ).scalar_one()

    total_screened: int = db.execute(
        select(func.coalesce(func.sum(ScreeningRun.candidates_scored), 0))
        .where(
            ScreeningRun.organization_id == org_id,
            ScreeningRun.created_at >= since,
        )
    ).scalar_one()

    total_shortlisted: int = db.execute(
        select(func.count())
        .select_from(ScreeningResult)
        .join(ScreeningRun, ScreeningResult.screening_run_id == ScreeningRun.id)
        .where(
            ScreeningRun.organization_id == org_id,
            ScreeningRun.created_at >= since,
            ScreeningResult.status == "shortlisted",
        )
    ).scalar_one()

    # -- Analytics event counts -----------------------------------------------
    event_rows = db.execute(
        select(AnalyticsEvent.event_type, func.count().label("cnt"))
        .where(
            AnalyticsEvent.org_id == org_id,
            AnalyticsEvent.created_at >= since,
        )
        .group_by(AnalyticsEvent.event_type)
        .order_by(func.count().desc())
    ).all()

    event_counts = [EventCountItem(event_type=r[0], count=r[1]) for r in event_rows]

    # -- Pipeline funnel (application stage breakdown) -------------------------
    funnel_rows = db.execute(
        select(Application.pipeline_stage, func.count().label("cnt"))
        .join(Job, Application.job_id == Job.id)
        .where(
            Job.organization_id == org_id,
            Application.created_at >= since,
            Application.pipeline_stage.isnot(None),
        )
        .group_by(Application.pipeline_stage)
        .order_by(func.count().desc())
    ).all()

    pipeline_funnel = [StageFunnelItem(stage=r[0], count=r[1]) for r in funnel_rows]

    return AnalyticsSummary(
        org_id=str(org_id),
        period_days=days,
        total_active_jobs=active_jobs,
        total_applications=total_apps,
        total_screening_runs=total_runs,
        total_candidates_screened=total_screened,
        total_shortlisted=total_shortlisted,
        event_counts=event_counts,
        pipeline_funnel=pipeline_funnel,
        generated_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# GET /analytics/bias-summary
# ---------------------------------------------------------------------------

@router.get(
    "/bias-summary",
    response_model=BiasSummary,
    summary="Disparate-impact bias metrics for the current organization.",
)
def get_bias_summary(
    days: int = Query(default=30, ge=1, le=365, description="Look-back window in days"),
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
) -> BiasSummary:
    org_id = ctx.organization_id
    since = datetime.now(timezone.utc) - timedelta(days=days)

    # -- Runs that have bias reports -------------------------------------------
    total_runs_checked: int = db.execute(
        select(func.count(BiasReport.screening_run_id.distinct()))
        .where(
            BiasReport.organization_id == org_id,
            BiasReport.created_at >= since,
        )
    ).scalar_one()

    runs_with_flags: int = db.execute(
        select(func.count(BiasReport.screening_run_id.distinct()))
        .where(
            BiasReport.organization_id == org_id,
            BiasReport.created_at >= since,
            BiasReport.passed == False,  # noqa: E712
        )
    ).scalar_one()

    total_flags: int = db.execute(
        select(func.count())
        .select_from(BiasReport)
        .where(
            BiasReport.organization_id == org_id,
            BiasReport.created_at >= since,
            BiasReport.passed == False,  # noqa: E712
        )
    ).scalar_one()

    # -- Per-attribute breakdown ----------------------------------------------
    # Fetch distinct attribute names first, then compute metrics per attribute.
    attr_name_rows = db.execute(
        select(BiasReport.attribute_name.distinct())
        .where(
            BiasReport.organization_id == org_id,
            BiasReport.created_at >= since,
            BiasReport.group_label != "__no_data__",
        )
        .order_by(BiasReport.attribute_name)
    ).scalars().all()

    attributes: list[BiasAttributeSummary] = []
    for attr_name in attr_name_rows:
        base_filter = [
            BiasReport.organization_id == org_id,
            BiasReport.created_at >= since,
            BiasReport.attribute_name == attr_name,
            BiasReport.group_label != "__no_data__",
        ]
        total_count: int = db.execute(
            select(func.count()).select_from(BiasReport).where(*base_filter)
        ).scalar_one()
        flagged_count: int = db.execute(
            select(func.count()).select_from(BiasReport)
            .where(*base_filter, BiasReport.passed == False)  # noqa: E712
        ).scalar_one()
        dir_stats = db.execute(
            select(
                func.min(BiasReport.disparate_impact_ratio),
                func.avg(BiasReport.disparate_impact_ratio),
            ).where(*base_filter, BiasReport.disparate_impact_ratio.isnot(None))
        ).one()

        attributes.append(BiasAttributeSummary(
            attribute_name=attr_name,
            total_groups_checked=total_count,
            groups_flagged=flagged_count,
            min_disparate_impact_ratio=float(dir_stats[0]) if dir_stats[0] is not None else None,
            avg_disparate_impact_ratio=float(dir_stats[1]) if dir_stats[1] is not None else None,
        ))

    return BiasSummary(
        org_id=str(org_id),
        period_days=days,
        total_runs_checked=total_runs_checked,
        runs_with_flags=runs_with_flags,
        total_flags=total_flags,
        attributes=attributes,
        generated_at=datetime.now(timezone.utc),
    )
