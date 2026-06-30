"""
PATHS Backend -- Outreach Agent LangGraph workflow.

Pipeline:
    compose_emails     -- LLM-draft + persist draft OutreachSessions
    -> send_emails     -- send via Gmail; update session status
    -> track_sends     -- mark ScreeningResults + append analytics event
    -> END
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.agents.outreach.nodes import (
    compose_emails_node,
    send_emails_node,
    track_sends_node,
)
from app.agents.outreach.state import OutreachState


def build_outreach_graph() -> StateGraph:
    """Build and compile the outreach agent workflow."""
    workflow = StateGraph(OutreachState)

    workflow.add_node("compose_emails", compose_emails_node)
    workflow.add_node("send_emails", send_emails_node)
    workflow.add_node("track_sends", track_sends_node)

    workflow.set_entry_point("compose_emails")
    workflow.add_edge("compose_emails", "send_emails")
    workflow.add_edge("send_emails", "track_sends")
    workflow.add_edge("track_sends", END)

    return workflow.compile()


__all__ = ["build_outreach_graph"]
