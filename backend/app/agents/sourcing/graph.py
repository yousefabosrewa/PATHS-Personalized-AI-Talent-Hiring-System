"""Sourcing agent LangGraph definition.

Pipeline: search_query → filter → deduplicate → enrich → persist → END

Usage:
    graph = build_sourcing_graph()
    result = await graph.ainvoke({
        "job_id": "...",
        "organization_id": "...",
        "top_k": 20,
        "provider": "mock",
    })
"""

from langgraph.graph import StateGraph, END

from app.agents.sourcing.state import SourcingState
from app.agents.sourcing.nodes import (
    search_query_node,
    filter_node,
    deduplicate_node,
    enrich_node,
    persist_node,
)


def build_sourcing_graph() -> StateGraph:
    workflow = StateGraph(SourcingState)

    workflow.add_node("search_query",  search_query_node)
    workflow.add_node("filter",        filter_node)
    workflow.add_node("deduplicate",   deduplicate_node)
    workflow.add_node("enrich",        enrich_node)
    workflow.add_node("persist",       persist_node)

    workflow.set_entry_point("search_query")

    workflow.add_edge("search_query",  "filter")
    workflow.add_edge("filter",        "deduplicate")
    workflow.add_edge("deduplicate",   "enrich")
    workflow.add_edge("enrich",        "persist")
    workflow.add_edge("persist",       END)

    return workflow.compile()
