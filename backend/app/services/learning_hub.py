"""
PATHS Backend — Candidate Learning Hub recommendation service.

Builds a personalised set of learning recommendations (role roadmaps,
skill roadmaps, project ideas, and best practices) for a candidate, each
linking out to https://roadmap.sh.

Recommendations are scored deterministically from the candidate's profile,
their skill gaps (from saved candidate-job scores), their interests, and the
jobs they have applied to. The scoring formula is the one defined in the
feature brief:

    recommendation_score =
          role_match_score        * 0.35
        + skill_gap_score         * 0.30
        + interest_match_score    * 0.20
        + job_requirement_score   * 0.15

The engine is intentionally LLM-free: it always returns a result, has no
external dependency, and is fast enough to run on every page load.
"""

from __future__ import annotations

import re

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.models.application import Application
from app.db.models.candidate import Candidate
from app.db.models.job import Job
from app.db.models.scoring import CandidateJobScore

logger = get_logger(__name__)


# ── Response schema (camelCase to match the feature brief contract) ────────────


class LearningRecommendation(BaseModel):
    id: str
    title: str
    type: str  # role | skill | project | best_practice
    priority: str  # high | medium | low
    difficulty: str  # beginner | intermediate | advanced
    score: float
    reason: str
    relatedSkills: list[str]
    url: str


class LearningHubSummary(BaseModel):
    recommendedRole: str | None
    topSkillGap: str | None
    recommendedProjectLevel: str
    totalRecommendations: int


class TargetOption(BaseModel):
    """A role the candidate can pick as their learning target."""

    id: str
    label: str


class LearningHubResponse(BaseModel):
    candidateId: str
    candidateName: str
    currentPosition: str | None
    targetRole: str | None
    # The role id currently driving recommendations (chosen or auto-detected).
    targetRoleId: str | None = None
    # The list the candidate can choose their target from.
    availableTargets: list[TargetOption] = []
    summary: LearningHubSummary
    recommendations: list[LearningRecommendation]


# ── roadmap.sh catalogue ───────────────────────────────────────────────────────
# A lightweight static mapping. roadmap.sh is linked directly — never scraped.
# Each entry carries the keywords used to match it to a candidate plus the
# skills the roadmap develops.

ROLE_ROADMAPS: list[dict] = [
    {
        "id": "backend",
        "title": "Backend Developer Roadmap",
        "url": "https://roadmap.sh/backend",
        "difficulty": "intermediate",
        "keywords": [
            "backend", "back end", "back-end", "server side", "server-side",
            "api developer", "django", "flask", "fastapi", "express",
            "spring boot", "rails", "node",
        ],
        "related_skills": [
            "API Design", "Databases", "SQL", "System Design",
            "Authentication", "Caching",
        ],
    },
    {
        "id": "frontend",
        "title": "Frontend Developer Roadmap",
        "url": "https://roadmap.sh/frontend",
        "difficulty": "intermediate",
        "keywords": [
            "frontend", "front end", "front-end", "ui developer",
            "ui engineer", "react", "vue", "angular", "web developer",
        ],
        "related_skills": [
            "HTML", "CSS", "JavaScript", "React", "Accessibility",
            "State Management",
        ],
    },
    {
        "id": "full-stack",
        "title": "Full Stack Developer Roadmap",
        "url": "https://roadmap.sh/full-stack",
        "difficulty": "intermediate",
        "keywords": [
            "full stack", "full-stack", "fullstack", "software engineer",
            "software developer", "web developer", "mern", "mean",
        ],
        "related_skills": [
            "JavaScript", "React", "Node.js", "Databases", "API Design",
            "Deployment",
        ],
    },
    {
        "id": "devops",
        "title": "DevOps Roadmap",
        "url": "https://roadmap.sh/devops",
        "difficulty": "advanced",
        "keywords": [
            "devops", "site reliability", "sre", "platform engineer",
            "infrastructure", "cloud engineer",
        ],
        "related_skills": [
            "Docker", "Kubernetes", "CI/CD", "Linux", "Terraform",
            "Monitoring",
        ],
    },
    {
        "id": "ai-engineer",
        "title": "AI Engineer Roadmap",
        "url": "https://roadmap.sh/ai-engineer",
        "difficulty": "advanced",
        "keywords": [
            "ai engineer", "ai developer", "llm", "genai",
            "generative ai", "machine learning engineer", "ml engineer",
        ],
        "related_skills": [
            "Python", "LLMs", "Prompt Engineering", "AI Agents",
            "Vector Databases", "APIs",
        ],
    },
    {
        "id": "ai-data-scientist",
        "title": "AI & Data Scientist Roadmap",
        "url": "https://roadmap.sh/ai-data-scientist",
        "difficulty": "advanced",
        "keywords": [
            "data scientist", "machine learning", "deep learning",
            "ai researcher", "ml researcher", "nlp",
        ],
        "related_skills": [
            "Python", "Statistics", "Machine Learning", "Pandas",
            "Model Evaluation", "Data Visualisation",
        ],
    },
    {
        "id": "data-analyst",
        "title": "Data Analyst Roadmap",
        "url": "https://roadmap.sh/data-analyst",
        "difficulty": "beginner",
        "keywords": [
            "data analyst", "business analyst", "bi analyst",
            "analytics", "reporting analyst",
        ],
        "related_skills": [
            "SQL", "Excel", "Data Visualisation", "Statistics",
            "Dashboards", "Python",
        ],
    },
    {
        "id": "mlops",
        "title": "MLOps Roadmap",
        "url": "https://roadmap.sh/mlops",
        "difficulty": "advanced",
        "keywords": [
            "mlops", "ml ops", "ml platform", "ml infrastructure",
            "model deployment",
        ],
        "related_skills": [
            "Docker", "Kubernetes", "CI/CD", "Model Serving",
            "Monitoring", "Python",
        ],
    },
    {
        "id": "android",
        "title": "Android Developer Roadmap",
        "url": "https://roadmap.sh/android",
        "difficulty": "intermediate",
        "keywords": ["android", "mobile developer", "kotlin developer"],
        "related_skills": [
            "Kotlin", "Android SDK", "Jetpack Compose", "APIs", "Testing",
        ],
    },
    {
        "id": "qa",
        "title": "QA Engineer Roadmap",
        "url": "https://roadmap.sh/qa",
        "difficulty": "intermediate",
        "keywords": [
            "qa", "quality assurance", "test engineer",
            "automation tester", "sdet",
        ],
        "related_skills": [
            "Test Automation", "Testing", "CI/CD", "Selenium", "APIs",
        ],
    },
    {
        "id": "software-architect",
        "title": "Software Architect Roadmap",
        "url": "https://roadmap.sh/software-design-architecture",
        "difficulty": "advanced",
        "keywords": [
            "architect", "software architect", "technical lead",
            "tech lead", "principal engineer", "staff engineer",
        ],
        "related_skills": [
            "System Design", "Design Patterns", "Scalability",
            "Architecture", "Trade-off Analysis",
        ],
    },
    {
        "id": "cyber-security",
        "title": "Cyber Security Roadmap",
        "url": "https://roadmap.sh/cyber-security",
        "difficulty": "advanced",
        "keywords": [
            "security", "cyber security", "cybersecurity",
            "penetration tester", "security engineer", "infosec",
        ],
        "related_skills": [
            "Networking", "Security", "Cryptography", "OWASP",
            "Threat Modelling",
        ],
    },
]

SKILL_ROADMAPS: list[dict] = [
    {
        "id": "python", "skill": "Python", "title": "Python Roadmap",
        "url": "https://roadmap.sh/python", "difficulty": "beginner",
        "keywords": ["python", "django", "flask", "fastapi", "pandas"],
        "role_categories": [
            "backend", "ai-engineer", "ai-data-scientist", "data-analyst",
            "mlops",
        ],
        "related_skills": ["Python", "OOP", "Testing"],
    },
    {
        "id": "javascript", "skill": "JavaScript", "title": "JavaScript Roadmap",
        "url": "https://roadmap.sh/javascript", "difficulty": "beginner",
        "keywords": ["javascript", "js", "es6", "node"],
        "role_categories": ["frontend", "full-stack", "backend"],
        "related_skills": ["JavaScript", "DOM", "Async Programming"],
    },
    {
        "id": "typescript", "skill": "TypeScript", "title": "TypeScript Roadmap",
        "url": "https://roadmap.sh/typescript", "difficulty": "intermediate",
        "keywords": ["typescript", "ts"],
        "role_categories": ["frontend", "full-stack", "backend"],
        "related_skills": ["TypeScript", "Type Safety", "JavaScript"],
    },
    {
        "id": "react", "skill": "React", "title": "React Roadmap",
        "url": "https://roadmap.sh/react", "difficulty": "intermediate",
        "keywords": ["react", "next.js", "nextjs", "jsx"],
        "role_categories": ["frontend", "full-stack"],
        "related_skills": ["React", "State Management", "Components"],
    },
    {
        "id": "nodejs", "skill": "Node.js", "title": "Node.js Roadmap",
        "url": "https://roadmap.sh/nodejs", "difficulty": "intermediate",
        "keywords": ["node", "node.js", "nodejs", "express"],
        "role_categories": ["backend", "full-stack"],
        "related_skills": ["Node.js", "APIs", "Async Programming"],
    },
    {
        "id": "sql", "skill": "SQL", "title": "SQL Roadmap",
        "url": "https://roadmap.sh/sql", "difficulty": "beginner",
        "keywords": ["sql", "postgres", "mysql", "database", "databases"],
        "role_categories": [
            "backend", "data-analyst", "ai-data-scientist", "full-stack",
        ],
        "related_skills": ["SQL", "Databases", "Query Optimisation"],
    },
    {
        "id": "docker", "skill": "Docker", "title": "Docker Roadmap",
        "url": "https://roadmap.sh/docker", "difficulty": "intermediate",
        "keywords": ["docker", "containers", "containerisation"],
        "role_categories": [
            "backend", "devops", "full-stack", "ai-engineer", "mlops",
        ],
        "related_skills": ["Docker", "Containers", "Deployment"],
    },
    {
        "id": "kubernetes", "skill": "Kubernetes", "title": "Kubernetes Roadmap",
        "url": "https://roadmap.sh/kubernetes", "difficulty": "advanced",
        "keywords": ["kubernetes", "k8s", "helm"],
        "role_categories": ["devops", "backend", "mlops"],
        "related_skills": ["Kubernetes", "Orchestration", "Scaling"],
    },
    {
        "id": "system-design", "skill": "System Design",
        "title": "System Design Roadmap",
        "url": "https://roadmap.sh/system-design", "difficulty": "advanced",
        "keywords": ["system design", "scalability", "distributed systems"],
        "role_categories": [
            "backend", "full-stack", "devops", "software-architect",
            "ai-engineer",
        ],
        "related_skills": ["System Design", "Scalability", "Architecture"],
    },
    {
        "id": "api-design", "skill": "API Design", "title": "API Design Roadmap",
        "url": "https://roadmap.sh/api-design", "difficulty": "intermediate",
        "keywords": ["api", "apis", "rest", "graphql", "api design"],
        "role_categories": ["backend", "full-stack", "ai-engineer"],
        "related_skills": ["API Design", "REST", "Authentication"],
    },
    {
        "id": "git-github", "skill": "Git & GitHub",
        "title": "Git and GitHub Roadmap",
        "url": "https://roadmap.sh/git-github", "difficulty": "beginner",
        "keywords": ["git", "github", "version control"],
        "role_categories": [
            "backend", "frontend", "full-stack", "devops", "ai-engineer",
            "ai-data-scientist", "data-analyst", "qa", "android", "mlops",
            "software-architect", "cyber-security",
        ],
        "related_skills": ["Git", "Version Control", "Collaboration"],
    },
    {
        "id": "aws", "skill": "AWS", "title": "AWS Roadmap",
        "url": "https://roadmap.sh/aws", "difficulty": "intermediate",
        "keywords": ["aws", "cloud", "amazon web services", "ec2", "s3"],
        "role_categories": ["devops", "backend", "mlops", "ai-engineer"],
        "related_skills": ["AWS", "Cloud", "Deployment"],
    },
    {
        "id": "computer-science", "skill": "Computer Science",
        "title": "Computer Science Roadmap",
        "url": "https://roadmap.sh/computer-science", "difficulty": "beginner",
        "keywords": [
            "computer science", "data structures", "algorithms", "cs",
        ],
        "role_categories": [
            "backend", "frontend", "full-stack", "ai-engineer",
            "ai-data-scientist", "software-architect",
        ],
        "related_skills": [
            "Data Structures", "Algorithms", "Problem Solving",
        ],
    },
    {
        "id": "prompt-engineering", "skill": "Prompt Engineering",
        "title": "Prompt Engineering Roadmap",
        "url": "https://roadmap.sh/prompt-engineering",
        "difficulty": "beginner",
        "keywords": ["prompt engineering", "prompting", "llm", "genai"],
        "role_categories": ["ai-engineer", "ai-data-scientist"],
        "related_skills": ["Prompt Engineering", "LLMs", "AI"],
    },
    {
        "id": "ai-agents", "skill": "AI Agents", "title": "AI Agents Roadmap",
        "url": "https://roadmap.sh/ai-agents", "difficulty": "advanced",
        "keywords": ["ai agents", "agentic", "langchain", "langgraph", "rag"],
        "role_categories": ["ai-engineer", "mlops"],
        "related_skills": ["AI Agents", "LLMs", "Orchestration"],
    },
    {
        "id": "java", "skill": "Java", "title": "Java Roadmap",
        "url": "https://roadmap.sh/java", "difficulty": "intermediate",
        "keywords": ["java", "spring", "spring boot"],
        "role_categories": ["backend", "android", "full-stack"],
        "related_skills": ["Java", "OOP", "Spring"],
    },
]

PROJECT_IDEAS: list[dict] = [
    {
        "id": "backend",
        "title": "Backend Project Ideas",
        "url": "https://roadmap.sh/backend/projects",
        "project_type": "Backend",
        "difficulty": "intermediate",
        "keywords": ["backend", "api", "server", "database"],
        "role_categories": ["backend", "full-stack"],
        "related_skills": ["API Design", "Databases", "Authentication"],
        "outcome": "Ship production-style APIs with auth, persistence and tests.",
    },
    {
        "id": "frontend",
        "title": "Frontend Project Ideas",
        "url": "https://roadmap.sh/frontend/projects",
        "project_type": "Frontend",
        "difficulty": "intermediate",
        "keywords": ["frontend", "ui", "react", "web"],
        "role_categories": ["frontend", "full-stack"],
        "related_skills": ["React", "CSS", "State Management"],
        "outcome": "Build polished, responsive interfaces from real designs.",
    },
    {
        "id": "full-stack",
        "title": "Full Stack Project Ideas",
        "url": "https://roadmap.sh/full-stack/projects",
        "project_type": "Full Stack",
        "difficulty": "intermediate",
        "keywords": ["full stack", "fullstack", "web app"],
        "role_categories": ["full-stack", "backend", "frontend"],
        "related_skills": ["API Design", "React", "Databases", "Deployment"],
        "outcome": "Deliver an end-to-end app from database to deployed UI.",
    },
    {
        "id": "devops",
        "title": "DevOps Project Ideas",
        "url": "https://roadmap.sh/devops/projects",
        "project_type": "DevOps",
        "difficulty": "advanced",
        "keywords": ["devops", "infrastructure", "ci/cd", "cloud"],
        "role_categories": ["devops", "mlops"],
        "related_skills": ["Docker", "CI/CD", "Kubernetes", "Monitoring"],
        "outcome": "Automate build, deploy and monitoring pipelines hands-on.",
    },
    {
        "id": "ai-ml",
        "title": "AI & ML Project Ideas",
        "url": "https://roadmap.sh/projects",
        "project_type": "AI / Machine Learning",
        "difficulty": "advanced",
        "keywords": ["ai", "ml", "machine learning", "llm", "data"],
        "role_categories": ["ai-engineer", "ai-data-scientist", "mlops"],
        "related_skills": ["Python", "LLMs", "Model Evaluation"],
        "outcome": "Turn models and LLMs into working, demoable products.",
    },
]

BEST_PRACTICES: list[dict] = [
    {
        "id": "api-security",
        "title": "API Security Best Practices",
        "url": "https://roadmap.sh/best-practices/api-security",
        "topic": "API Security",
        "difficulty": "intermediate",
        "keywords": ["api", "backend", "security", "auth"],
        "role_categories": [
            "backend", "full-stack", "devops", "ai-engineer",
            "cyber-security",
        ],
        "related_skills": ["Authentication", "Authorisation", "OWASP"],
    },
    {
        "id": "backend-performance",
        "title": "Backend Performance Best Practices",
        "url": "https://roadmap.sh/best-practices/backend-performance",
        "topic": "Backend Performance",
        "difficulty": "advanced",
        "keywords": ["backend", "performance", "scalability", "api"],
        "role_categories": ["backend", "full-stack", "software-architect"],
        "related_skills": ["Caching", "Query Optimisation", "Profiling"],
    },
    {
        "id": "frontend-performance",
        "title": "Frontend Performance Best Practices",
        "url": "https://roadmap.sh/best-practices/frontend-performance",
        "topic": "Frontend Performance",
        "difficulty": "intermediate",
        "keywords": ["frontend", "performance", "web", "ui"],
        "role_categories": ["frontend", "full-stack"],
        "related_skills": ["Web Vitals", "Bundling", "Rendering"],
    },
    {
        "id": "code-review",
        "title": "Code Review Best Practices",
        "url": "https://roadmap.sh/best-practices/code-review",
        "topic": "Code Review",
        "difficulty": "beginner",
        "keywords": [
            "code review", "collaboration", "engineering", "developer",
        ],
        "role_categories": [
            "backend", "frontend", "full-stack", "devops", "ai-engineer",
            "qa", "software-architect",
        ],
        "related_skills": ["Code Review", "Collaboration", "Code Quality"],
    },
    {
        "id": "aws",
        "title": "AWS Best Practices",
        "url": "https://roadmap.sh/best-practices/aws",
        "topic": "AWS / Cloud",
        "difficulty": "advanced",
        "keywords": ["aws", "cloud", "infrastructure", "devops"],
        "role_categories": ["devops", "backend", "mlops", "ai-engineer"],
        "related_skills": ["AWS", "Cloud", "Cost Optimisation"],
    },
]

# Default safety net — shown when the candidate profile carries too little
# signal to produce a confident, fully personalised set.
_DEFAULT_IDS = {
    "role": ["full-stack"],
    "skill": ["git-github", "computer-science", "system-design"],
    "project": ["full-stack"],
    "best_practice": ["code-review"],
}

_JUNIOR_LEVELS = {
    "junior", "entry", "entry-level", "intern", "trainee", "graduate",
    "associate", "student",
}
_MID_LEVELS = {"mid", "middle", "intermediate", "mid-level", "mid level"}
_SENIOR_LEVELS = {
    "senior", "lead", "principal", "staff", "manager", "director", "head",
    "vp", "executive", "architect",
}

_ACRONYMS = {
    "api", "apis", "sql", "aws", "gcp", "ci", "cd", "ci/cd", "css", "html",
    "ml", "ai", "oop", "tdd", "ui", "ux", "jwt", "orm", "rest", "grpc",
    "npm", "seo", "etl", "llm", "llms", "nlp", "k8s", "devops", "mlops",
    "ios", "qa", "owasp", "dom",
}


# ── Helpers ────────────────────────────────────────────────────────────────────


def _norm(text: str | None) -> str:
    return (text or "").strip().lower()


def _pretty(skill: str | None) -> str:
    """Title-case a skill name, keeping known acronyms upper-case."""
    raw = (skill or "").strip()
    if not raw:
        return ""
    words = []
    for word in raw.split():
        words.append(
            word.upper() if word.lower() in _ACRONYMS else word.capitalize()
        )
    return " ".join(words)


def _join_pretty(items: list[str]) -> str:
    pretty = [_pretty(x) for x in items if x]
    if not pretty:
        return ""
    if len(pretty) == 1:
        return pretty[0]
    return ", ".join(pretty[:-1]) + " and " + pretty[-1]


def _skill_name(raw: object) -> str:
    """A missing/matched skill entry may be a plain string or a dict."""
    if isinstance(raw, str):
        return raw.strip()
    if isinstance(raw, dict):
        for key in ("skill", "name", "skill_name", "skill_name_normalized"):
            value = raw.get(key)
            if value:
                return str(value).strip()
    return ""


def _kw_hit(keywords: list[str], text: str) -> bool:
    """True when any keyword appears in the (already lower-cased) text."""
    return any(kw and kw in text for kw in keywords)


def _candidate_level(career_level: str | None, years: int | None) -> str:
    level = _norm(career_level)
    yrs = years or 0
    if level in _SENIOR_LEVELS:
        return "advanced"
    if level in _MID_LEVELS:
        return "intermediate"
    if level in _JUNIOR_LEVELS:
        return "beginner"
    if yrs >= 6:
        return "advanced"
    if yrs <= 2:
        return "beginner"
    return "intermediate"


def _priority(score: float, force_high: bool = False) -> str:
    if force_high:
        return "high"
    if score >= 0.6:
        return "high"
    if score >= 0.38:
        return "medium"
    return "low"


# ── Signal gathering ───────────────────────────────────────────────────────────


def _gather_signals(db: Session, candidate: Candidate) -> dict:
    """Collect every personalisation signal from the candidate's profile."""
    current_position = (candidate.current_title or "").strip()
    desired_titles = [t.strip() for t in (candidate.desired_job_titles or []) if t]
    target_role = desired_titles[0] if desired_titles else ""
    categories = [c.strip() for c in (candidate.desired_job_categories or []) if c]
    candidate_skills = {_norm(s) for s in (candidate.skills or []) if s}

    required_gap: set[str] = set()
    preferred_gap: set[str] = set()
    role_families: set[str] = set()
    try:
        scores = db.execute(
            select(CandidateJobScore).where(
                CandidateJobScore.candidate_id == candidate.id
            )
        ).scalars().all()
        for row in scores:
            for raw in row.missing_required_skills or []:
                name = _norm(_skill_name(raw))
                if name:
                    required_gap.add(name)
            for raw in row.missing_preferred_skills or []:
                name = _norm(_skill_name(raw))
                if name:
                    preferred_gap.add(name)
            if row.role_family:
                role_families.add(_norm(row.role_family))
    except Exception as exc:  # pragma: no cover - resilience only
        logger.warning("learning-hub: skill-gap lookup failed: %s", exc)

    applied_titles: list[str] = []
    try:
        applied_titles = list(
            db.execute(
                select(Job.title)
                .select_from(Application)
                .join(Job, Application.job_id == Job.id)
                .where(Application.candidate_id == candidate.id)
            ).scalars().all()
        )
    except Exception as exc:  # pragma: no cover - resilience only
        logger.warning("learning-hub: applied-job lookup failed: %s", exc)

    all_gaps = required_gap | preferred_gap
    role_text = _norm(
        " ".join([current_position, " ".join(desired_titles), " ".join(role_families)])
    )
    interest_text = _norm(
        " ".join(
            [
                candidate.headline or "",
                candidate.summary or "",
                " ".join(categories),
                " ".join(desired_titles),
            ]
        )
    )
    applied_text = _norm(" ".join(t for t in applied_titles if t))
    # A bag-of-words of the candidate's own skills — lets the scorer react
    # when a CV upload adds skills, even if the job title never changed.
    skills_text = " ".join(sorted(candidate_skills))

    return {
        "current_position": current_position,
        "target_role": target_role,
        "candidate_skills": candidate_skills,
        "required_gap": required_gap,
        "all_gaps": all_gaps,
        "role_text": role_text,
        "interest_text": interest_text,
        "applied_text": applied_text,
        "skills_text": skills_text,
        "has_signal": bool(
            current_position
            or target_role
            or candidate_skills
            or applied_text
            or interest_text.strip()
        ),
    }


# ── Scoring ────────────────────────────────────────────────────────────────────


def _score_components(
    role_match: float, skill_gap: float, interest: float, job_req: float
) -> float:
    score = (
        role_match * 0.35
        + skill_gap * 0.30
        + interest * 0.20
        + job_req * 0.15
    )
    return round(max(0.0, min(1.0, score)), 4)


def _score_role(item: dict, sig: dict) -> tuple[float, float, list[str]]:
    kw = item["keywords"]
    if _kw_hit(kw, sig["role_text"]):
        role_match = 1.0
    elif _kw_hit(kw, sig["applied_text"]):
        role_match = 0.55
    elif _kw_hit(kw, sig["skills_text"]):
        # The candidate's own skills point at this roadmap.
        role_match = 0.5
    elif _kw_hit(kw, sig["interest_text"]):
        role_match = 0.3
    else:
        role_match = 0.0

    related = [_norm(s) for s in item["related_skills"]]
    gap_hits = [s for s in related if s in sig["all_gaps"]]
    measured_gap = min(1.0, len(gap_hits) / 2.0)
    # A roadmap for the candidate's exact role inherently maps skills they
    # should master, so it earns a modest floor even without measured gaps.
    skill_gap = max(measured_gap, 0.34 if role_match >= 1.0 else 0.0)
    interest = 1.0 if _kw_hit(kw, sig["interest_text"]) else 0.0
    job_req = 1.0 if _kw_hit(kw, sig["applied_text"]) else 0.0

    score = _score_components(role_match, skill_gap, interest, job_req)
    return score, role_match, gap_hits


def _score_skill(item: dict, sig: dict, detected_role: str | None) -> tuple:
    kw = item["keywords"]
    if detected_role and detected_role in item["role_categories"]:
        role_match = 1.0
    elif _kw_hit(kw, sig["role_text"]):
        role_match = 0.6
    elif _kw_hit(kw, sig["skills_text"]):
        role_match = 0.5
    else:
        role_match = 0.0

    skill_key = _norm(item["skill"])
    is_required_gap = skill_key in sig["required_gap"] or any(
        k in sig["required_gap"] for k in kw
    )
    is_gap = skill_key in sig["all_gaps"] or any(k in sig["all_gaps"] for k in kw)
    has_already = skill_key in sig["candidate_skills"] or any(
        k in sig["candidate_skills"] for k in kw
    )

    if is_gap:
        skill_gap = 1.0
    elif has_already:
        skill_gap = 0.15
    elif role_match >= 0.6:
        skill_gap = 0.45
    else:
        skill_gap = 0.2

    interest = 1.0 if _kw_hit(kw, sig["interest_text"]) else 0.0
    job_req = 1.0 if _kw_hit(kw, sig["applied_text"]) else 0.0

    score = _score_components(role_match, skill_gap, interest, job_req)
    return score, is_required_gap, is_gap, has_already


def _score_catalogue_item(
    item: dict, sig: dict, detected_role: str | None
) -> tuple[float, list[str]]:
    """Shared scoring for project ideas and best practices."""
    kw = item["keywords"]
    if detected_role and detected_role in item["role_categories"]:
        role_match = 1.0
    elif _kw_hit(kw, sig["role_text"]):
        role_match = 0.6
    elif _kw_hit(kw, sig["skills_text"]):
        role_match = 0.5
    else:
        role_match = 0.0

    related = [_norm(s) for s in item["related_skills"]]
    gap_hits = [s for s in related if s in sig["all_gaps"]]
    skill_gap = min(1.0, len(gap_hits) / 2.0)
    interest = 1.0 if _kw_hit(kw, sig["interest_text"]) else 0.0
    job_req = 1.0 if _kw_hit(kw, sig["applied_text"]) else 0.0

    score = _score_components(role_match, skill_gap, interest, job_req)
    return score, gap_hits


# ── Reason builders ────────────────────────────────────────────────────────────


def _role_reason(item: dict, gap_hits: list[str], sig: dict) -> str:
    name = item["title"].replace(" Roadmap", "")
    position = sig["current_position"]
    target = sig["target_role"]
    if position and target:
        opening = f"Recommended because you work as {position} and are targeting {target}"
    elif position:
        opening = f"Recommended because your current role as {position} maps onto this path"
    elif target:
        opening = f"Recommended because you're aiming for a {target} role"
    else:
        opening = f"A solid foundation for growing into the {name} track"
    if gap_hits:
        return f"{opening}. It also closes gap areas such as {_join_pretty(gap_hits[:3])}."
    return f"{opening}. It maps the skills employers expect for this role."


def _skill_reason(
    item: dict, is_required_gap: bool, is_gap: bool, has_already: bool, sig: dict
) -> str:
    skill = item["skill"]  # catalogue names are already display-ready
    if is_required_gap:
        return (
            f"Closes a key skill gap — {skill} showed up as a missing "
            f"required skill in roles you were scored against."
        )
    if is_gap:
        return (
            f"{skill} was flagged as a preferred skill you haven't evidenced "
            f"yet — learning it strengthens your match scores."
        )
    if has_already:
        return (
            f"You already list {skill} — this roadmap helps you deepen it "
            f"and fill the gaps employers probe in interviews."
        )
    target = sig["target_role"] or sig["current_position"]
    if target:
        return f"{skill} is a core skill for your {target} direction — worth getting solid."
    return f"{skill} is a high-leverage skill that strengthens your overall profile."


def _project_reason(item: dict, gap_hits: list[str], sig: dict) -> str:
    target = sig["target_role"] or sig["current_position"] or "your next role"
    if gap_hits:
        return (
            f"Hands-on {item['project_type'].lower()} projects let you practise "
            f"{_join_pretty(gap_hits[:3])} through real builds. {item['outcome']}"
        )
    return (
        f"Practical {item['project_type'].lower()} projects turn theory into "
        f"portfolio evidence for {target}. {item['outcome']}"
    )


def _best_practice_reason(item: dict, sig: dict) -> str:
    target = sig["target_role"] or sig["current_position"]
    if target:
        return (
            f"{item['topic']} is what separates strong candidates for {target} "
            f"roles — employers expect it at the next level."
        )
    return (
        f"{item['topic']} sharpens the production-readiness habits that "
        f"hiring teams look for."
    )


# ── Public entry point ─────────────────────────────────────────────────────────


def build_learning_hub(
    db: Session,
    candidate: Candidate,
    *,
    target_role_override: str | None = None,
) -> LearningHubResponse:
    """Produce the personalised Learning Hub payload for one candidate.

    ``target_role_override`` is a ROLE_ROADMAPS id the candidate picked
    manually; when set it pins the recommended path to that role and aligns
    the skill / project / best-practice picks to it.
    """
    sig = _gather_signals(db, candidate)
    level = _candidate_level(candidate.career_level, candidate.years_experience)

    targets = [
        TargetOption(id=r["id"], label=r["title"].replace(" Roadmap", ""))
        for r in ROLE_ROADMAPS
    ]
    by_id = {r["id"]: r for r in ROLE_ROADMAPS}

    chosen = by_id.get(target_role_override) if target_role_override else None
    if chosen:
        # An explicit choice is itself a strong signal and pins the target.
        sig["target_role"] = chosen["title"].replace(" Roadmap", "")
        sig["role_text"] = f"{sig['role_text']} {' '.join(chosen['keywords'])}".strip()
        sig["has_signal"] = True

    base = LearningHubResponse(
        candidateId=str(candidate.id),
        candidateName=candidate.full_name or "Candidate",
        currentPosition=sig["current_position"] or None,
        targetRole=sig["target_role"] or None,
        targetRoleId=chosen["id"] if chosen else None,
        availableTargets=targets,
        summary=LearningHubSummary(
            recommendedRole=None,
            topSkillGap=None,
            recommendedProjectLevel=level.capitalize(),
            totalRecommendations=0,
        ),
        recommendations=[],
    )

    if not sig["has_signal"]:
        # Nothing to personalise from — the UI renders its empty state.
        return base

    threshold = 0.12

    # ── Role roadmaps + primary-role detection ────────────────────────────────
    role_scored: list[tuple[dict, float, float, list[str]]] = []
    for item in ROLE_ROADMAPS:
        score, role_match, gap_hits = _score_role(item, sig)
        if chosen and item["id"] == chosen["id"]:
            # The manually-chosen target is pinned to the top of the list.
            score, role_match = 1.0, 1.0
        role_scored.append((item, score, role_match, gap_hits))

    detected_role: str | None = chosen["id"] if chosen else None
    if detected_role is None:
        best_role_match = 0.0
        for item, score, role_match, _ in role_scored:
            if role_match > best_role_match:
                best_role_match = role_match
                detected_role = item["id"]

    role_recs: list[LearningRecommendation] = []
    for item, score, _, gap_hits in sorted(
        role_scored, key=lambda x: x[1], reverse=True
    ):
        if score < threshold:
            continue
        role_recs.append(
            LearningRecommendation(
                id=f"role-{item['id']}",
                title=item["title"],
                type="role",
                priority=_priority(score),
                difficulty=item["difficulty"],
                score=score,
                reason=_role_reason(item, gap_hits, sig),
                relatedSkills=item["related_skills"],
                url=item["url"],
            )
        )
    role_recs = role_recs[:5]

    # ── Skill roadmaps ────────────────────────────────────────────────────────
    skill_scored = []
    for item in SKILL_ROADMAPS:
        score, is_req_gap, is_gap, has_already = _score_skill(
            item, sig, detected_role
        )
        skill_scored.append((item, score, is_req_gap, is_gap, has_already))

    skill_recs: list[LearningRecommendation] = []
    measured_gap: str | None = None  # a formally-measured missing skill
    focus_skill: str | None = None  # top skill the candidate hasn't evidenced
    for item, score, is_req_gap, is_gap, has_already in sorted(
        skill_scored, key=lambda x: x[1], reverse=True
    ):
        if score < threshold:
            continue
        if measured_gap is None and is_gap:
            measured_gap = item["skill"]
        if focus_skill is None and not has_already:
            focus_skill = item["skill"]
        skill_recs.append(
            LearningRecommendation(
                id=f"skill-{item['id']}",
                title=item["title"],
                type="skill",
                priority=_priority(score, force_high=is_req_gap),
                difficulty=item["difficulty"],
                score=score,
                reason=_skill_reason(item, is_req_gap, is_gap, has_already, sig),
                relatedSkills=item["related_skills"],
                url=item["url"],
            )
        )
    skill_recs = skill_recs[:8]
    # Prefer a formally-measured gap; otherwise surface the top focus skill.
    top_skill_gap = measured_gap or focus_skill

    # ── Project ideas ─────────────────────────────────────────────────────────
    project_recs: list[LearningRecommendation] = []
    project_scored = [
        (item, *_score_catalogue_item(item, sig, detected_role))
        for item in PROJECT_IDEAS
    ]
    for item, score, gap_hits in sorted(
        project_scored, key=lambda x: x[1], reverse=True
    ):
        if score < threshold:
            continue
        project_recs.append(
            LearningRecommendation(
                id=f"project-{item['id']}",
                title=item["title"],
                type="project",
                priority=_priority(score),
                difficulty=item["difficulty"],
                score=score,
                reason=_project_reason(item, gap_hits, sig),
                relatedSkills=item["related_skills"],
                url=item["url"],
            )
        )
    project_recs = project_recs[:4]

    # ── Best practices ────────────────────────────────────────────────────────
    bp_recs: list[LearningRecommendation] = []
    bp_scored = [
        (item, *_score_catalogue_item(item, sig, detected_role))
        for item in BEST_PRACTICES
    ]
    for item, score, _ in sorted(bp_scored, key=lambda x: x[1], reverse=True):
        if score < threshold:
            continue
        bp_recs.append(
            LearningRecommendation(
                id=f"bp-{item['id']}",
                title=item["title"],
                type="best_practice",
                priority=_priority(score),
                difficulty=item["difficulty"],
                score=score,
                reason=_best_practice_reason(item, sig),
                relatedSkills=item["related_skills"],
                url=item["url"],
            )
        )
    bp_recs = bp_recs[:4]

    recommendations = role_recs + skill_recs + project_recs + bp_recs

    # ── Safety net — guarantee a useful page even on thin profiles ────────────
    if len(recommendations) < 5:
        recommendations = _augment_with_defaults(recommendations)

    recommendations.sort(key=lambda r: r.score, reverse=True)

    recommended_role = next(
        (r.title for r in recommendations if r.type == "role"), None
    )
    if chosen:
        recommended_role = chosen["title"]

    # Surface the role actually driving the page (chosen or auto-detected) so
    # the UI dropdown can reflect the current target.
    applied_id = chosen["id"] if chosen else detected_role
    base.targetRoleId = applied_id
    if applied_id and applied_id in by_id:
        base.targetRole = by_id[applied_id]["title"].replace(" Roadmap", "")

    base.summary = LearningHubSummary(
        recommendedRole=recommended_role,
        topSkillGap=top_skill_gap,
        recommendedProjectLevel=level.capitalize(),
        totalRecommendations=len(recommendations),
    )
    base.recommendations = recommendations
    return base


def _augment_with_defaults(
    existing: list[LearningRecommendation],
) -> list[LearningRecommendation]:
    """Append a small, honest default set when personalisation is thin."""
    seen = {rec.id for rec in existing}
    result = list(existing)
    catalogues = {
        "role": (ROLE_ROADMAPS, "role-"),
        "skill": (SKILL_ROADMAPS, "skill-"),
        "project": (PROJECT_IDEAS, "project-"),
        "best_practice": (BEST_PRACTICES, "bp-"),
    }
    default_reason = (
        "A strong default while we learn more about your goals — "
        "add a target role and skills to your profile for sharper picks."
    )
    for rec_type, ids in _DEFAULT_IDS.items():
        catalogue, prefix = catalogues[rec_type]
        for item_id in ids:
            rec_id = f"{prefix}{item_id}"
            if rec_id in seen:
                continue
            item = next((c for c in catalogue if c["id"] == item_id), None)
            if not item:
                continue
            title = item["title"]
            related = item["related_skills"]
            result.append(
                LearningRecommendation(
                    id=rec_id,
                    title=title,
                    type=rec_type,
                    priority="medium",
                    difficulty=item["difficulty"],
                    score=0.3,
                    reason=default_reason,
                    relatedSkills=related,
                    url=item["url"],
                )
            )
            seen.add(rec_id)
    return result
