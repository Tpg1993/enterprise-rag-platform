"""State schema for Hierarchical Multi-Agent Supervisor Team (Phase 37)."""

from typing import Any, TypedDict


class AgentTraceStep(TypedDict):
    """Execution trace step for individual sub-agent actions."""

    agent: str
    action: str
    summary: str
    timestamp: float


class HierarchicalTeamState(TypedDict):
    """State object passing between Supervisor and Specialist Agents in LangGraph."""

    query: str
    tenant_id: str
    plan: list[str]
    current_step: int
    research_results: list[dict[str, Any]]
    sql_results: list[dict[str, Any]]
    critique_notes: list[str]
    final_answer: str
    citations: list[dict[str, Any]]
    agent_traces: list[AgentTraceStep]
    iteration: int
    next_worker: str
