"""Decision Support standalone LangGraph.

Pipeline: gather_signals → synthesize → generate_growth_plan → persist_decision → END

Usage:
    graph = build_decision_support_graph()
    result = await graph.ainvoke({
        "job_id": "...",
        "candidate_id": "...",
        "application_id": "...",
        "organization_id": "...",
    })
"""

from langgraph.graph import StateGraph, END

from app.agents.decision_support.state import DecisionSupportState
from app.agents.decision_support.nodes import (
    gather_signals_node,
    synthesize_node,
    generate_growth_plan_node,
    persist_decision_node,
)


def build_decision_support_graph() -> StateGraph:
    workflow = StateGraph(DecisionSupportState)

    workflow.add_node("gather_signals",       gather_signals_node)
    workflow.add_node("synthesize",           synthesize_node)
    workflow.add_node("generate_growth_plan", generate_growth_plan_node)
    workflow.add_node("persist_decision",     persist_decision_node)

    workflow.set_entry_point("gather_signals")

    workflow.add_edge("gather_signals",       "synthesize")
    workflow.add_edge("synthesize",           "generate_growth_plan")
    workflow.add_edge("generate_growth_plan", "persist_decision")
    workflow.add_edge("persist_decision",     END)

    return workflow.compile()
