"""
PATHS Backend — Screening Service orchestrator.

Creates a ScreeningRun, invokes the LangGraph screening agent pipeline,
and returns the final result with ranked candidates.

Two public entry points:
  - screen_from_database()  — discovers candidates from the DB
  - screen_from_csv()       — imports candidates from an uploaded CSV
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.db.models.screening import ScreeningResult, ScreeningRun

logger = logging.getLogger(__name__)
settings = get_settings()


class ScreeningService:
    """Orchestrates screening runs for a given job."""

    def __init__(self, *, session_factory=SessionLocal) -> None:
        self._session_factory = session_factory

    # ── Public: screen from database ────────────────────────────────────

    async def screen_from_database(
        self,
        *,
        organization_id: UUID,
        job_id: UUID,
        top_k: int = 10,
        force_rescore: bool = False,
    ) -> dict[str, Any]:
        """Discover all DB candidates for a job, score, rank, persist."""
        run = self._create_run(
            organization_id=organization_id,
            job_id=job_id,
            source="database",
            top_k=top_k,
        )
        if run is None:
            return {"ok": False, "error": "could_not_create_screening_run"}

        return await self._execute_pipeline(
            run_id=run.id,
            job_id=job_id,
            organization_id=organization_id,
            source="database",
            top_k=top_k,
            force_rescore=force_rescore,
        )

    # ── Public: screen from CSV upload ──────────────────────────────────

    async def screen_from_csv(
        self,
        *,
        organization_id: UUID,
        job_id: UUID,
        csv_file_bytes: bytes,
        file_name: str,
        top_k: int = 10,
        force_rescore: bool = False,
    ) -> dict[str, Any]:
        """Import candidates from CSV, then score and rank them."""
        run = self._create_run(
            organization_id=organization_id,
            job_id=job_id,
            source="csv_upload",
            top_k=top_k,
        )
        if run is None:
            return {"ok": False, "error": "could_not_create_screening_run"}

        # Import candidates from CSV using the existing org CSV importer
        from app.db.repositories import organization_matching_repo as om_repo
        from app.services.organization_matching import (
            organization_csv_candidate_import_service as csv_svc,
        )

        db: Session = self._session_factory()
        try:
            imp = om_repo.create_candidate_import(
                db,
                {
                    "organization_id": organization_id,
                    "matching_run_id": None,
                    "file_name": file_name,
                },
            )
            db.commit()
            summary = csv_svc.import_candidates_from_csv(
                db,
                organization_id=organization_id,
                matching_run_id=None,
                import_id=imp.id,
                file_bytes=csv_file_bytes,
                _file_name=file_name,
            )
            om_repo.finish_candidate_import(
                db,
                imp.id,
                total_rows=summary.get("total_rows"),
                valid_rows=summary.get("valid_rows"),
                imported_candidates=summary.get("imported_candidates"),
                updated_candidates=summary.get("updated_candidates"),
                failed_rows=summary.get("failed_rows"),
                status="completed",
            )
            db.commit()
            csv_candidate_ids = summary.get("candidate_ids") or []
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            logger.exception("[ScreeningService] CSV import failed")
            self._fail_run(run.id, str(exc))
            return {
                "ok": False,
                "error": f"csv_import_failed: {exc}",
                "screening_run_id": str(run.id),
            }
        finally:
            db.close()

        if not csv_candidate_ids:
            self._fail_run(run.id, "no_valid_candidates_in_csv")
            return {
                "ok": False,
                "error": "no_valid_candidates_in_csv",
                "screening_run_id": str(run.id),
            }

        return await self._execute_pipeline(
            run_id=run.id,
            job_id=job_id,
            organization_id=organization_id,
            source="csv_upload",
            top_k=top_k,
            force_rescore=force_rescore,
            csv_candidate_ids=csv_candidate_ids,
        )

    # ── Pipeline execution ──────────────────────────────────────────────

    async def _execute_pipeline(
        self,
        *,
        run_id: UUID,
        job_id: UUID,
        organization_id: UUID,
        source: str,
        top_k: int,
        force_rescore: bool,
        csv_candidate_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Run the LangGraph screening pipeline."""
        from app.agents.screening.graph import build_screening_graph

        # Mark run as running
        self._update_run_status(run_id, "running")

        initial_state = {
            "job_id": str(job_id),
            "organization_id": str(organization_id),
            "source": source,
            "top_k": top_k,
            "force_rescore": force_rescore,
            "screening_run_id": str(run_id),
            "csv_candidate_ids": csv_candidate_ids or [],
            "discovered_candidate_ids": [],
            "scored_candidates": [],
            "total_scanned": 0,
            "passed_filter": 0,
            "scored_count": 0,
            "failed_count": 0,
            "ranked_results": [],
            "status": "running",
            "error": None,
        }

        try:
            graph = build_screening_graph()
            final_state = await graph.ainvoke(initial_state)
        except Exception as exc:  # noqa: BLE001
            logger.exception("[ScreeningService] pipeline crashed for run %s", run_id)
            self._fail_run(run_id, str(exc))
            return {
                "ok": False,
                "error": f"pipeline_failed: {exc}",
                "screening_run_id": str(run_id),
            }

        status = final_state.get("status", "completed")
        error = final_state.get("error")

        if status == "failed":
            self._fail_run(run_id, error or "unknown_error")
        # rank_and_persist already updated the run to "completed"

        # Build response
        return {
            "ok": True,
            "screening_run_id": str(run_id),
            "job_id": str(job_id),
            "source": source,
            "top_k": top_k,
            "status": status,
            "total_candidates_scanned": final_state.get("total_scanned", 0),
            "candidates_passed_filter": final_state.get("passed_filter", 0),
            "candidates_scored": final_state.get("scored_count", 0),
            "candidates_failed": final_state.get("failed_count", 0),
            "results": final_state.get("ranked_results") or [],
            "error": error,
        }

    # ── Run lifecycle helpers ───────────────────────────────────────────

    def _create_run(
        self,
        *,
        organization_id: UUID,
        job_id: UUID,
        source: str,
        top_k: int,
    ) -> ScreeningRun | None:
        db: Session = self._session_factory()
        try:
            run = ScreeningRun(
                organization_id=organization_id,
                job_id=job_id,
                source=source,
                top_k=top_k,
                status="pending",
                started_at=datetime.now(timezone.utc),
            )
            db.add(run)
            db.commit()
            db.refresh(run)
            return run
        except Exception:
            db.rollback()
            logger.exception("[ScreeningService] could not create screening run")
            return None
        finally:
            db.close()

    def _update_run_status(self, run_id: UUID, status: str) -> None:
        db: Session = self._session_factory()
        try:
            run = db.get(ScreeningRun, run_id)
            if run:
                run.status = status
                db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    def _fail_run(self, run_id: UUID, error_message: str) -> None:
        db: Session = self._session_factory()
        try:
            run = db.get(ScreeningRun, run_id)
            if run:
                run.status = "failed"
                run.error_message = error_message[:2000]
                run.finished_at = datetime.now(timezone.utc)
                db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    # ── Read helpers (used by API) ──────────────────────────────────────

    @staticmethod
    def get_run(run_id: UUID) -> dict[str, Any] | None:
        db: Session = SessionLocal()
        try:
            run = db.get(ScreeningRun, run_id)
            if run is None:
                return None
            return {
                "screening_run_id": str(run.id),
                "organization_id": str(run.organization_id),
                "job_id": str(run.job_id),
                "source": run.source,
                "top_k": run.top_k,
                "status": run.status,
                "total_candidates_scanned": run.total_candidates_scanned or 0,
                "candidates_passed_filter": run.candidates_passed_filter or 0,
                "candidates_scored": run.candidates_scored or 0,
                "candidates_failed": run.candidates_failed or 0,
                "error_message": run.error_message,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            }
        finally:
            db.close()

    @staticmethod
    def get_results(run_id: UUID) -> list[dict[str, Any]]:
        db: Session = SessionLocal()
        try:
            from sqlalchemy import select

            rows = db.execute(
                select(ScreeningResult)
                .where(ScreeningResult.screening_run_id == run_id)
                .order_by(ScreeningResult.rank_position)
            ).scalars().all()

            return [
                {
                    "result_id": str(r.id),
                    "blind_label": r.blind_label,
                    "rank_position": r.rank_position,
                    "agent_score": float(r.agent_score),
                    "vector_similarity_score": float(r.vector_similarity_score),
                    "final_score": float(r.final_score),
                    "relevance_score": float(r.relevance_score) if r.relevance_score else None,
                    "recommendation": r.recommendation,
                    "match_classification": r.match_classification,
                    "status": r.status,
                }
                for r in rows
            ]
        finally:
            db.close()

    @staticmethod
    def get_result_detail(result_id: UUID) -> dict[str, Any] | None:
        db: Session = SessionLocal()
        try:
            r = db.get(ScreeningResult, result_id)
            if r is None:
                return None
            return {
                "result_id": str(r.id),
                "blind_label": r.blind_label,
                "rank_position": r.rank_position,
                "agent_score": float(r.agent_score),
                "vector_similarity_score": float(r.vector_similarity_score),
                "final_score": float(r.final_score),
                "relevance_score": float(r.relevance_score) if r.relevance_score else None,
                "recommendation": r.recommendation,
                "match_classification": r.match_classification,
                "criteria_breakdown": r.criteria_breakdown,
                "matched_skills": list(r.matched_skills or []),
                "missing_required_skills": list(r.missing_required_skills or []),
                "missing_preferred_skills": list(r.missing_preferred_skills or []),
                "strengths": list(r.strengths or []),
                "weaknesses": list(r.weaknesses or []),
                "explanation": r.explanation,
                "status": r.status,
            }
        finally:
            db.close()
