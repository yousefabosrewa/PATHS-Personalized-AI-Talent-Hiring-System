"""Sourcing agent nodes (5-node pipeline).

search_query → filter → deduplicate → enrich → persist

Uses the mock sourcing provider for the demo; swapping in a real provider
(LinkedIn, Hunter.io, etc.) only requires changing the provider config.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.db.models import Job, Candidate, CandidatePoolRun, CandidatePoolMember
from app.db.models.agent_runs import AgentRun
from app.agents.sourcing.state import SourcingState

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_db() -> Session:
    return SessionLocal()


def _advance_run(db: Session, run_id: str | None, node: str) -> None:
    if not run_id:
        return
    run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
    if run:
        run.current_node = node
        db.commit()


# ── Node 1: search_query ─────────────────────────────────────────────────────

def search_query_node(state: SourcingState) -> dict[str, Any]:
    """Load job context and retrieve candidate matches from the configured provider."""
    db = _get_db()
    try:
        _advance_run(db, state.get("agent_run_id"), "search_query")

        job_id = state["job_id"]
        org_id = state["organization_id"]
        top_k = state.get("top_k", 20)
        provider = state.get("provider", "mock")

        # Load job context
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return {"status": "failed", "error": f"Job {job_id} not found"}

        job_context = {
            "job_id": str(job.id),
            "title": job.title or "",
            "skills": [],
            "seniority": getattr(job, "seniority_level", "") or "",
            "location": getattr(job, "location_text", "") or "",
        }

        # Fetch from provider
        if provider == "mock":
            raw_candidates = _mock_search(job_context, top_k, org_id)
        elif provider == "internal_pool":
            raw_candidates = _internal_pool_search(db, job_context, top_k, org_id)
        else:
            # Extensible: add LinkedIn, Hunter.io, etc.
            raw_candidates = _mock_search(job_context, top_k, org_id)

        return {
            "job_context": job_context,
            "raw_candidates": raw_candidates,
        }
    except Exception as exc:
        logger.exception("search_query_node failed")
        return {"status": "failed", "error": str(exc)}
    finally:
        db.close()


def _mock_search(job_context: dict, top_k: int, org_id: str) -> list[dict]:
    """Generate realistic-looking mock candidate results for the demo."""
    import random, hashlib
    seed = hashlib.md5(f"{org_id}{job_context['title']}".encode()).hexdigest()
    rng = random.Random(seed)

    first_names = ["Alex", "Jordan", "Sam", "Taylor", "Morgan", "Casey", "Jamie", "Riley"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Davis", "Miller", "Wilson"]
    titles = [
        f"Senior {job_context['title']}", job_context['title'],
        f"Lead {job_context['title']}", f"Principal {job_context['title']}",
    ]
    skills = ["Python", "FastAPI", "React", "TypeScript", "PostgreSQL", "Docker", "AWS"]

    results = []
    for i in range(min(top_k, len(first_names) * len(last_names))):
        fn = rng.choice(first_names)
        ln = rng.choice(last_names)
        results.append({
            "id": str(uuid.UUID(hashlib.md5(f"{fn}{ln}{i}".encode()).hexdigest())),
            "full_name": f"{fn} {ln}",
            "headline": rng.choice(titles),
            "email": f"{fn.lower()}.{ln.lower()}@example.com",
            "location": job_context.get("location") or "Remote",
            "years_experience": rng.randint(2, 12),
            "skills": rng.sample(skills, k=rng.randint(3, 5)),
            "score": round(rng.uniform(0.55, 0.95), 2),
            "source": "mock",
        })
    return sorted(results, key=lambda c: c["score"], reverse=True)


def _internal_pool_search(db: Session, job_context: dict, top_k: int, org_id: str) -> list[dict]:
    """Pull candidates from the internal CandidatePoolMember table."""
    members = (
        db.query(CandidatePoolMember)
        .filter(CandidatePoolMember.organization_id == org_id)
        .limit(top_k)
        .all()
    )
    return [
        {
            "id": str(m.candidate_id),
            "full_name": getattr(m, "full_name", "Unknown"),
            "email": getattr(m, "email", ""),
            "score": float(getattr(m, "match_score", 0.5) or 0.5),
            "source": "internal_pool",
        }
        for m in members
    ]


# ── Node 2: filter ────────────────────────────────────────────────────────────

def filter_node(state: SourcingState) -> dict[str, Any]:
    """Apply score threshold, location, and workplace filters."""
    db = _get_db()
    try:
        _advance_run(db, state.get("agent_run_id"), "filter")

        raw = state.get("raw_candidates", [])
        min_score = state.get("min_score", 0.6)
        location_filter = state.get("location_filter")
        workplace_filter = state.get("workplace_filter", [])

        filtered = []
        for c in raw:
            if c.get("score", 0) < min_score:
                continue
            if location_filter and location_filter.lower() not in (c.get("location") or "").lower():
                continue
            filtered.append(c)

        return {"filtered_candidates": filtered}
    finally:
        db.close()


# ── Node 3: deduplicate ───────────────────────────────────────────────────────

def deduplicate_node(state: SourcingState) -> dict[str, Any]:
    """Remove candidates already in the org's candidate pool."""
    db = _get_db()
    try:
        _advance_run(db, state.get("agent_run_id"), "deduplicate")

        filtered = state.get("filtered_candidates", [])
        org_id = state["organization_id"]

        # Collect existing candidate IDs in the pool
        existing_ids: set[str] = set()
        existing_emails: set[str] = set()

        # Query existing pool members for this org
        members = (
            db.query(CandidatePoolMember)
            .filter(CandidatePoolMember.organization_id == org_id)
            .all()
        )
        for m in members:
            existing_ids.add(str(m.candidate_id))

        # Also check existing candidates by email to avoid re-ingesting
        existing_candidates = (
            db.query(Candidate)
            .filter(Candidate.organization_id == org_id)
            .all()
        )
        for cand in existing_candidates:
            email = getattr(cand, "email", None)
            if email:
                existing_emails.add(email.lower())

        deduped = [
            c for c in filtered
            if c.get("id") not in existing_ids
            and (c.get("email") or "").lower() not in existing_emails
        ]

        return {"deduplicated_candidates": deduped}
    finally:
        db.close()


# ── Node 4: enrich ────────────────────────────────────────────────────────────

def enrich_node(state: SourcingState) -> dict[str, Any]:
    """Enrich candidates with additional metadata.

    For the demo this is a no-op / minimal enrichment.
    In production, wire in Hunter.io MCP or Clearbit here.
    """
    db = _get_db()
    try:
        _advance_run(db, state.get("agent_run_id"), "enrich")
        deduped = state.get("deduplicated_candidates", [])

        enriched = []
        for c in deduped:
            enriched.append({
                **c,
                "enriched": True,
                # Demo: add a placeholder LinkedIn URL
                "linkedin_url": f"https://linkedin.com/in/{c.get('full_name','').lower().replace(' ','-')}-demo",
            })

        return {"enriched_candidates": enriched}
    finally:
        db.close()


# ── Node 5: persist ───────────────────────────────────────────────────────────

def persist_node(state: SourcingState) -> dict[str, Any]:
    """Save new candidates and create/update the CandidatePoolRun record."""
    db = _get_db()
    try:
        _advance_run(db, state.get("agent_run_id"), "persist")

        enriched = state.get("enriched_candidates", [])
        org_id = state["organization_id"]
        job_id = state["job_id"]

        # Create or find an existing pool run for this job
        pool_run = CandidatePoolRun(
            id=uuid.uuid4(),
            organization_id=org_id,
            job_id=job_id,
            status="completed",
            candidates_found=len(enriched),
        )
        db.add(pool_run)
        db.flush()

        persisted = 0
        for c in enriched:
            # Create Candidate record if it doesn't exist
            cand_id = c.get("id")
            if cand_id:
                existing = db.query(Candidate).filter(Candidate.id == cand_id).first()
            else:
                existing = None

            if not existing:
                new_cand = Candidate(
                    id=cand_id or str(uuid.uuid4()),
                    organization_id=org_id,
                    full_name=c.get("full_name", "Unknown"),
                    email=c.get("email"),
                    headline=c.get("headline"),
                    years_experience=c.get("years_experience"),
                )
                db.add(new_cand)
                db.flush()
                cand_id = str(new_cand.id)
                persisted += 1

            # Add pool member record
            member = CandidatePoolMember(
                id=uuid.uuid4(),
                pool_run_id=pool_run.id,
                organization_id=org_id,
                candidate_id=cand_id,
                match_score=c.get("score"),
                source=c.get("source", "unknown"),
            )
            db.add(member)

        db.commit()

        # Complete the agent run
        run_id = state.get("agent_run_id")
        if run_id:
            run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
            if run:
                from datetime import datetime, timezone
                run.status = "completed"
                run.current_node = None
                run.finished_at = datetime.now(timezone.utc)
                run.result_ref = {
                    "pool_run_id": str(pool_run.id),
                    "persisted_count": persisted,
                }
                db.commit()

        return {
            "persisted_count": persisted,
            "pool_run_id": str(pool_run.id),
            "status": "completed",
        }
    except Exception as exc:
        db.rollback()
        logger.exception("persist_node failed")
        return {"status": "failed", "error": str(exc)}
    finally:
        db.close()
