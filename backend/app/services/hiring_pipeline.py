"""
PATHS — per-job hiring pipeline (configurable candidate workflow).

An organisation can decide, per job, exactly which stages a candidate moves
through: e.g. one job is *Assessment → Technical → HR → Mixed → Decision*
while another is just *three interviews, no assessment*.

The pipeline is stored on ``jobs.hiring_pipeline_jsonb`` as::

    {"version": 1, "stages": [
        {"key": "assessment",   "kind": "assessment",          "label": "Skills Assessment"},
        {"key": "interview_1",  "kind": "technical_interview", "label": "Technical Interview"},
        ...
    ]}

The candidate-facing roadmap is always bookended by an implicit **Applied**
start and **Offer → Hired** finish; only the middle is configurable.
"""

from __future__ import annotations

import re
from typing import Any

# ── Catalog of stage kinds an org may add ───────────────────────────────────
# ``group`` tells the UI how to render / interact with the stage:
#   "assessment" → links to the skills test; "interview" → clickable interview
#   detail; "screening" → automated CV review (no candidate action).
STAGE_CATALOG: dict[str, dict[str, str]] = {
    "screening":           {"label": "CV Screening",        "group": "screening"},
    "assessment":          {"label": "Skills Assessment",   "group": "assessment"},
    "hr_interview":        {"label": "HR Interview",        "group": "interview"},
    "technical_interview": {"label": "Technical Interview", "group": "interview"},
    "mixed_interview":     {"label": "Mixed Interview",     "group": "interview"},
}

INTERVIEW_KINDS = {"hr_interview", "technical_interview", "mixed_interview", "interview"}

# Sensible default for jobs that never customised a pipeline — mirrors the
# platform's historical "Screening → Interview" flow.
DEFAULT_PIPELINE: list[dict[str, str]] = [
    {"key": "screening",    "kind": "screening",    "label": "CV Screening"},
    {"key": "hr_interview", "kind": "hr_interview", "label": "Interview"},
]


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (text or "").strip().lower()).strip("_")


def normalize_pipeline(raw: Any) -> list[dict[str, str]]:
    """Coerce arbitrary client/stored input into a clean ordered stage list.

    Accepts either a list of stage dicts/strings, or the wrapped
    ``{"stages": [...]}`` form. Unknown kinds are dropped. Keys are made
    unique so a kind can repeat (e.g. two technical interviews).
    """
    if isinstance(raw, dict):
        raw = raw.get("stages")
    if not isinstance(raw, list):
        return []

    out: list[dict[str, str]] = []
    seen_keys: set[str] = set()
    for i, item in enumerate(raw):
        if isinstance(item, str):
            kind = _slug(item)
            label = None
        elif isinstance(item, dict):
            kind = _slug(str(item.get("kind") or item.get("type") or ""))
            label = item.get("label")
        else:
            continue
        if kind not in STAGE_CATALOG:
            continue
        key = str((item.get("key") if isinstance(item, dict) else "") or kind)
        key = _slug(key) or kind
        while key in seen_keys:
            key = f"{kind}_{i + 1}"
            i += 1  # noqa: PLW2901 - intentional bump for uniqueness
        seen_keys.add(key)
        out.append({
            "key": key,
            "kind": kind,
            "label": str(label).strip() if label else STAGE_CATALOG[kind]["label"],
        })
    return out


def pipeline_for_job(job: Any) -> list[dict[str, str]]:
    """Return the effective (normalised) pipeline for a Job, falling back to
    the default when the job has none configured."""
    raw = getattr(job, "hiring_pipeline_jsonb", None)
    stages = normalize_pipeline(raw)
    return stages or [dict(s) for s in DEFAULT_PIPELINE]


def stage_group(kind: str) -> str:
    return STAGE_CATALOG.get(kind, {}).get("group", "interview")


# ── Map an application's current_stage_code onto the configured pipeline ─────

# Stage codes the backend stamps on ``applications.current_stage_code`` and how
# they relate to the configurable stages. Anything not listed → "applied".
_CODE_TO_KIND_GROUP: dict[str, str] = {
    "applied": "applied", "sourced": "applied", "new": "applied",
    "screening": "screening", "screen": "screening", "cv_screening": "screening",
    "assessment": "assessment", "assessment_pending": "assessment",
    "hr_interview": "hr_interview", "hr": "hr_interview",
    "technical_interview": "technical_interview", "tech_interview": "technical_interview",
    "technical": "technical_interview",
    "mixed_interview": "mixed_interview", "mixed": "mixed_interview",
    "interview": "interview", "panel": "interview",
    "decision": "offer", "offer": "offer", "offered": "offer", "offer_extended": "offer",
    "hired": "hired", "accepted": "hired",
}

_TERMINAL_STATUSES = {"rejected", "declined", "withdrawn", "closed_rejected"}


def _resolve_current_index(
    stages: list[dict[str, str]], code: str, overall_status: str,
) -> int:
    """Index into the full roadmap (0 = Applied, len+1 = Offer, len+2 = Hired)."""
    n = len(stages)
    applied_idx, offer_idx, hired_idx = 0, n + 1, n + 2
    target = _CODE_TO_KIND_GROUP.get(_slug(code), "applied")

    if target == "applied":
        return applied_idx
    if target == "offer":
        return offer_idx
    if target == "hired":
        return hired_idx

    # Find the stage matching the target kind/group.
    def first_index(pred) -> int | None:
        for i, s in enumerate(stages):
            if pred(s):
                return i + 1  # +1 because Applied occupies slot 0
        return None

    if target in ("screening", "assessment"):
        idx = first_index(lambda s: s["kind"] == target)
        if idx is None and target == "assessment":
            idx = first_index(lambda s: s["kind"] == "screening")
        return idx if idx is not None else applied_idx

    # interview-family target — prefer exact kind, else any interview stage.
    idx = first_index(lambda s: s["kind"] == target)
    if idx is None:
        idx = first_index(lambda s: stage_group(s["kind"]) == "interview")
    if idx is None:
        # No interview configured but candidate is "in interview" → treat as
        # the last pre-offer stage.
        return n if n else applied_idx
    return idx


def build_candidate_roadmap(
    stages: list[dict[str, str]],
    current_stage_code: str,
    overall_status: str,
    *,
    has_match_score: bool = False,
) -> dict[str, Any]:
    """Produce the ordered candidate roadmap with per-step state.

    Returns ``{steps: [{key, kind, label, group, state, clickable}], current_index,
    terminal, terminal_label}`` where ``state`` ∈ {done, current, upcoming}.

    When ``has_match_score`` is true, the **CV Screening** stage is treated as
    complete: the candidate↔job match score *is* the automated CV screen, so the
    progress advances past screening even if the stage code hasn't been bumped.
    """
    status = (overall_status or "").strip().lower()
    code = (current_stage_code or "").strip().lower()
    terminal = status in _TERMINAL_STATUSES or code in _TERMINAL_STATUSES

    full: list[dict[str, str]] = [
        {"key": "applied", "kind": "applied", "label": "Applied"},
        *[{"key": s["key"], "kind": s["kind"], "label": s["label"]} for s in stages],
        {"key": "offer", "kind": "offer", "label": "Offer"},
        {"key": "hired", "kind": "hired", "label": "Hired"},
    ]

    current_index = -1 if terminal else _resolve_current_index(stages, code, status)

    # A match score means the CV has been screened → mark CV Screening done and
    # advance the candidate to the stage after it (unless they're already past).
    if has_match_score and not terminal:
        screening_idx = max(
            (i for i, s in enumerate(full) if s["kind"] == "screening"),
            default=-1,
        )
        if screening_idx >= 0 and current_index <= screening_idx:
            current_index = min(screening_idx + 1, len(full) - 1)

    steps: list[dict[str, Any]] = []
    for i, s in enumerate(full):
        grp = (
            "applied" if s["kind"] == "applied"
            else "offer" if s["kind"] == "offer"
            else "hired" if s["kind"] == "hired"
            else stage_group(s["kind"])
        )
        if terminal:
            state = "upcoming"
        elif i < current_index:
            state = "done"
        elif i == current_index:
            state = "current"
        else:
            state = "upcoming"
        clickable = (grp == "interview" and i <= current_index) or (
            s["kind"] == "offer" and i <= current_index
        )
        steps.append({
            "key": s["key"],
            "kind": s["kind"],
            "label": s["label"],
            "group": grp,
            "state": state,
            "clickable": bool(clickable),
        })

    terminal_label = None
    if terminal:
        terminal_label = "Not selected" if status != "withdrawn" and code != "withdrawn" else "Withdrawn"

    return {
        "steps": steps,
        "current_index": current_index,
        "terminal": terminal,
        "terminal_label": terminal_label,
    }
