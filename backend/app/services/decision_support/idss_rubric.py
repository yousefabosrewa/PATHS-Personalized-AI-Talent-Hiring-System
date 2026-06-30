"""
PATHS — Intelligent Decision Support System (IDSS) 9-stage rubric.

Brief-mandated weighted scoring with explicit categories that the existing
6-stage ``scoring_aggregation_service`` does not separate (Vector, Graph,
Outreach, Human Feedback). This module is *additive* — it never replaces
the existing aggregation; the IDSS payload is stored under
``DecisionSupportPacket.packet_json["idss_v2"]`` so the existing v1
breakdown remains intact.

Default weights (sum = 100):

    cv_profile_fit         15
    job_requirement_match  15
    vector_similarity      12
    graph_similarity       10
    outreach_engagement     5
    technical_interview    18
    hr_interview           12
    assessment              8
    human_feedback          5

Override per-job-type via ``IDSS_RUBRIC_WEIGHTS_JSON`` (env, JSON string)
or by passing a ``weights_override`` dict at runtime.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Iterable

logger = logging.getLogger(__name__)


# ── Default rubric ───────────────────────────────────────────────────────


DEFAULT_WEIGHTS: dict[str, float] = {
    "cv_profile_fit": 15,
    "job_requirement_match": 15,
    "vector_similarity": 12,
    "graph_similarity": 10,
    "technical_interview": 18,
    "hr_interview": 12,
    "assessment": 8,
    "human_feedback": 10,
}

# Pre-tuned profile overrides keyed by ``role_family`` or ``interview_type``.
# Pure data — callers can swap in their own at runtime.
ROLE_PROFILE_OVERRIDES: dict[str, dict[str, float]] = {
    "engineering": {  # tilt toward technical signals
        "technical_interview": 22,
        "assessment": 10,
        "hr_interview": 10,
        "outreach_engagement": 4,
        "human_feedback": 4,
    },
    "sales": {  # tilt toward HR/communication
        "hr_interview": 18,
        "outreach_engagement": 8,
        "technical_interview": 10,
        "assessment": 4,
        "human_feedback": 6,
    },
    "internship": {  # learning potential > experience
        "cv_profile_fit": 10,
        "assessment": 16,
        "technical_interview": 14,
        "hr_interview": 16,
        "human_feedback": 6,
    },
}


# ── Score sources ────────────────────────────────────────────────────────


@dataclass
class StageInputs:
    """Raw evidence (0..100) for each rubric stage. ``None`` = missing."""

    cv_profile_fit: float | None = None
    job_requirement_match: float | None = None
    vector_similarity: float | None = None
    graph_similarity: float | None = None
    technical_interview: float | None = None
    hr_interview: float | None = None
    assessment: float | None = None
    human_feedback: float | None = None

    # Free-text evidence per stage — kept verbatim for the agent prompt.
    evidence: dict[str, list[str]] = field(default_factory=dict)

    # Per-stage missing-reason codes, populated by the context collector so
    # the UI can explain *who* needs to provide what instead of just saying
    # "missing". One of:
    #   missing_candidate_input | missing_recruiter_input |
    #   missing_job_requirements | missing_outreach_activity |
    #   not_applicable | available
    # The display label is rendered by the frontend. Defaults to "available"
    # when a value is set, "missing_candidate_input" otherwise.
    missing_reasons: dict[str, str] = field(default_factory=dict)


# Stable mapping the agent uses when it has no specific reason. Tuned to
# the brief: the platform must never blame itself for missing evidence.
STAGE_DEFAULT_MISSING_REASON: dict[str, str] = {
    "cv_profile_fit":        "missing_candidate_input",
    "job_requirement_match": "missing_job_requirements",
    "vector_similarity":     "missing_candidate_input",
    "graph_similarity":      "missing_candidate_input",
    "technical_interview":   "missing_recruiter_input",
    "hr_interview":          "missing_recruiter_input",
    "assessment":            "missing_recruiter_input",
    "human_feedback":        "missing_recruiter_input",
}


@dataclass
class IdssBreakdown:
    final_score: float
    stages: dict[str, dict[str, Any]]
    weights: dict[str, float]
    missing_evidence: list[str]
    overrides_applied: list[str]
    confidence: str   # high | medium | low

    def to_dict(self) -> dict[str, Any]:
        return {
            "final_score": round(self.final_score, 2),
            "stages": self.stages,
            "weights": self.weights,
            "missing_evidence": list(self.missing_evidence),
            "overrides_applied": list(self.overrides_applied),
            "confidence": self.confidence,
        }


# ── Public API ───────────────────────────────────────────────────────────


def resolve_weights(
    *,
    role_family: str | None = None,
    profile: str | None = None,
    weights_override: dict[str, float] | None = None,
) -> dict[str, float]:
    """Pick the active weights dict.

    Priority:
      1. explicit ``weights_override`` argument
      2. env var ``IDSS_RUBRIC_WEIGHTS_JSON`` (advanced ops escape hatch)
      3. ``profile`` -> known ROLE_PROFILE_OVERRIDES key
      4. ``role_family`` -> matched against engineering/sales/internship
      5. DEFAULT_WEIGHTS
    """
    if weights_override:
        return _renormalize({**DEFAULT_WEIGHTS, **weights_override})

    env_blob = os.getenv("IDSS_RUBRIC_WEIGHTS_JSON")
    if env_blob:
        try:
            blob = json.loads(env_blob)
            if isinstance(blob, dict):
                return _renormalize({**DEFAULT_WEIGHTS, **blob})
        except json.JSONDecodeError:
            logger.warning("[IDSS] IDSS_RUBRIC_WEIGHTS_JSON not valid JSON; ignoring")

    key = (profile or _profile_from_role_family(role_family) or "").strip().lower()
    if key and key in ROLE_PROFILE_OVERRIDES:
        return _renormalize({**DEFAULT_WEIGHTS, **ROLE_PROFILE_OVERRIDES[key]})

    return _renormalize(DEFAULT_WEIGHTS.copy())


def compute_idss_breakdown(
    inputs: StageInputs,
    *,
    role_family: str | None = None,
    profile: str | None = None,
    weights_override: dict[str, float] | None = None,
    must_have_skills_missing: bool = False,
    bias_risk: bool = False,
    technical_role: bool = False,
) -> IdssBreakdown:
    """Compute the weighted final score with brief-mandated overrides.

    Honours the brief's override rules:
      * must-have skills missing → cap at "Accept" max (clamped 84)
      * bias risk detected → mark missing_evidence + nudge confidence Low
      * very weak technical interview on a technical role → cap at 74 (Hold)
    """
    weights = resolve_weights(
        role_family=role_family,
        profile=profile,
        weights_override=weights_override,
    )

    missing: list[str] = []
    stages: dict[str, dict[str, Any]] = {}
    weighted_total = 0.0
    used_weight_total = 0.0

    for stage, weight in weights.items():
        raw = getattr(inputs, stage, None)
        ev_list = list(inputs.evidence.get(stage, []) or [])
        # Reason code resolution: prefer what the collector explicitly set,
        # otherwise fall back to the stable per-stage default. The UI uses
        # this to write a clear "missing because X did not provide Y"
        # sentence instead of blaming the platform.
        reason = inputs.missing_reasons.get(stage) if isinstance(inputs.missing_reasons, dict) else None
        if raw is None:
            stages[stage] = {
                "score": None,
                "weight": weight,
                "weighted_score": 0,
                "evidence": ev_list,
                "missing": True,
                "missing_reason": reason or STAGE_DEFAULT_MISSING_REASON.get(stage, "missing_candidate_input"),
            }
            missing.append(stage)
            continue
        clamped = max(0.0, min(100.0, float(raw)))
        weighted = clamped * (weight / 100.0)
        weighted_total += weighted
        used_weight_total += weight
        stages[stage] = {
            "score": round(clamped, 2),
            "weight": weight,
            "weighted_score": round(weighted, 3),
            "evidence": ev_list,
            "missing": False,
            "missing_reason": "available",
        }

    # Re-base weights so missing stages don't unfairly punish; keeps the
    # 0-100 scale intact across runs with partial evidence.
    if used_weight_total > 0:
        rebased = round(weighted_total * (100.0 / used_weight_total), 3)
    else:
        rebased = 0.0

    overrides_applied: list[str] = []
    if must_have_skills_missing and rebased > 84:
        overrides_applied.append("cap_strong_accept_due_to_missing_must_have")
        rebased = 84.0
    if technical_role and (inputs.technical_interview or 0) < 40 and rebased > 74:
        overrides_applied.append("cap_to_hold_due_to_weak_technical_for_technical_role")
        rebased = 74.0
    if bias_risk:
        overrides_applied.append("bias_risk_requires_human_review")

    confidence = _confidence_label(missing_count=len(missing), total=len(weights), bias=bias_risk)

    return IdssBreakdown(
        final_score=round(rebased, 2),
        stages=stages,
        weights=weights,
        missing_evidence=missing,
        overrides_applied=overrides_applied,
        confidence=confidence,
    )


def recommendation_from_score(
    score: float, *, missing_required_evidence: bool = False, bias_risk: bool = False,
) -> str:
    """Threshold mapper from the brief.

    85-100  Strong Accept
    75-84   Accept
    60-74   Hold / Needs Review
    <60     Reject
    """
    if bias_risk or missing_required_evidence:
        # Force review path so HR can adjudicate.
        return "Hold / Needs Review"
    s = max(0.0, min(100.0, float(score)))
    if s >= 85:
        return "Strong Accept"
    if s >= 75:
        return "Accept"
    if s >= 60:
        return "Hold / Needs Review"
    return "Reject"


def detect_bias_risk(human_notes: Iterable[str]) -> tuple[bool, list[str]]:
    """Tiny lexical heuristic — the agent does the deeper check, but we
    want to flag obvious bias triggers BEFORE the LLM runs so we can
    require human review even when the model is offline."""

    triggers = [
        "too young",
        "too old",
        "looks unprofessional",
        "not from a good university",
        "not cultural enough",
        "too pretty",
        "too aggressive for a woman",
        "she/he should focus on family",
        "doesn't look like one of us",
    ]
    matches: list[str] = []
    for note in human_notes or []:
        if not isinstance(note, str):
            continue
        low = note.lower()
        for t in triggers:
            if t in low:
                matches.append(note.strip()[:200])
                break
    return bool(matches), matches


# ── Internals ────────────────────────────────────────────────────────────


def _renormalize(weights: dict[str, float]) -> dict[str, float]:
    """Ensure weights cover only known stages and (re-)scale to 100."""
    cleaned = {k: float(v) for k, v in weights.items() if k in DEFAULT_WEIGHTS}
    total = sum(cleaned.values())
    if total <= 0:
        return DEFAULT_WEIGHTS.copy()
    if abs(total - 100.0) <= 0.01:
        return cleaned
    factor = 100.0 / total
    return {k: round(v * factor, 4) for k, v in cleaned.items()}


def _profile_from_role_family(role_family: str | None) -> str | None:
    if not role_family:
        return None
    rf = role_family.strip().lower()
    if rf in {"engineering", "software", "backend", "frontend", "platform", "devops", "data", "ml", "ai"}:
        return "engineering"
    if rf in {"sales", "account_executive", "bdr", "sdr"}:
        return "sales"
    if rf in {"intern", "internship"}:
        return "internship"
    return None


def _confidence_label(*, missing_count: int, total: int, bias: bool) -> str:
    if bias:
        return "Low"
    ratio = missing_count / max(1, total)
    if ratio >= 0.4:
        return "Low"
    if ratio >= 0.2:
        return "Medium"
    return "High"


__all__ = [
    "DEFAULT_WEIGHTS",
    "IdssBreakdown",
    "ROLE_PROFILE_OVERRIDES",
    "StageInputs",
    "compute_idss_breakdown",
    "detect_bias_risk",
    "recommendation_from_score",
    "resolve_weights",
]
