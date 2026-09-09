"""Integration test comparing Basic, Hybrid, and MMR strategies side-by-side."""

import pytest
from httpx import ASGITransport, AsyncClient
from src.api.main import app


@pytest.mark.asyncio
async def test_side_by_side_strategy_comparison():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        strategies = [
            "Basic", "Hybrid", "MMR", "Reranked", "Parent-Child",
            "Multi-Query", "HyDE", "Adaptive", "Corrective", "Self-RAG",
            "ReAct", "GraphRAG", "SQL-RAG", "Multimodal"
        ]
        query = "Explain Sarvam-105B multi-architecture RAG platform."

        results = {}
        for strat in strategies:
            res = await ac.post(
                "/api/v1/chat",
                json={
                    "query": query,
                    "rag_strategy": strat,
                    "tenant_id": "comparison_tenant",
                },
            )
            assert res.status_code == 200
            data = res.json()
            assert "answer" in data
            assert data["latency_ms"] >= 0
            assert "token_usage" in data
            results[strat] = data

        assert "Basic" in results
        assert "Hybrid" in results
        assert "MMR" in results
        assert "Reranked" in results
        assert "Parent-Child" in results
        assert "Multi-Query" in results
        assert "HyDE" in results
        assert "Adaptive" in results
        assert "Corrective" in results
        assert "Self-RAG" in results
        assert "ReAct" in results
        assert "GraphRAG" in results
        assert "SQL-RAG" in results
        assert "Multimodal" in results
