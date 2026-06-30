"""
PATHS Backend — FastAPI application entry point.
"""
# reload-trigger: 2026-04-27

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from urllib.parse import urlparse

from app.core.config import get_settings
from app.core.logging import setup_logging, set_correlation_id

settings = get_settings()

# Configure logging at import time. The observability bootstrap below runs
# at module-construction time (not inside the lifespan), so logging must be
# ready before it emits any records.
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    from app.core.logging import get_logger
    logger = get_logger(__name__)
    logger.info("Starting %s (%s)", settings.app_name, settings.app_env)

    # ── Sentry (PATHS-178) — init early so startup errors are captured ──
    if settings.sentry_dsn:
        try:
            import sentry_sdk
            sentry_sdk.init(
                dsn=settings.sentry_dsn,
                traces_sample_rate=settings.sentry_traces_sample_rate,
                release=settings.sentry_release or None,
                environment=settings.app_env,
                send_default_pii=False,
            )
            logger.info("Sentry initialised (env=%s)", settings.app_env)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to initialise Sentry")
    else:
        logger.debug("Sentry DSN not configured — error monitoring disabled")

    # Log startup warnings for non-production-safe config
    if settings.debug:
        logger.warning("DEBUG mode is enabled — disable in production with debug=False")
    if settings.secret_key == "CHANGE-ME-TO-A-RANDOM-SECRET":
        logger.warning("SECRET_KEY is still the default — set a strong random secret in production")
    if settings.candidate_sourcing_provider == "mock" and settings.app_env == "development":
        logger.info("Candidate sourcing provider is 'mock' — only suitable for local development")
    elif settings.candidate_sourcing_provider == "mock" and settings.app_env != "development":
        logger.warning(
            "Candidate sourcing provider is 'mock' in a non-development environment. "
            "Configure a real provider or disable candidate sourcing."
        )

    # Hourly job-scraper scheduler — opt-in via ENABLE_SCHEDULER=true and
    # JOB_SCRAPER_ENABLED / LINKEDIN_SCRAPER_ENABLED.
    # Importing inside the lifespan keeps APScheduler optional.
    from app.services.job_scraper.scheduler import scheduler as job_scheduler
    try:
        if settings.enable_scheduler:
            await job_scheduler.start()
        else:
            logger.info("Background scheduler disabled (ENABLE_SCHEDULER=false)")
    except Exception:  # noqa: BLE001
        logger.exception("Failed to start hourly job-scraper scheduler")

    # One-shot sweep: expire member invites that went stale while the server
    # was down. The Members tab also sweeps lazily on every read.
    try:
        from app.core.database import SessionLocal
        from app.services.organization_service import expire_stale_pending_invites

        with SessionLocal() as _db:
            n = expire_stale_pending_invites(_db)
            if n:
                logger.info("Expired %d stale member invite(s) on startup", n)
    except Exception:  # noqa: BLE001
        logger.exception("Startup member-invite expiry sweep failed")

    try:
        yield
    finally:
        try:
            await job_scheduler.shutdown()
        except Exception:  # noqa: BLE001
            logger.exception("Error while shutting down job-scraper scheduler")
        logger.info("Shutting down %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="PATHS — Hiring workflow backend with PostgreSQL, Apache AGE, and Qdrant",
    lifespan=lifespan,
)

# ── Trusted Host middleware ──────────────────────────────────────────────
trusted_hosts = set()
for origin in settings.cors_origin_list:
    parsed = urlparse(origin)
    if parsed.hostname:
        host = parsed.hostname
        trusted_hosts.add(host)
        if parsed.port:
            trusted_hosts.add(f"{host}:{parsed.port}")
trusted_hosts.update(["localhost", "127.0.0.1", settings.app_host])

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=list(trusted_hosts),
)

# ── CORS ─────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Security headers (PATHS-173) ─────────────────────────────────────────
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

    # CSP — strict in production; relaxed in dev for hot-reload
    if settings.app_env == "development":
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-eval' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            "connect-src 'self' ws: wss: http://localhost:*; "
            "font-src 'self' data:;"
        )
    else:
        # Production strict CSP — no inline scripts; nonce-based would be ideal
        # but this baseline blocks the most common XSS vectors.
        frontend_origin = settings.app_frontend_url if hasattr(settings, "app_frontend_url") else ""
        csp = (
            "default-src 'self'; "
            f"script-src 'self' {frontend_origin}; "
            f"style-src 'self' {frontend_origin} 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            f"connect-src 'self' {frontend_origin}; "
            "font-src 'self' data:; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )
        response.headers["Strict-Transport-Security"] = \
            "max-age=15552000; includeSubDomains"  # 6 months

    response.headers["Content-Security-Policy"] = csp
    return response


# ── Correlation-ID middleware (PATHS-177) ────────────────────────────────
# Reads the X-Correlation-ID request header (set by a gateway / client) or
# generates a fresh UUID.  The ID is stored in a ContextVar so every log
# record emitted during the request automatically carries it.
@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    cid = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    set_correlation_id(cid)
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = cid
    return response


# ── Observability: Prometheus /metrics + optional OpenTelemetry (PATHS-177) ──
# Registered here, at module-construction time — NOT inside the lifespan.
# Instrumentator.instrument() adds an ASGI middleware, and Starlette forbids
# adding middleware once the application lifespan has started.
from app.core.telemetry import configure_telemetry  # noqa: E402

configure_telemetry(app, settings)


# ── Import routers ─────────────────────────────────────────────────────
from app.api.v1.health import router as health_router  # noqa: E402
from app.api.v1.system import router as system_router  # noqa: E402
from app.api.v1.cv_ingestion import router as cv_ingestion_router  # noqa: E402
from app.api.v1.candidates import router as candidates_router  # noqa: E402
from app.api.v1.candidate_duplicates import router as candidate_duplicates_router  # noqa: E402
from app.api.v1.auth import router as auth_router  # noqa: E402
from app.api.v1.organizations import router as organizations_router  # noqa: E402
from app.api.v1.job_ingestion import router as job_ingestion_router  # noqa: E402
from app.api.v1.admin import router as admin_router  # noqa: E402
from app.api.v1.platform_admin import router as platform_admin_router  # noqa: E402
from app.api.v1.candidate_sourcing import router as candidate_sourcing_router  # noqa: E402
from app.api.v1.job_import import router as job_import_router  # noqa: E402
from app.api.v1.scoring import router as scoring_router  # noqa: E402
from app.api.v1.organization_matching import (  # noqa: E402
    router as organization_matching_router,
)
from app.api.v1.interviews import router as interviews_router  # noqa: E402
from app.api.v1.decision_support import router as decision_support_router  # noqa: E402
from app.api.v1.jobs import router as jobs_router  # noqa: E402
from app.api.v1.applications import router as applications_router  # noqa: E402
from app.api.v1.approvals import router as approvals_router  # noqa: E402
from app.api.v1.dashboard import router as dashboard_router  # noqa: E402
from app.api.v1.audit import router as audit_router  # noqa: E402
from app.api.v1.bias_fairness import router as bias_fairness_router  # noqa: E402
from app.api.v1.evidence import router as evidence_router  # noqa: E402
from app.api.v1.organization_candidate_sourcing import (  # noqa: E402
    router as organization_candidate_sourcing_router,
    admin_router as candidate_sourcing_admin_router,
)
from app.api.v1.google_integration import router as google_integration_router  # noqa: E402
from app.api.v1.outreach_agent import router as outreach_agent_router  # noqa: E402
from app.api.v1.scheduling import router as scheduling_router  # noqa: E402
from app.api.v1.interview_runtime import router as interview_runtime_router  # noqa: E402
from app.api.v1.interview_recall import (  # noqa: E402
    router as interview_recall_router,
    webhook_router as recall_webhook_router,
)
from app.api.v1.skill_evidence import router as skill_evidence_router  # noqa: E402
from app.api.v1.assessment import (  # noqa: E402
    router as assessment_router,
    job_router as assessment_job_router,
)
from app.api.v1.screening import router as screening_router  # noqa: E402
from app.api.v1.contact_enrichment import router as contact_enrichment_router  # noqa: E402
from app.api.v1.identity_resolution import router as identity_resolution_router  # noqa: E402
from app.api.v1.idss import (  # noqa: E402
    candidate_plans_router,
    decision_extra_router,
    plans_router,
)
from app.api.v1.job_detail import router as job_detail_router  # noqa: E402
from app.api.v1.candidate_applications import router as candidate_applications_router  # noqa: E402
from app.api.v1.analytics import router as analytics_router  # noqa: E402
from app.api.v1.agent_runs import router as agent_runs_router  # noqa: E402
from app.api.v1.sourcing_agent import router as sourcing_agent_router  # noqa: E402
from app.api.v1.sourcing import router as sourcing_router  # noqa: E402
from app.api.v1.source_candidate import router as source_candidate_router  # noqa: E402
from app.api.v1.organization_linkedin import router as organization_linkedin_router  # noqa: E402
from app.api.v1.company_knowledge import router as company_knowledge_router  # noqa: E402
from app.api.v1.outreach_search import router as outreach_search_router  # noqa: E402
from app.api.v1.matching_workspace import router as matching_workspace_router  # noqa: E402
from app.api.v1.jd_analysis import router as jd_analysis_router  # noqa: E402
from app.api.v1.assistant import router as assistant_router  # noqa: E402
from app.api.v1.candidate_jobs import router as candidate_jobs_router  # noqa: E402
from app.api.v1.billing import router as billing_router  # noqa: E402
from app.api.v1.public import router as public_router  # noqa: E402
from app.api.v1.owner import router as owner_router  # noqa: E402

# ── Register routers ───────────────────────────────────────────────────
app.include_router(auth_router, prefix="/api/v1")
app.include_router(organizations_router, prefix="/api/v1")
app.include_router(cv_ingestion_router, prefix="/api/v1")
# fix2_1.md — candidate duplicate review/merge. Registered BEFORE the
# candidates router so /candidates/duplicates is matched before the
# catch-all /candidates/{candidate_id}.
app.include_router(candidate_duplicates_router, prefix="/api/v1")
app.include_router(candidates_router, prefix="/api/v1")
app.include_router(system_router, prefix="/api/v1")
app.include_router(job_ingestion_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(platform_admin_router, prefix="/api/v1")
app.include_router(candidate_sourcing_router, prefix="/api/v1")
app.include_router(job_import_router, prefix="/api/v1")
app.include_router(scoring_router, prefix="/api/v1")
app.include_router(organization_matching_router, prefix="/api/v1")
app.include_router(interviews_router, prefix="/api/v1")
app.include_router(decision_support_router, prefix="/api/v1")
# ── New recruiter-facing routers ───────────────────────────────────────
app.include_router(jobs_router, prefix="/api/v1")
app.include_router(applications_router, prefix="/api/v1")
app.include_router(approvals_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(audit_router, prefix="/api/v1")
app.include_router(bias_fairness_router, prefix="/api/v1")
app.include_router(evidence_router, prefix="/api/v1")
app.include_router(organization_candidate_sourcing_router, prefix="/api/v1")
app.include_router(candidate_sourcing_admin_router, prefix="/api/v1")
app.include_router(google_integration_router, prefix="/api/v1")
app.include_router(outreach_agent_router, prefix="/api/v1")
app.include_router(scheduling_router, prefix="/api/v1")
app.include_router(interview_runtime_router, prefix="/api/v1")
app.include_router(interview_recall_router, prefix="/api/v1")
app.include_router(recall_webhook_router, prefix="/api/v1")
app.include_router(skill_evidence_router, prefix="/api/v1")
app.include_router(assessment_router, prefix="/api/v1")
# fix5.md — job-scoped assessment listing + candidate-facing published list
app.include_router(assessment_job_router, prefix="/api/v1")
app.include_router(screening_router, prefix="/api/v1")
app.include_router(contact_enrichment_router, prefix="/api/v1")
app.include_router(identity_resolution_router, prefix="/api/v1")
app.include_router(decision_extra_router, prefix="/api/v1")
app.include_router(plans_router, prefix="/api/v1")
app.include_router(candidate_plans_router, prefix="/api/v1")
# Health router exposes /api/v1/health/databases plus the legacy
# per-service paths used by integration tests.
app.include_router(job_detail_router, prefix="/api/v1")
app.include_router(candidate_applications_router, prefix="/api/v1")
app.include_router(analytics_router, prefix="/api/v1")
app.include_router(agent_runs_router, prefix="/api/v1")
app.include_router(sourcing_agent_router, prefix="/api/v1")
app.include_router(sourcing_router, prefix="/api/v1")
# fix6.md — recruiter Source Candidate preview/import workflow
app.include_router(source_candidate_router, prefix="/api/v1")
app.include_router(organization_linkedin_router, prefix="/api/v1")
# fix2_1.md — Company Knowledge file uploads + indexing
app.include_router(company_knowledge_router, prefix="/api/v1")
# fix4.md — unified Outreach search (anonymized shortlist + agent explanations)
app.include_router(outreach_search_router, prefix="/api/v1")
# fix7.md — Semantic Search + RAG Test for the Matching/Outreach workspace
app.include_router(matching_workspace_router, prefix="/api/v1")
# fix8&9 — Candidate-side Job Description Analysis
app.include_router(jd_analysis_router, prefix="/api/v1")
app.include_router(assistant_router, prefix="/api/v1")
# Candidate portal — top matching jobs + per-job AI explanation
app.include_router(candidate_jobs_router, prefix="/api/v1")
# Phase 6 — Billing + Public endpoints
app.include_router(billing_router, prefix="/api/v1")
app.include_router(public_router, prefix="/api/v1")
# Phase 7 — Owner portal
app.include_router(owner_router, prefix="/api/v1")
app.include_router(health_router, prefix="/api/v1")


# ── Root-level health endpoint (legacy - kept for backward compatibility) ──
@app.get("/health", tags=["Health"])
def root_health():
    """Root-level aggregated health check returning per-service connectivity."""
    import os
    import httpx
    from app.services.postgres_service import PostgresService
    from app.services.age_service import AGEService
    from app.services.qdrant_service import QdrantService

    pg = PostgresService.test_connection()
    age = AGEService.test_connection()

    qdrant_svc = QdrantService()
    qd = qdrant_svc.test_connection()

    base_url = settings.ollama_base_url
    try:
        r = httpx.get(f"{base_url}/api/tags", timeout=3.0)
        ol = {"status": "healthy" if r.status_code == 200 else "unhealthy"}
    except Exception:
        ol = {"status": "unreachable"}

    return {
        "postgres": pg,
        "age": age,
        "qdrant": qd,
        "ollama": ol,
    }


# ── Spec-compliant root-level GET /health/databases ────────────────────
# 01_MASTER_DATABASE_INTEGRATION_INSTRUCTIONS.md (Phase 2) requires this
# exact path with the canonical {postgres, apache_age, qdrant} payload.
@app.get("/health/databases", tags=["Health"])
def health_databases_root():
    from app.services.database_health_service import check_all
    return check_all()


@app.get("/", tags=["Root"])
def root():
    """Root endpoint."""
    return {
        "app": settings.app_name,
        "version": "0.1.0",
        "docs": "/docs",
    }
