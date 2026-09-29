"""Integration tests for RAG Strategy Catalog and Version Manifest endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient
from src.api.main import app


@pytest.mark.asyncio
async def test_get_rag_strategies_endpoint():
    """Verifies that GET /api/v1/rag/strategies returns HTTP 200 with 15 strategies."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/rag/strategies")
        assert res.status_code == 200
        data = res.json()
        assert data["total_strategies"] == 18
        assert len(data["strategies"]) == 18

        strategy_ids = [s["id"] for s in data["strategies"]]
        assert "Basic" in strategy_ids
        assert "Hybrid-Graph-Agentic" in strategy_ids
        assert "Hierarchical-Multi-Agent" in strategy_ids
        assert "Agentic-Web-RAG" in strategy_ids
        assert "Speculative-Draft-Verify" in strategy_ids
        assert "GraphRAG" in strategy_ids
        assert "SQL-RAG" in strategy_ids
        assert "Multimodal" in strategy_ids


@pytest.mark.asyncio
async def test_get_rag_versions_endpoint():
    """Verifies that GET /api/v1/rag/versions returns HTTP 200 with version.yaml contents."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/rag/versions")
        assert res.status_code == 200
        data = res.json()
        assert data["application"]["version"] == "4.0.0"
        assert data["models"]["llm"]["model"] == "sarvam-105b"
        assert "hybrid_graph_agentic" in data["rag"]
        assert "speculative_draft_verify" in data["rag"]
