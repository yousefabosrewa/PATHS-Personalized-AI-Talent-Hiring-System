"""
PATHS Backend -- Interview Intelligence Agent LangGraph workflow.

Pipeline (Phase 2.2):
    transcript_capture  -- load transcript + context from DB; upsert to Qdrant
    -> summarize_transcript  -- LLM: structured summary
    -> hr_evaluation         -- LLM + RAG: HR scorecard
    -> technical_evaluation  -- LLM + RAG: technical scorecard
    -> compliance_guardrail  -- LLM: bias / legal check
    -> decision_support      -- LLM + DB: decision packet + DevelopmentPlan row
    -> END
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.agents.interview_intelligence.nodes import (
    node_compliance,
    node_decision_support,
    node_hr_evaluation,
    node_summarize,
    node_technical_evaluation,
    transcript_capture_node,
)
from app.agents.interview_intelligence.state import InterviewGraphState


def create_interview_analysis_graph():
    workflow = StateGraph(InterviewGraphState)

    # Nodes
    workflow.add_node("transcript_capture", transcript_capture_node)
    workflow.add_node("summarize_transcript", node_summarize)
    workflow.add_node("hr_evaluation", node_hr_evaluation)
    workflow.add_node("technical_evaluation", node_technical_evaluation)
    workflow.add_node("compliance_guardrail", node_compliance)
    workflow.add_node("decision_support", node_decision_support)

    # Edges
    workflow.set_entry_point("transcript_capture")
    workflow.add_edge("transcript_capture", "summarize_transcript")
    workflow.add_edge("summarize_transcript", "hr_evaluation")
    workflow.add_edge("hr_evaluation", "technical_evaluation")
    workflow.add_edge("technical_evaluation", "compliance_guardrail")
    workflow.add_edge("compliance_guardrail", "decision_support")
    workflow.add_edge("decision_support", END)

    return workflow.compile()


interview_analysis_app = create_interview_analysis_graph()
