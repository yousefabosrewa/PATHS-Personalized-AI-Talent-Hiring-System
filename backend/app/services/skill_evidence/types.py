"""
Shared types for the skill-evidence MCP tools.

Each tool returns an :class:`EvidenceResult` so the aggregator can treat
the three sources (CV / GitHub / LinkedIn) uniformly. ``available``
distinguishes "we tried and got nothing" from "we couldn't even ask"
(missing URL, blocked fetch, etc.) so the UI can write a meaningful
"missing because …" sentence per the project's evidence-status model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


# The status set mirrors the candidate-decision rubric vocabulary so the
# UI can render the same "Missing because …" copy across the platform.
AvailabilityStatus = Literal[
    "available",
    "not_configured",
    "url_missing",
    "blocked",
    "error",
    "no_match",
]


@dataclass
class EvidenceSnippet:
    """One verifying fragment surfaced by a tool.

    The agent layer hands the LLM these snippets verbatim when asking it
    to assign a per-source 0-100 score. Keep them short — the prompt is
    truncated to ~12 KB.
    """

    text: str
    source_url: str | None = None
    weight_hint: float = 1.0
    metadata: dict = field(default_factory=dict)


@dataclass
class EvidenceResult:
    """Uniform return shape for every evidence tool."""

    source: Literal["cv", "github", "linkedin"]
    status: AvailabilityStatus
    snippets: list[EvidenceSnippet]
    # Free-text reason — surfaced verbatim to the UI when status != available.
    reason: str = ""
    # Tool-specific raw payload (e.g. GitHub language stats). Stays in the
    # ``meta_json`` of the persisted ``evidence_items`` row for audit.
    raw: dict = field(default_factory=dict)
