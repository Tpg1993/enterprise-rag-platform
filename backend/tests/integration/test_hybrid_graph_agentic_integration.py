"""Integration tests for Hybrid-Graph-Agentic RAG strategy through FastAPI."""

import pytest
from httpx import ASGITransport, AsyncClient
from src.api.main import app


@pytest.mark.asyncio
async def test_hybrid_graph_agentic_chat_endpoint():
    """Verifies that POST /api/v1/chat executes successfully with Hybrid-Graph-Agentic strategy."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "query": "Explain Sarvam AI and sarvam-105b language support.",
            "rag_strategy": "Hybrid-Graph-Agentic",
            "tenant_id": "default_tenant",
            "user_id": "usr_hga_integ",
        }
        res = await client.post("/api/v1/chat", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["rag_strategy"] == "Hybrid-Graph-Agentic"
        assert data["framework"] == "langgraph"
        assert data["model"] is not None
        assert data["answer"] is not None
        assert data["latency_ms"] > 0
        assert data["security_verdict"] == "ALLOWED"
