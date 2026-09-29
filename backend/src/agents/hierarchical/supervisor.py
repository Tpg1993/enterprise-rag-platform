"""Supervisor Router Agent for Hierarchical Multi-Agent Team (Phase 37).

Analyzes user prompts, formulates execution plans, and dynamically delegates
tasks across specialized worker sub-agents.
"""

import time
from typing import Any

from src.agents.hierarchical.state import AgentTraceStep, HierarchicalTeamState


class SupervisorAgent:
    """Central orchestrator node in the Hierarchical Multi-Agent LangGraph."""

    def __init__(self, max_iterations: int = 6) -> None:
        self.max_iterations = max_iterations

    async def plan_and_route(self, state: HierarchicalTeamState) -> dict[str, Any]:
        """Formulates execution plan and delegates control to the appropriate specialist."""
        query = state.get("query", "")
        plan = state.get("plan", [])
        iteration = state.get("iteration", 0) + 1
        trace_steps = list(state.get("agent_traces", []))

        # Initial planning phase
        if not plan:
            plan = [
                "1. Delegate domain literature retrieval to Research Agent",
                "2. Delegate structured operational metrics retrieval to SQL Analytics Agent",
                "3. Perform security, PII and hallucination audit via Compliance & Critique Agent",
                "4. Compile multi-perspective executive summary via Synthesis Agent",
            ]
            trace_steps.append(
                AgentTraceStep(
                    agent="Supervisor Agent",
                    action="Formulate Execution Plan",
                    summary=f"Decomposed query '{query[:50]}' into 4 specialized team phases.",
                    timestamp=time.time(),
                )
            )

        # Enforce maximum iteration bounds (Safety guardrail)
        if iteration >= self.max_iterations:
            trace_steps.append(
                AgentTraceStep(
                    agent="Supervisor Agent",
                    action="Enforce Execution Boundary",
                    summary="Maximum graph iterations reached. Forcing Synthesis phase.",
                    timestamp=time.time(),
                )
            )
            return {
                "plan": plan,
                "current_step": 3,
                "iteration": iteration,
                "next_worker": "SYNTHESIS",
                "agent_traces": trace_steps,
            }

        # Step routing sequence: Research -> SQL -> Critique -> Synthesis
        if "research_results" not in state or not state["research_results"]:
            next_worker = "RESEARCH"
            next_step = 0
            delegation_msg = "Delegating to Research Agent for unstructured knowledge retrieval."
        elif "sql_results" not in state or not state["sql_results"]:
            next_worker = "SQL"
            next_step = 1
            delegation_msg = "Delegating to SQL & Analytics Agent for relational metrics."
        elif "critique_notes" not in state or not state["critique_notes"]:
            next_worker = "CRITIQUE"
            next_step = 2
            delegation_msg = "Delegating to Compliance & Critique Agent for guardrail validation."
        else:
            next_worker = "SYNTHESIS"
            next_step = 3
            delegation_msg = "Delegating to Synthesis Agent for executive answer consolidation."

        trace_steps.append(
            AgentTraceStep(
                agent="Supervisor Agent",
                action=f"Route Step {next_step + 1}",
                summary=delegation_msg,
                timestamp=time.time(),
            )
        )

        return {
            "plan": plan,
            "current_step": next_step,
            "iteration": iteration,
            "next_worker": next_worker,
            "agent_traces": trace_steps,
        }
