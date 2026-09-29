"""Integration tests for Hierarchical Multi-Agent RAG Strategy and API (Phase 37)."""

import pytest
from httpx import ASGITransport, AsyncClient
from src.api.main import app
from src.rag.hierarchical_agentic.strategy import HierarchicalMultiAgentStrategy
from src.rag.router import get_rag_strategy


@pytest.mark.asyncio
async def test_hierarchical_multi_agent_chat_endpoint():
    """Verify POST /api/v1/chat executes Hierarchical Multi-Agent pipeline successfully."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/chat",
            json={
                "query": "Synthesize operational architecture and compliance metrics.",
                "rag_strategy": "Hierarchical-Multi-Agent",
                "tenant_id": "default_tenant",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["rag_strategy"] == "Hierarchical-Multi-Agent"
        assert len(data["answer"]) > 50
        assert "Multi-Agent Executive Assessment" in data["answer"]
        assert "citations" in data


@pytest.mark.asyncio
async def test_strategies_catalog_includes_hierarchical_agent():
    """Verify GET /api/v1/rag/strategies lists Strategy 16 Hierarchical Multi-Agent."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/rag/strategies")
        assert response.status_code == 200
        data = response.json()
        strat_ids = [s["id"] for s in data["strategies"]]
        assert "Hierarchical-Multi-Agent" in strat_ids

        hierarchical = next(s for s in data["strategies"] if s["id"] == "Hierarchical-Multi-Agent")
        assert hierarchical["framework"] == "langgraph"
        assert hierarchical["category"] == "Multi-Agent Orchestration"


def test_strategy_router_hierarchical_instantiation():
    """Verify factory router instantiates HierarchicalMultiAgentStrategy."""
    strategy = get_rag_strategy("Hierarchical-Multi-Agent")
    assert isinstance(strategy, HierarchicalMultiAgentStrategy)

    strategy_alias = get_rag_strategy("SUPERVISOR")
    assert isinstance(strategy_alias, HierarchicalMultiAgentStrategy)
