"""
PATHS Backend — Dashboard endpoints.

GET /dashboard/stats   — aggregated KPIs for the current org
GET /dashboard/agents  — live agent status feed
GET /dashboard/funnel  — pipeline stage counts
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import OrgContext, get_current_hiring_org_context
from app.db.models.application import Application, OrganizationMember
from app.db.models.hitl import HITLApproval
from app.db.models.job import Job
from app.db.models.job_scraper import JobImportRun
from app.db.models.scoring import ScoringRun
from app.schemas.dashboard import AgentStatusOut, DashboardStats

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
):
    org_id = ctx.organization_id
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_ago = now - timedelta(days=30)

    # Active jobs: only internal org-owned jobs (exclude external scraped)
    active_jobs = db.execute(
        select(func.count())
        .select_from(Job)
        .where(
            Job.organization_id == org_id,
            Job.application_mode == "internal_apply",
            Job.is_active == True,  # noqa: E712
        )
    ).scalar_one()

    # Total candidates with applications to org's jobs
    total_candidates = db.execute(
        select(func.count(Application.candidate_id.distinct()))
        .join(Job, Application.job_id == Job.id)
        .where(Job.organization_id == org_id)
    ).scalar_one()

    # Pending HITL approvals
    pending_approvals = db.execute(
        select(func.count()).select_from(HITLApproval)
        .where(HITLApproval.organization_id == org_id, HITLApproval.status == "pending")
    ).scalar_one()

    # Applications this week
    apps_this_week = db.execute(
        select(func.count()).select_from(Application)
        .join(Job, Application.job_id == Job.id)
        .where(Job.organization_id == org_id, Application.created_at >= week_ago)
    ).scalar_one()

    # Shortlisted today (stage = screening or higher, created today)
    shortlisted_today = db.execute(
        select(func.count()).select_from(Application)
        .join(Job, Application.job_id == Job.id)
        .where(
            Job.organization_id == org_id,
            Application.current_stage_code.in_(
                ["screening", "assessment", "hr_interview", "tech_interview", "decision"]
            ),
            Application.updated_at >= today_start,
        )
    ).scalar_one()

    # Interviews scheduled (stage = hr_interview or tech_interview)
    interviews = db.execute(
        select(func.count()).select_from(Application)
        .join(Job, Application.job_id == Job.id)
        .where(
            Job.organization_id == org_id,
            Application.current_stage_code.in_(["hr_interview", "tech_interview"]),
        )
    ).scalar_one()

    # Hired this month
    hired = db.execute(
        select(func.count()).select_from(Application)
        .join(Job, Application.job_id == Job.id)
        .where(
            Job.organization_id == org_id,
            Application.current_stage_code == "hired",
            Application.updated_at >= month_ago,
        )
    ).scalar_one()

    # Average time-to-hire — created_at → updated_at for hired applications.
    # updated_at is the best available hire-date proxy (no dedicated column).
    avg_hire_seconds = db.execute(
        select(
            func.avg(
                func.extract("epoch", Application.updated_at - Application.created_at)
            )
        )
        .select_from(Application)
        .join(Job, Application.job_id == Job.id)
        .where(
            Job.organization_id == org_id,
            Application.current_stage_code == "hired",
        )
    ).scalar()
    avg_time_to_hire_days = (
        round(avg_hire_seconds / 86400, 1) if avg_hire_seconds else 0.0
    )

    return DashboardStats(
        active_jobs=active_jobs,
        total_candidates=total_candidates,
        pending_approvals=pending_approvals,
        applications_this_week=apps_this_week,
        shortlisted_today=shortlisted_today,
        interviews_scheduled=interviews,
        hired_this_month=hired,
        avg_time_to_hire_days=avg_time_to_hire_days,
    )


_SHORTLISTED_STAGES = (
    "screening", "assessment", "hr_interview", "tech_interview", "decision", "hired",
)


@router.get("/funnel", response_model=list[dict])
def get_funnel(
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
):
    """Return a true cumulative pipeline funnel for the org.

    Each stage's count is "reached this stage or beyond" using the
    application's current stage as the best-available furthest-reached proxy.
    This makes the funnel monotonically decreasing (Applied ≥ Screening ≥ …
    ≥ Hired) and the per-stage conversion meaningful — instead of a raw
    current-stage snapshot where bars could jump around.
    """
    org_id = ctx.organization_id
    # Positive progression ladder. "sourced" is a pre-application pool and is
    # intentionally excluded; rejected/withdrawn count only toward "Applied".
    ladder = [
        "applied", "screening", "assessment",
        "hr_interview", "tech_interview", "decision", "hired",
    ]

    # Snapshot: how many applications are currently in each ladder stage.
    snapshot: dict[str, int] = {}
    for stage in ladder:
        snapshot[stage] = db.execute(
            select(func.count()).select_from(Application)
            .join(Job, Application.job_id == Job.id)
            .where(
                Job.organization_id == org_id,
                Application.current_stage_code == stage,
            )
        ).scalar_one()

    # Everyone with an application "reached" Applied (incl. rejected/withdrawn).
    total_apps = db.execute(
        select(func.count()).select_from(Application)
        .join(Job, Application.job_id == Job.id)
        .where(Job.organization_id == org_id)
    ).scalar_one()

    result = []
    prev_count = None
    for i, stage in enumerate(ladder):
        if i == 0:
            reached = total_apps
        else:
            reached = sum(snapshot[s] for s in ladder[i:])
        conversion = round(reached / prev_count * 100, 1) if prev_count else 100.0
        result.append({"stage": stage, "count": reached, "conversionRate": conversion})
        prev_count = reached
    return result


@router.get("/weekly", response_model=list[dict])
def get_weekly_applications(
    weeks: int = 8,
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
):
    """Applications received per week + how many of them were shortlisted.

    Real data: buckets the org's applications by the week they were created
    (last ``weeks`` weeks, gaps included as 0). "shortlisted" = applications
    created in that week whose current stage is screening or beyond.
    """
    org_id = ctx.organization_id
    weeks = max(1, min(weeks, 26))
    now = datetime.now(timezone.utc)
    # Anchor to the start of the current day, then walk back in 7-day buckets.
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    out: list[dict] = []
    for i in range(weeks - 1, -1, -1):
        start = today_start - timedelta(days=7 * (i + 1) - 1)
        end = today_start - timedelta(days=7 * i) + timedelta(days=1)
        apps = db.execute(
            select(func.count()).select_from(Application)
            .join(Job, Application.job_id == Job.id)
            .where(
                Job.organization_id == org_id,
                Application.created_at >= start,
                Application.created_at < end,
            )
        ).scalar_one()
        shortlisted = db.execute(
            select(func.count()).select_from(Application)
            .join(Job, Application.job_id == Job.id)
            .where(
                Job.organization_id == org_id,
                Application.created_at >= start,
                Application.created_at < end,
                Application.current_stage_code.in_(_SHORTLISTED_STAGES),
            )
        ).scalar_one()
        label = (end - timedelta(days=1)).strftime("%b %d")
        out.append({"week": label, "applications": apps, "shortlisted": shortlisted})
    return out


@router.get("/agents", response_model=list[AgentStatusOut])
def get_agent_status(
    ctx: OrgContext = Depends(get_current_hiring_org_context),
    db: Session = Depends(get_db),
):
    """Return live agent status derived from recent scoring + ingestion runs."""
    recent_import = db.execute(
        select(JobImportRun).order_by(JobImportRun.started_at.desc()).limit(1)
    ).scalar_one_or_none()

    # Check for recent scoring runs to determine scoring agent state
    recent_scoring = db.execute(
        select(ScoringRun).order_by(ScoringRun.started_at.desc()).limit(1)
    ).scalar_one_or_none()

    scoring_status = "idle"
    scoring_progress = 0
    if recent_scoring:
        if recent_scoring.status == "running":
            total = max(recent_scoring.total_relevant_jobs, 1)
            done = recent_scoring.scored_jobs + recent_scoring.failed_jobs
            scoring_progress = min(int(done / total * 100), 99)
            scoring_status = "running"
        elif recent_scoring.status == "completed":
            scoring_status = "completed"
            scoring_progress = 100
        else:
            scoring_status = "failed"

    sourcing_status = "idle"
    sourcing_progress = 0
    sourcing_task: str | None = None
    sourcing_jobs = 0
    sourcing_last: str | None = None
    if recent_import:
        sourcing_last = recent_import.started_at.isoformat()
        sourcing_jobs = recent_import.inserted_count or 0
        if recent_import.status == "running":
            sourcing_status = "running"
            cap = max(recent_import.requested_limit, 1)
            done = min(
                (recent_import.inserted_count or 0)
                + (recent_import.updated_count or 0)
                + (recent_import.skipped_count or 0)
                + (recent_import.failed_count or 0),
                cap,
            )
            sourcing_progress = min(int(done / cap * 100), 99)
            sourcing_task = (
                f"Importing {recent_import.source_platform} jobs "
                f"({recent_import.scraped_count or 0} scraped)"
            )
        elif recent_import.status in {"success", "partial"}:
            sourcing_status = "completed"
            sourcing_progress = 100
            sourcing_task = (
                f"Last run: +{recent_import.inserted_count or 0} inserted, "
                f"{recent_import.skipped_count or 0} skipped"
            )
        elif recent_import.status == "failed":
            sourcing_status = "failed"
            sourcing_task = (recent_import.error_message or "")[:120] or None

    agents = [
        AgentStatusOut(
            id="agent_screening",
            name="Screening Agent",
            status=scoring_status,
            progress=scoring_progress,
            current_task="Scoring candidates against open jobs" if scoring_status == "running" else None,
            jobs_processed=recent_scoring.scored_jobs if recent_scoring else 0,
            last_run=recent_scoring.started_at.isoformat() if recent_scoring else None,
        ),
        AgentStatusOut(
            id="agent_sourcing",
            name="Sourcing Agent",
            status=sourcing_status,
            progress=sourcing_progress,
            current_task=sourcing_task,
            jobs_processed=sourcing_jobs,
            last_run=sourcing_last,
        ),
        AgentStatusOut(
            id="agent_assessment",
            name="Assessment Agent",
            status="idle",
            progress=0,
            current_task=None,
            jobs_processed=0,
        ),
        AgentStatusOut(
            id="agent_compliance",
            name="Compliance Agent",
            status="idle",
            progress=0,
            current_task=None,
            jobs_processed=0,
        ),
    ]
    return agents
