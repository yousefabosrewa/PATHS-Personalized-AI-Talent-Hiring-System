"""Candidate "Import fresh jobs" service (Open Jobs page).

When a candidate clicks *Import fresh jobs*, we want them to reliably see 5
new, active, publicly-listed jobs. Strategy (chosen: live-scrape + fallback):

  1. Run the real job scraper (RemoteOK RSS by default) for up to N jobs,
     guarded by a timeout so a slow/unreachable feed can't hang the request.
  2. Top up with realistic generated sample jobs to reach N, so the button
     always delivers fresh listings even offline / when the feed had nothing
     new.

Generated jobs are inserted active + public (so they appear in /jobs/public)
and synced to Qdrant/AGE (so they also feed the candidate's Top Matches).
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.job import Job
from app.services.job_scraper.job_import_service import JobImportService
from app.services.job_sync_service import sync_job_full

logger = logging.getLogger(__name__)
settings = get_settings()

_SCRAPE_TIMEOUT_SECONDS = 25

# Realistic, skill-rich templates so generated jobs both read well and match
# candidates by skill/title. Requirements deliberately name concrete skills.
_SAMPLE_JOBS: list[dict[str, Any]] = [
    {
        "title": "Frontend Engineer (React/TypeScript)",
        "company": "Brightwave Labs", "seniority": "mid", "workplace": "remote",
        "location": "Remote", "salary": (90000, 130000),
        "summary": "Build delightful web UIs for a fast-growing SaaS product.",
        "description": "Own the React/TypeScript frontend, ship features end to end, and partner with design on a polished user experience.",
        "requirements": "React, TypeScript, Next.js, Tailwind CSS, REST APIs, Jest, accessibility.",
    },
    {
        "title": "Backend Engineer (Node.js)",
        "company": "Northpeak Systems", "seniority": "senior", "workplace": "hybrid",
        "location": "Berlin, Germany", "salary": (110000, 150000),
        "summary": "Design and scale backend services for millions of users.",
        "description": "Build resilient APIs and event-driven services, own data models, and improve reliability.",
        "requirements": "Node.js, TypeScript, PostgreSQL, Redis, Kafka, Docker, REST, microservices.",
    },
    {
        "title": "Full Stack Engineer (Python/React)",
        "company": "Cobalt & Co", "seniority": "mid", "workplace": "remote",
        "location": "Remote (EU)", "salary": (95000, 135000),
        "summary": "Ship full-stack features across a Python + React codebase.",
        "description": "Work across the stack: FastAPI services and a React frontend, from database to UI.",
        "requirements": "Python, FastAPI, React, TypeScript, PostgreSQL, Docker, REST APIs.",
    },
    {
        "title": "Machine Learning Engineer",
        "company": "Helix AI", "seniority": "senior", "workplace": "remote",
        "location": "Remote", "salary": (130000, 180000),
        "summary": "Take ML models from research to production.",
        "description": "Train, evaluate, and deploy models; build data and inference pipelines for real products.",
        "requirements": "Python, PyTorch, TensorFlow, scikit-learn, NLP, MLOps, Docker, AWS.",
    },
    {
        "title": "Data Engineer (Spark/SQL)",
        "company": "Quanta Metrics", "seniority": "mid", "workplace": "hybrid",
        "location": "London, UK", "salary": (100000, 140000),
        "summary": "Build the data platform powering analytics and ML.",
        "description": "Design pipelines and warehouses, ensure data quality, and enable self-serve analytics.",
        "requirements": "Python, SQL, Apache Spark, Airflow, dbt, Snowflake, AWS, ETL.",
    },
    {
        "title": "DevOps Engineer (Kubernetes/AWS)",
        "company": "Streamline Cloud", "seniority": "senior", "workplace": "remote",
        "location": "Remote", "salary": (120000, 165000),
        "summary": "Own the infrastructure and CI/CD for a cloud-native platform.",
        "description": "Run and scale Kubernetes, automate everything, and champion reliability and observability.",
        "requirements": "Kubernetes, Docker, AWS, Terraform, CI/CD, Prometheus, Linux, Python.",
    },
    {
        "title": "Mobile Engineer (Flutter)",
        "company": "Pocket Studios", "seniority": "mid", "workplace": "remote",
        "location": "Remote", "salary": (85000, 125000),
        "summary": "Craft cross-platform mobile apps loved by users.",
        "description": "Build and ship Flutter apps for iOS and Android with a focus on performance.",
        "requirements": "Flutter, Dart, REST APIs, Firebase, iOS, Android, state management.",
    },
    {
        "title": "QA Automation Engineer",
        "company": "Veritas Quality", "seniority": "mid", "workplace": "hybrid",
        "location": "Austin, TX", "salary": (80000, 115000),
        "summary": "Keep quality high with robust automated testing.",
        "description": "Design test frameworks and pipelines that catch regressions before users do.",
        "requirements": "Python, Selenium, Playwright, pytest, CI/CD, API testing, SQL.",
    },
    {
        "title": "Data Analyst (SQL/Tableau)",
        "company": "Insight Partners Co", "seniority": "junior", "workplace": "remote",
        "location": "Remote", "salary": (65000, 95000),
        "summary": "Turn data into decisions for product and growth teams.",
        "description": "Build dashboards, run analyses, and tell clear stories with data.",
        "requirements": "SQL, Tableau, Excel, Python, statistics, data visualization.",
    },
    {
        "title": "Cloud Security Engineer",
        "company": "Aegis Security", "seniority": "senior", "workplace": "remote",
        "location": "Remote", "salary": (125000, 170000),
        "summary": "Secure cloud infrastructure at scale.",
        "description": "Harden cloud environments, automate security controls, and lead incident response.",
        "requirements": "AWS, Kubernetes, Terraform, IAM, Python, SIEM, threat modeling.",
    },
    {
        "title": "Product Manager",
        "company": "Lattice Works", "seniority": "senior", "workplace": "hybrid",
        "location": "Amsterdam, NL", "salary": (110000, 150000),
        "summary": "Own the roadmap for a B2B product line.",
        "description": "Define strategy, prioritize ruthlessly, and ship outcomes with engineering and design.",
        "requirements": "Product strategy, roadmapping, analytics, A/B testing, stakeholder management, SQL.",
    },
    {
        "title": "UX Designer",
        "company": "Form & Function", "seniority": "mid", "workplace": "remote",
        "location": "Remote", "salary": (80000, 120000),
        "summary": "Design intuitive experiences end to end.",
        "description": "Run research, craft flows and prototypes, and partner with engineers to ship.",
        "requirements": "Figma, user research, prototyping, design systems, usability testing.",
    },
]


def _generate_jobs(db: Session, n: int) -> list[Job]:
    """Insert ``n`` distinct sample jobs (active + public) and sync them."""
    picks = random.sample(_SAMPLE_JOBS, k=min(n, len(_SAMPLE_JOBS)))
    created: list[Job] = []
    now = datetime.now(timezone.utc)
    for tpl in picks:
        smin, smax = tpl["salary"]
        job = Job(
            title=tpl["title"],
            company_name=tpl["company"],
            summary=tpl["summary"],
            description_text=tpl["description"],
            requirements=tpl["requirements"],
            seniority_level=tpl["seniority"],
            employment_type="full_time",
            workplace_type=tpl["workplace"],
            location_text=tpl["location"],
            location_mode="remote" if tpl["workplace"] == "remote" else "onsite",
            salary_min=float(smin),
            salary_max=float(smax),
            salary_currency="USD",
            application_mode="internal_apply",
            visibility="public",
            status="active",
            is_active=True,
            source_type="generated",
            source_platform="sample_seed",
            posted_at=now,
            canonical_hash=None,  # NULL avoids the unique-hash collision
        )
        db.add(job)
        created.append(job)
    db.commit()

    for job in created:
        db.refresh(job)
        try:
            sync_job_full(db, job.id)  # embed → Qdrant + AGE (best-effort)
        except Exception:  # noqa: BLE001
            logger.exception("[discover_import] sync failed for seed job %s", job.id)
    return created


async def import_fresh_jobs(db: Session, *, limit: int = 5) -> dict[str, Any]:
    """Import up to ``limit`` fresh jobs: live scrape first, then top up."""
    scraped_new = 0
    try:
        svc = JobImportService()
        result = await asyncio.wait_for(
            svc.run_import(
                limit=limit,
                source=settings.job_scraper_source,
                admin_override=True,
            ),
            timeout=_SCRAPE_TIMEOUT_SECONDS,
        )
        scraped_new = int(result.inserted_count or 0)
    except (asyncio.TimeoutError, Exception) as exc:  # noqa: BLE001
        logger.warning("[discover_import] scrape unavailable, falling back: %s", exc)
        scraped_new = 0

    need = max(0, limit - scraped_new)
    generated = len(_generate_jobs(db, need)) if need > 0 else 0

    source = (
        "scraped" if generated == 0
        else "generated" if scraped_new == 0
        else "mixed"
    )
    return {
        "imported": scraped_new + generated,
        "scraped": scraped_new,
        "generated": generated,
        "source": source,
    }


__all__ = ["import_fresh_jobs"]
