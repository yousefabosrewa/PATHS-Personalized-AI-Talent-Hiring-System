"""
PATHS Demo Seed Script — PATHS-184

Creates a demo-ready database in ~30 seconds:

  • 3 organisations (Pending, Active Free, Active Premium)
  • 1 platform admin user
  • 3 recruiter users (one per org)
  • 3 jobs per active org  (6 total)
  • 50 candidate profiles with skills + experience
  • 20 applications spread across jobs
  • 1 screening run with bias report on the first Premium job
  • 1 scheduled interview with transcript + evaluation
  • 1 Hire decision → growth plan for the top candidate
  • Billing plans (free / pro / premium) + subscriptions for active orgs

Run:
    cd backend
    python -m seed.demo

Pass --reset to drop and recreate all seed data (safe for local dev):
    python -m seed.demo --reset

Environment:
    Reads DATABASE_URL from .env / environment variables.
    No external services required — embeddings are random unit vectors.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

# ── Bootstrap path so app.* imports work when running via -m ─────────────
import pathlib, os

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.core.database import SessionLocal, engine
from app.core.security import hash_password
from app.db.models import (
    Base,
    Organization,
    OrganizationStatus,
    User,
    Candidate,
    Job,
    Application,
    OrganizationMember,
    Plan,
    Subscription,
    Invoice,
    AgentRun,
    GrowthPlan,
    BiasReport,
    ScreeningRun,
    ScreeningResult,
    Interview,
    InterviewTranscript,
    InterviewEvaluation,
    CandidateSkill,
    CandidateExperience,
    Skill,
)

NOW = datetime.now(timezone.utc)
RNG = random.Random(42)   # deterministic for reproducible demos


# ────────────────────────────────────────────────────────────────────────────
# Fake data fixtures
# ────────────────────────────────────────────────────────────────────────────

FIRST_NAMES = [
    "Amara", "Ben", "Chloe", "David", "Elena", "Farida", "George",
    "Hannah", "Ibrahim", "Jasmine", "Kevin", "Layla", "Mohamed", "Nadia",
    "Oliver", "Priya", "Quinn", "Rachel", "Samuel", "Tamar", "Uma",
    "Victor", "Wendy", "Xander", "Yuki", "Zara", "Alice", "Bruno",
    "Carmen", "Dimitri", "Evelyn", "Felix", "Grace", "Hugo", "Iris",
    "James", "Kira", "Leo", "Mia", "Noah", "Ophelia", "Patrick",
    "Quentin", "Rosa", "Stefan", "Tina", "Ursula", "Vince", "Willa",
    "Xiu",
]
LAST_NAMES = [
    "Ahmed", "Baker", "Chen", "Diallo", "Evans", "Fischer", "Garcia",
    "Harris", "Ismail", "Jensen", "Kim", "Lopez", "Müller", "Nakamura",
    "Osei", "Patel", "Quinn", "Ramos", "Singh", "Tanaka", "Ueda",
    "Vargas", "White", "Xu", "Yamamoto", "Zhang",
]
TECH_SKILLS = [
    "Python", "TypeScript", "React", "FastAPI", "PostgreSQL", "Docker",
    "Kubernetes", "AWS", "GCP", "Azure", "Machine Learning", "LangChain",
    "SQLAlchemy", "Redis", "GraphQL", "Next.js", "Node.js", "Rust",
    "Go", "Java", "Spark", "Airflow", "dbt", "Terraform", "CI/CD",
]
JOB_TITLES = [
    "Senior Software Engineer",
    "ML Engineer",
    "Backend Engineer",
    "Frontend Engineer",
    "Data Engineer",
    "DevOps Engineer",
    "Product Manager",
    "Engineering Manager",
    "Staff Engineer",
    "Principal Engineer",
]
COMPANIES = [
    "TechCorp", "DataFlow Ltd", "CloudNine", "InnovateCo", "BuildFast",
    "Nexus Systems", "Sigma Analytics", "Vertex AI", "PipelineIO", "AlphaStack",
]
LOCATIONS = [
    "London, UK", "Berlin, Germany", "New York, USA", "Amsterdam, Netherlands",
    "Paris, France", "Dubai, UAE", "Cairo, Egypt", "Toronto, Canada",
    "Sydney, Australia", "Singapore",
]
GENDERS = ["male", "female", "non-binary", "prefer_not_to_say"]


def _name() -> tuple[str, str]:
    return RNG.choice(FIRST_NAMES), RNG.choice(LAST_NAMES)


def _email(first: str, last: str, domain: str = "demo.paths.ai") -> str:
    return f"{first.lower()}.{last.lower()}{RNG.randint(1, 999)}@{domain}"


def _random_unit_vector(dim: int = 768) -> list[float]:
    """Return a random unit vector (fake embedding for demo data)."""
    raw = [RNG.gauss(0, 1) for _ in range(dim)]
    norm = math.sqrt(sum(x * x for x in raw)) or 1.0
    return [x / norm for x in raw]


def _ago(days: int = 0, hours: int = 0) -> datetime:
    return NOW - timedelta(days=days, hours=hours)


# ────────────────────────────────────────────────────────────────────────────
# Seed functions
# ────────────────────────────────────────────────────────────────────────────

def seed_plans(db: Session) -> dict[str, Plan]:
    """Create billing plans unless they already exist."""
    plan_defs = [
        dict(
            code="free", name="Free",
            price_monthly_cents=0, price_annual_cents=0,
            features=["3 active jobs", "10 candidates/month", "Basic analytics"],
            limits={"jobs": 3, "candidates_per_month": 10},
        ),
        dict(
            code="pro", name="Pro",
            price_monthly_cents=9900, price_annual_cents=99000,
            features=["25 active jobs", "100 candidates/month", "Full analytics", "AI screening"],
            limits={"jobs": 25, "candidates_per_month": 100},
        ),
        dict(
            code="premium", name="Premium",
            price_monthly_cents=29900, price_annual_cents=299000,
            features=["Unlimited jobs", "Unlimited candidates", "All agents", "Priority support"],
            limits={"jobs": -1, "candidates_per_month": -1},
        ),
    ]
    plans: dict[str, Plan] = {}
    for pd in plan_defs:
        existing = db.query(Plan).filter_by(code=pd["code"]).first()
        if existing:
            plans[pd["code"]] = existing
        else:
            p = Plan(**pd)
            db.add(p)
            db.flush()
            plans[pd["code"]] = p
            print(f"  ✓ Plan: {pd['name']}")
    return plans


def seed_admin(db: Session) -> User:
    """Create the platform admin account."""
    email = "admin@paths.ai"
    user = db.query(User).filter_by(email=email).first()
    if user:
        print(f"  ✓ Admin already exists: {email}")
        return user
    user = User(
        email=email,
        full_name="Platform Admin",
        hashed_password=hash_password("Admin@123!"),
        account_type="platform_admin",
        is_active=True,
    )
    db.add(user)
    db.flush()
    print(f"  ✓ Admin: {email} / Admin@123!")
    return user


def seed_organizations(
    db: Session, plans: dict[str, Plan], admin: User
) -> list[dict]:
    """Create 3 organisations. Returns list of {org, recruiter, plan} dicts."""
    orgs_spec = [
        dict(
            name="Pending Corp",
            slug="pending-corp",
            status=OrganizationStatus.PENDING_APPROVAL.value,
            is_active=False,
            plan_code="free",
        ),
        dict(
            name="Active Tech Ltd",
            slug="active-tech",
            status=OrganizationStatus.ACTIVE.value,
            is_active=True,
            plan_code="pro",
        ),
        dict(
            name="Premium Ventures",
            slug="premium-ventures",
            status=OrganizationStatus.ACTIVE.value,
            is_active=True,
            plan_code="premium",
        ),
    ]

    results = []
    for spec in orgs_spec:
        org = db.query(Organization).filter_by(slug=spec["slug"]).first()
        if not org:
            org = Organization(
                name=spec["name"],
                slug=spec["slug"],
                status=spec["status"],
                is_active=spec["is_active"],
                industry="Technology",
                contact_email=f"contact@{spec['slug']}.com",
                approved_by_admin_id=admin.id if spec["is_active"] else None,
                approved_at=_ago(30) if spec["is_active"] else None,
            )
            db.add(org)
            db.flush()
            print(f"  ✓ Org: {spec['name']} ({spec['status']})")
        else:
            print(f"  ✓ Org already exists: {spec['name']}")

        # Recruiter user
        recruiter_email = f"recruiter@{spec['slug']}.demo"
        recruiter = db.query(User).filter_by(email=recruiter_email).first()
        if not recruiter:
            f, l = _name()
            recruiter = User(
                email=recruiter_email,
                full_name=f"{f} {l}",
                hashed_password=hash_password("Recruiter@123!"),
                account_type="recruiter",
                is_active=True,
            )
            db.add(recruiter)
            db.flush()

        # Membership
        member = db.query(OrganizationMember).filter_by(
            user_id=recruiter.id, organization_id=org.id
        ).first()
        if not member:
            db.add(OrganizationMember(
                user_id=recruiter.id,
                organization_id=org.id,
                role="admin",
            ))
            db.flush()

        # Subscription
        sub = db.query(Subscription).filter_by(organization_id=org.id).first()
        if not sub:
            plan = plans[spec["plan_code"]]
            sub = Subscription(
                organization_id=org.id,
                plan_id=plan.id,
                status="active" if spec["is_active"] else "pending",
                current_period_start=_ago(days=15),
                current_period_end=_ago(days=-15),
            )
            db.add(sub)
            db.flush()

            # One invoice
            if spec["is_active"] and plan.price_monthly_cents > 0:
                db.add(Invoice(
                    organization_id=org.id,
                    subscription_id=sub.id,
                    amount_cents=plan.price_monthly_cents,
                    currency="USD",
                    status="paid",
                    invoice_date=_ago(days=15),
                    paid_at=_ago(days=15),
                ))
                db.flush()

        results.append({"org": org, "recruiter": recruiter, "plan_code": spec["plan_code"]})

    return results


def seed_jobs(db: Session, orgs_data: list[dict]) -> list[Job]:
    """Create 3 jobs per active org."""
    job_templates = [
        dict(
            title="Senior Python Engineer",
            description_text="""We are looking for a Senior Python Engineer to join our platform team.

You will design and build scalable APIs, work with PostgreSQL and Qdrant,
and collaborate with our AI/ML team to ship production agent systems.

Requirements:
• 5+ years Python experience
• Strong FastAPI or Django REST framework background
• Experience with async programming and SQLAlchemy
• Familiarity with vector databases and LLM tooling

We offer a competitive salary, remote-first culture, and equity.""",
            location_text="London, UK (Remote-friendly)",
            employment_type="full_time",
            seniority_level="senior",
        ),
        dict(
            title="ML Engineer — Hiring AI",
            description_text="""Join the PATHS AI team to build the next generation of hiring intelligence.

You will design LangGraph agent pipelines, fine-tune LLMs for ranking and evaluation,
and ensure our AI decisions are fair and explainable.

Requirements:
• MSc or PhD in ML/NLP, or equivalent industry experience
• Proficiency in Python, PyTorch or JAX
• Experience with LLM APIs (OpenAI, Anthropic, Llama)
• Understanding of fairness-aware ML

Bonus: experience with recruitment or HR-tech domains.""",
            location_text="Berlin, Germany (Hybrid)",
            employment_type="full_time",
            seniority_level="mid",
        ),
        dict(
            title="Frontend Engineer — React/Next.js",
            description_text="""We're hiring a Frontend Engineer to own the recruiter workspace and candidate portal.

You'll work in our Next.js 16 App Router codebase, implement complex data visualisations,
and ensure the UI is accessible and performant.

Requirements:
• 3+ years of React experience
• Strong TypeScript skills
• Experience with TanStack Query and Zod
• Passion for accessibility (WCAG 2.1 AA)

Nice to have: experience with shadcn/ui or Radix UI primitives.""",
            location_text="Amsterdam, Netherlands (Hybrid)",
            employment_type="full_time",
            seniority_level="mid",
        ),
    ]

    all_jobs: list[Job] = []
    for od in orgs_data:
        if od["plan_code"] == "free" and od["org"].status != OrganizationStatus.ACTIVE.value:
            continue   # skip pending org
        for tmpl in job_templates:
            existing = db.query(Job).filter_by(
                organization_id=od["org"].id, title=tmpl["title"]
            ).first()
            if existing:
                all_jobs.append(existing)
                continue
            job = Job(
                organization_id=od["org"].id,
                created_by_user_id=od["recruiter"].id,
                title=tmpl["title"],
                description_text=tmpl["description_text"],
                location_text=tmpl["location_text"],
                employment_type=tmpl.get("employment_type", "full_time"),
                seniority_level=tmpl.get("seniority_level", "mid"),
                status="published",
                visibility="public",
                source_type="manual",
            )
            db.add(job)
            db.flush()
            all_jobs.append(job)
    print(f"  ✓ Jobs: {len(all_jobs)} created/found")
    return all_jobs


def seed_candidates(db: Session, count: int = 50) -> list[Candidate]:
    """Create `count` fake candidates with skills and experience."""
    candidates: list[Candidate] = []
    existing_count = db.query(Candidate).filter(
        Candidate.email.like("%@demo.paths.ai")
    ).count()
    if existing_count >= count:
        print(f"  ✓ Candidates: {existing_count} already exist")
        return list(db.query(Candidate).filter(
            Candidate.email.like("%@demo.paths.ai")
        ).limit(count).all())

    # Ensure Skill rows exist
    skill_map: dict[str, Skill] = {}
    for skill_name in TECH_SKILLS:
        s = db.query(Skill).filter_by(name=skill_name).first()
        if not s:
            s = Skill(name=skill_name, category="technical")
            db.add(s)
            db.flush()
        skill_map[skill_name] = s

    to_create = count - existing_count
    for i in range(to_create):
        fn, ln = _name()
        email = _email(fn, ln)
        # avoid duplication on reruns
        while db.query(Candidate).filter_by(email=email).first():
            email = _email(fn, ln)

        yoe = RNG.randint(2, 15)
        skills_sample = RNG.sample(TECH_SKILLS, k=RNG.randint(4, 10))

        # Create a candidate user (optional — some candidates are sourced)
        cand = Candidate(
            full_name=f"{fn} {ln}",
            email=email,
            phone=f"+44 7{RNG.randint(100, 999)} {RNG.randint(100000, 999999)}",
            current_title=RNG.choice(JOB_TITLES),
            location_text=RNG.choice(LOCATIONS),
            headline=f"{yoe} years of experience building {RNG.choice(TECH_SKILLS)} systems",
            years_experience=yoe,
            career_level="senior" if yoe >= 7 else "mid" if yoe >= 3 else "junior",
            skills=skills_sample,
            open_to_job_types=["full_time"],
            open_to_workplace_settings=RNG.sample(["remote", "hybrid", "onsite"], k=2),
            desired_job_titles=[RNG.choice(JOB_TITLES)],
            summary=(
                f"{fn} is a {RNG.choice(['passionate', 'experienced', 'detail-oriented'])} "
                f"engineer with {yoe} years of hands-on experience in "
                f"{', '.join(skills_sample[:3])}. "
                f"Based in {RNG.choice(LOCATIONS)}, they are open to new opportunities."
            ),
            status="active",
            source_type="paths_profile",
        )
        db.add(cand)
        db.flush()

        # Candidate skills
        for skill_name in skills_sample:
            db.add(CandidateSkill(
                candidate_id=cand.id,
                skill_id=skill_map[skill_name].id,
                proficiency_level=RNG.choice(["beginner", "intermediate", "advanced", "expert"]),
                years_experience=min(yoe, RNG.randint(1, yoe)),
                is_primary=skill_name == skills_sample[0],
            ))

        # Work experience
        company = RNG.choice(COMPANIES)
        start_date = _ago(days=yoe * 365)
        db.add(CandidateExperience(
            candidate_id=cand.id,
            company_name=company,
            title=RNG.choice(JOB_TITLES),
            start_date=start_date.date(),
            end_date=None,
            is_current=True,
            description=f"Building scalable systems using {', '.join(skills_sample[:3])}.",
            location=RNG.choice(LOCATIONS),
        ))
        db.flush()
        candidates.append(cand)

    print(f"  ✓ Candidates: {len(candidates)} created")
    return candidates


def seed_applications(
    db: Session, jobs: list[Job], candidates: list[Candidate]
) -> list[Application]:
    """Spread 20 applications across the published jobs."""
    apps: list[Application] = []
    # Pick a subset of candidates and jobs
    sample_jobs = [j for j in jobs if j.organization_id is not None][:6]
    sample_cands = RNG.sample(candidates, min(20, len(candidates)))

    for idx, cand in enumerate(sample_cands):
        job = sample_jobs[idx % len(sample_jobs)]
        # skip if already applied
        existing = db.query(Application).filter_by(
            candidate_id=cand.id, job_id=job.id
        ).first()
        if existing:
            apps.append(existing)
            continue

        stages = ["applied", "screening", "interview", "offer"]
        stage = stages[min(idx % 4, 3)]
        app = Application(
            candidate_id=cand.id,
            job_id=job.id,
            application_type="standard",
            source_channel="demo_seed",
            current_stage_code=stage,
            pipeline_stage=stage,
            overall_status="active",
        )
        db.add(app)
        db.flush()
        apps.append(app)

    print(f"  ✓ Applications: {len(apps)} created/found")
    return apps


def seed_screening_and_bias(
    db: Session, job: Job, applications: list[Application]
) -> ScreeningRun | None:
    """Create a screening run + bias report for one job."""
    run = db.query(ScreeningRun).filter_by(job_id=job.id).first()
    if run:
        print(f"  ✓ Screening run already exists for: {job.title}")
        return run

    run = ScreeningRun(
        job_id=job.id,
        organization_id=job.organization_id,
        status="completed",
        total_candidates=len(applications),
        processed_candidates=len(applications),
        started_at=_ago(days=5, hours=2),
        completed_at=_ago(days=5),
    )
    db.add(run)
    db.flush()

    # Screening results for each application
    for i, app in enumerate(applications[:10]):
        score = round(RNG.uniform(0.3, 0.95), 3)
        db.add(ScreeningResult(
            screening_run_id=run.id,
            candidate_id=app.candidate_id,
            application_id=app.id,
            score=score,
            recommendation="shortlist" if score >= 0.7 else "review",
            reasoning=f"Candidate demonstrates strong skills in {RNG.choice(TECH_SKILLS)}.",
            rank=i + 1,
        ))
    db.flush()

    # Bias report
    report = db.query(BiasReport).filter_by(screening_run_id=run.id).first()
    if not report:
        db.add(BiasReport(
            screening_run_id=run.id,
            job_id=job.id,
            organization_id=job.organization_id,
            status="completed",
            overall_bias_score=round(RNG.uniform(0.05, 0.15), 4),
            gender_bias_score=round(RNG.uniform(0.02, 0.1), 4),
            ethnicity_bias_score=round(RNG.uniform(0.02, 0.1), 4),
            age_bias_score=round(RNG.uniform(0.01, 0.08), 4),
            flagged_criteria=[],
            summary=(
                "Low overall bias detected. Gender parity is within acceptable range. "
                "Recommend reviewing criteria weighting for years-of-experience scoring."
            ),
            generated_at=_ago(days=4),
        ))
        db.flush()

    print(f"  ✓ Screening run + bias report for: {job.title}")
    return run


def seed_interview_and_decision(
    db: Session, job: Job, candidate: Candidate, recruiter: User
) -> None:
    """Create interview → transcript → evaluation → hire decision → growth plan."""
    # Interview
    interview = db.query(Interview).filter_by(
        job_id=job.id, candidate_id=candidate.id
    ).first()
    if not interview:
        interview = Interview(
            job_id=job.id,
            candidate_id=candidate.id,
            organization_id=job.organization_id,
            interviewer_id=recruiter.id,
            scheduled_at=_ago(days=3),
            duration_minutes=45,
            interview_type="technical",
            status="completed",
            meeting_link="https://meet.example.com/paths-demo",
        )
        db.add(interview)
        db.flush()
        print(f"  ✓ Interview scheduled for: {candidate.full_name}")

    # Transcript
    transcript = db.query(InterviewTranscript).filter_by(
        interview_id=interview.id
    ).first()
    if not transcript:
        turns = [
            {"speaker": "interviewer", "text": "Tell me about your experience with Python async programming."},
            {"speaker": "candidate",   "text": "I have 4 years of experience building async APIs with FastAPI and asyncpg. I find async programming natural for I/O-bound workloads."},
            {"speaker": "interviewer", "text": "Can you describe a challenging system design problem you solved?"},
            {"speaker": "candidate",   "text": "At my last role I redesigned our CV ingestion pipeline to use LangGraph. We reduced processing time from 8 seconds to under 2 seconds by parallelising the embedding and entity extraction nodes."},
            {"speaker": "interviewer", "text": "How do you approach fairness in ML systems?"},
            {"speaker": "candidate",   "text": "I always start with a bias audit on the training data. For our scoring agent, we ran counterfactual testing — swapping gender pronouns in CVs — to ensure scores were invariant to protected attributes."},
        ]
        db.add(InterviewTranscript(
            interview_id=interview.id,
            raw_transcript=json.dumps(turns),
            turn_count=len(turns),
            duration_seconds=2700,
            language="en",
        ))
        db.flush()

    # Evaluation
    evaluation = db.query(InterviewEvaluation).filter_by(
        interview_id=interview.id
    ).first()
    if not evaluation:
        db.add(InterviewEvaluation(
            interview_id=interview.id,
            overall_score=0.87,
            technical_score=0.9,
            communication_score=0.85,
            cultural_fit_score=0.86,
            recommendation="strong_hire",
            strengths=["Deep async Python expertise", "LangGraph experience", "Fairness-aware ML mindset"],
            concerns=["Less experience with Kubernetes"],
            notes="Exceptional candidate. Move to offer stage immediately.",
            evaluated_by="ai",
            evaluated_at=_ago(days=2),
        ))
        db.flush()

    # Growth plan
    growth = db.query(GrowthPlan).filter_by(
        candidate_id=candidate.id, job_id=job.id
    ).first()
    if not growth:
        db.add(GrowthPlan(
            candidate_id=candidate.id,
            job_id=job.id,
            organization_id=job.organization_id,
            status="active",
            title=f"90-Day Onboarding Plan — {job.title}",
            summary=(
                "Strong technical foundation. Focus first 30 days on domain knowledge "
                "(hiring processes, GDPR), then 30 days on Kubernetes proficiency, "
                "then 30 days leading a feature end-to-end."
            ),
            milestones=[
                {"day": 30, "goal": "Complete GDPR + domain knowledge certification", "status": "pending"},
                {"day": 60, "goal": "Ship first production feature independently",     "status": "pending"},
                {"day": 90, "goal": "Lead Kubernetes migration of one microservice",   "status": "pending"},
            ],
            learning_resources=[
                {"title": "FastAPI Advanced Tutorial", "url": "https://fastapi.tiangolo.com/advanced/"},
                {"title": "LangGraph Docs",            "url": "https://langchain-ai.github.io/langgraph/"},
            ],
            created_by_agent=True,
        ))
        db.flush()
        print(f"  ✓ Growth plan created for: {candidate.full_name}")


def seed_agent_runs(db: Session, org_id: uuid.UUID) -> None:
    """Create a handful of completed agent run records for the dashboard."""
    run_types = ["cv_ingestion", "scoring", "sourcing", "decision_support"]
    for rtype in run_types:
        run = AgentRun(
            organization_id=org_id,
            agent_type=rtype,
            status="completed",
            started_at=_ago(days=RNG.randint(1, 10)),
            completed_at=_ago(days=RNG.randint(0, 1)),
            node_count=RNG.randint(3, 8),
            metadata_json={"demo": True},
        )
        db.add(run)
    db.flush()
    print(f"  ✓ Agent runs created for org {org_id}")


# ────────────────────────────────────────────────────────────────────────────
# Entry point
# ────────────────────────────────────────────────────────────────────────────

def _reset_seed_data(db: Session) -> None:
    """Remove rows created by the seed script (those with demo markers)."""
    print("⚠️  Resetting seed data...")
    db.query(Candidate).filter(Candidate.email.like("%@demo.paths.ai")).delete()
    db.query(Organization).filter(Organization.slug.in_([
        "pending-corp", "active-tech", "premium-ventures"
    ])).delete()
    db.query(User).filter(User.email.like("%@demo.paths.ai")).delete()
    db.query(User).filter(User.email == "admin@paths.ai").delete()
    db.query(Plan).filter(Plan.code.in_(["free", "pro", "premium"])).delete()
    db.commit()
    print("  ✓ Seed data cleared\n")


def run(reset: bool = False) -> None:
    settings = get_settings()
    print(f"\n🌱  PATHS Demo Seed  —  {settings.app_env}  —  {settings.database_url[:50]}...\n")

    with SessionLocal() as db:
        if reset:
            _reset_seed_data(db)

        print("── Plans ──────────────────────────────────────────────")
        plans = seed_plans(db)
        db.commit()

        print("\n── Admin user ─────────────────────────────────────────")
        admin = seed_admin(db)
        db.commit()

        print("\n── Organisations ──────────────────────────────────────")
        orgs_data = seed_organizations(db, plans, admin)
        db.commit()

        # Only work with active orgs from here on
        active_orgs = [od for od in orgs_data if od["org"].status == "active"]

        print("\n── Jobs ────────────────────────────────────────────────")
        jobs = seed_jobs(db, orgs_data)
        db.commit()

        print("\n── Candidates ──────────────────────────────────────────")
        candidates = seed_candidates(db, count=50)
        db.commit()

        print("\n── Applications ────────────────────────────────────────")
        apps = seed_applications(db, jobs, candidates)
        db.commit()

        # Pick the Premium org and its first job for the full demo pipeline
        premium_org_data = next(
            (od for od in active_orgs if od["plan_code"] == "premium"), active_orgs[0]
        )
        premium_jobs = [j for j in jobs if j.organization_id == premium_org_data["org"].id]
        if premium_jobs:
            demo_job = premium_jobs[0]
            demo_apps = [a for a in apps if a.job_id == demo_job.id]

            print("\n── Screening + Bias report ─────────────────────────────")
            seed_screening_and_bias(db, demo_job, demo_apps)
            db.commit()

            if demo_apps:
                demo_candidate = db.query(Candidate).filter_by(
                    id=demo_apps[0].candidate_id
                ).first()
                if demo_candidate:
                    print("\n── Interview → Evaluation → Growth plan ────────────────")
                    seed_interview_and_decision(
                        db, demo_job, demo_candidate, premium_org_data["recruiter"]
                    )
                    db.commit()

        print("\n── Agent runs ──────────────────────────────────────────")
        for od in active_orgs:
            seed_agent_runs(db, od["org"].id)
        db.commit()

        print("\n" + "─" * 55)
        print("✅  Demo seed complete!\n")
        print("Login credentials:")
        print("  Platform admin:  admin@paths.ai           /  Admin@123!")
        for od in orgs_data:
            email = f"recruiter@{od['org'].slug}.demo"
            status = "✓ active" if od["org"].status == "active" else "⏳ pending"
            print(f"  Recruiter ({od['plan_code']:8s}): {email}  /  Recruiter@123!  [{status}]")
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PATHS demo data seed script")
    parser.add_argument("--reset", action="store_true", help="Clear existing seed data first")
    args = parser.parse_args()
    run(reset=args.reset)
