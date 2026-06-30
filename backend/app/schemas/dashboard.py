"""PATHS Backend — Dashboard schemas."""

from pydantic import BaseModel


class DashboardStats(BaseModel):
    active_jobs: int = 0
    total_candidates: int = 0
    pending_approvals: int = 0
    applications_this_week: int = 0
    shortlisted_today: int = 0
    interviews_scheduled: int = 0
    hired_this_month: int = 0
    avg_time_to_hire_days: float = 0.0


class AgentStatusOut(BaseModel):
    id: str
    name: str
    status: str        # running | idle | completed | failed
    progress: int = 0  # 0-100
    current_task: str | None = None
    jobs_processed: int = 0
    last_run: str | None = None
