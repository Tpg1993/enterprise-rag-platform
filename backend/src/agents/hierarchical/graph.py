"""LangGraph Workflow Compilation for Hierarchical Multi-Agent Team (Phase 37)."""

import logging
from typing import Any

from langgraph.graph import END, StateGraph
from src.agents.hierarchical.specialists import SpecialistTeam
from src.agents.hierarchical.state import HierarchicalTeamState
from src.agents.hierarchical.supervisor import SupervisorAgent

logger = logging.getLogger("HierarchicalMultiAgentGraph")


def route_supervisor_decision(state: HierarchicalTeamState) -> str:
    """Evaluates supervisor routing output to select next specialist node."""
    next_worker = state.get("next_worker", "SYNTHESIS")
    if next_worker == "RESEARCH":
        return "research"
    if next_worker == "SQL":
        return "sql"
    if next_worker == "CRITIQUE":
        return "critique"
    return "synthesis"


def build_hierarchical_multi_agent_graph() -> Any:
    """Compiles the complete Hierarchical Multi-Agent LangGraph StateGraph."""
    supervisor = SupervisorAgent()
    specialists = SpecialistTeam()

    workflow = StateGraph(HierarchicalTeamState)

    # 1. Register Nodes
    workflow.add_node("supervisor", supervisor.plan_and_route)
    workflow.add_node("research", specialists.run_research)
    workflow.add_node("sql", specialists.run_sql_analytics)
    workflow.add_node("critique", specialists.run_compliance_critique)
    workflow.add_node("synthesis", specialists.run_synthesis)

    # 2. Register Edges
    workflow.set_entry_point("supervisor")

    # Conditional routing from supervisor
    workflow.add_conditional_edges(
        "supervisor",
        route_supervisor_decision,
        {
            "research": "research",
            "sql": "sql",
            "critique": "critique",
            "synthesis": "synthesis",
        },
    )

    # Specialist feedback loop back to supervisor
    workflow.add_edge("research", "supervisor")
    workflow.add_edge("sql", "supervisor")
    workflow.add_edge("critique", "supervisor")

    # Terminal node
    workflow.add_edge("synthesis", END)

    return workflow.compile()
