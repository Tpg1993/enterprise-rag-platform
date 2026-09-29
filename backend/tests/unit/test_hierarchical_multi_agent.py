"""Unit tests for Hierarchical Multi-Agent Supervisor Team (Phase 37)."""

import pytest
from src.agents.hierarchical.specialists import SpecialistTeam
from src.agents.hierarchical.state import HierarchicalTeamState
from src.agents.hierarchical.supervisor import SupervisorAgent
from src.rag.base import RAGRequest, RAGResponse
from src.rag.hierarchical_agentic.strategy import HierarchicalMultiAgentStrategy


@pytest.mark.asyncio
async def test_supervisor_planning_and_routing():
    """Verify Supervisor generates execution plan and transitions states sequentially."""
    supervisor = SupervisorAgent(max_iterations=6)
    initial_state: HierarchicalTeamState = {
        "query": "Assess platform latency and operational compliance.",
        "tenant_id": "test_tenant_hma",
        "plan": [],
        "current_step": 0,
        "research_results": [],
        "sql_results": [],
        "critique_notes": [],
        "final_answer": "",
        "citations": [],
        "agent_traces": [],
        "iteration": 0,
        "next_worker": "SUPERVISOR",
    }

    # Step 1: Initial planning routes to Research
    r1 = await supervisor.plan_and_route(initial_state)
    assert len(r1["plan"]) == 4
    assert r1["next_worker"] == "RESEARCH"

    # Step 2: With research filled, routes to SQL
    state_step2 = dict(initial_state)
    state_step2["plan"] = r1["plan"]
    state_step2["research_results"] = [{"content": "Platform doc snippet"}]
    state_step2["iteration"] = 1
    r2 = await supervisor.plan_and_route(state_step2)
    assert r2["next_worker"] == "SQL"

    # Step 3: With SQL filled, routes to Critique
    state_step3 = dict(state_step2)
    state_step3["sql_results"] = [{"metric": "CSAT", "value": "98%"}]
    state_step3["iteration"] = 2
    r3 = await supervisor.plan_and_route(state_step3)
    assert r3["next_worker"] == "CRITIQUE"

    # Step 4: With Critique filled, routes to Synthesis
    state_step4 = dict(state_step3)
    state_step4["critique_notes"] = ["Zero PII violations"]
    state_step4["iteration"] = 3
    r4 = await supervisor.plan_and_route(state_step4)
    assert r4["next_worker"] == "SYNTHESIS"


@pytest.mark.asyncio
async def test_supervisor_max_iteration_guardrail():
    """Verify supervisor forces synthesis when max iteration bound is reached."""
    supervisor = SupervisorAgent(max_iterations=4)
    state: HierarchicalTeamState = {
        "query": "Infinite loop test",
        "tenant_id": "test_tenant",
        "plan": ["step 1"],
        "current_step": 0,
        "research_results": [],
        "sql_results": [],
        "critique_notes": [],
        "final_answer": "",
        "citations": [],
        "agent_traces": [],
        "iteration": 4,  # Reached limit
        "next_worker": "RESEARCH",
    }
    result = await supervisor.plan_and_route(state)
    assert result["next_worker"] == "SYNTHESIS"


@pytest.mark.asyncio
async def test_specialists_execution():
    """Verify individual specialist agents execute and populate respective state channels."""
    team = SpecialistTeam()
    state: HierarchicalTeamState = {
        "query": "What are platform quotas and vector specifications?",
        "tenant_id": "default_tenant",
        "plan": ["step 1"],
        "current_step": 0,
        "research_results": [],
        "sql_results": [],
        "critique_notes": [],
        "final_answer": "",
        "citations": [],
        "agent_traces": [],
        "iteration": 1,
        "next_worker": "RESEARCH",
    }

    # 1. Research
    res_out = await team.run_research(state)
    assert "research_results" in res_out
    assert len(res_out["agent_traces"]) == 1

    # 2. SQL Analytics
    sql_out = await team.run_sql_analytics(state)
    assert "sql_results" in sql_out
    assert len(sql_out["sql_results"]) > 0

    # 3. Compliance & Critique
    crit_state = dict(state)
    crit_state["research_results"] = res_out["research_results"]
    crit_out = await team.run_compliance_critique(crit_state)
    assert "critique_notes" in crit_out
    assert len(crit_out["critique_notes"]) >= 1

    # 4. Synthesis
    synth_state = dict(state)
    synth_state["research_results"] = res_out["research_results"]
    synth_state["sql_results"] = sql_out["sql_results"]
    synth_state["critique_notes"] = crit_out["critique_notes"]
    synth_out = await team.run_synthesis(synth_state)
    assert "final_answer" in synth_out
    assert "Multi-Agent Executive Assessment" in synth_out["final_answer"]


@pytest.mark.asyncio
async def test_hierarchical_multi_agent_strategy_execution():
    """Verify full end-to-end execution of HierarchicalMultiAgentStrategy."""
    strategy = HierarchicalMultiAgentStrategy()
    request = RAGRequest(
        query="Provide platform operational telemetry and compliance summary.",
        tenant_id="default_tenant",
        rag_strategy="Hierarchical-Multi-Agent",
    )
    response = await strategy.execute(request)

    assert isinstance(response, RAGResponse)
    assert response.rag_strategy == "Hierarchical-Multi-Agent"
    assert len(response.answer) > 50
    assert "Multi-Agent Executive Assessment" in response.answer
    assert response.metadata is not None
    assert "plan" in response.metadata
    assert len(response.metadata["plan"]) == 4
    assert "agent_traces" in response.metadata
    assert len(response.metadata["agent_traces"]) >= 4
