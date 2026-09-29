"""Integration tests for Fact-Checking Guardrail and Chat API endpoints."""

import json

import pytest
from httpx import ASGITransport, AsyncClient
from src.api.main import app


@pytest.mark.asyncio
async def test_security_fact_check_endpoint():
    """Verifies that POST /api/v1/security/fact-check verifies claims against context."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "answer": "Qdrant stores dense embeddings. Redis provides high-performance L2 caching.",
            "context_chunks": [
                {"chunk_id": "c1", "content": "Qdrant vector database indexes BGE-M3 embeddings."},
                {"chunk_id": "c2", "content": "Redis provides distributed caching for responses."},
            ],
            "strict_correction": False,
        }
        res = await client.post("/api/v1/security/fact-check", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["total_claims"] == 2
        assert data["supported_claims"] >= 1
        assert data["grounding_score"] >= 0.50
        assert data["risk_level"] in ("LOW", "MEDIUM", "HIGH")
        assert len(data["claims"]) == 2


@pytest.mark.asyncio
async def test_chat_endpoint_with_fact_check():
    """Verifies that POST /api/v1/chat returns fact_check_score when enable_fact_check=True."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "query": "What are the core vector stores supported in this platform?",
            "rag_strategy": "Basic",
            "tenant_id": "default_tenant",
            "stream": False,
            "enable_fact_check": True,
        }
        res = await client.post("/api/v1/chat", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["fact_check_score"] is not None
        assert 0.0 <= data["fact_check_score"] <= 1.0
        assert data["fact_check_risk"] in ("LOW", "MEDIUM", "HIGH")


@pytest.mark.asyncio
async def test_chat_streaming_with_fact_check():
    """Verifies that POST /api/v1/chat/stream includes fact check metrics in done event."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "query": "Explain how hybrid retrieval fuses sparse and dense scores.",
            "rag_strategy": "Hybrid",
            "tenant_id": "default_tenant",
            "stream": True,
            "enable_fact_check": True,
        }
        res = await client.post("/api/v1/chat/stream", json=payload)
        assert res.status_code == 200
        body = res.text
        assert "data: " in body

        done_event = None
        for line in body.split("\n"):
            if line.startswith("data: "):
                try:
                    parsed = json.loads(line[6:])
                    if parsed.get("type") == "done":
                        done_event = parsed
                        break
                except Exception:
                    continue

        assert done_event is not None
        assert done_event.get("fact_check_score") is not None
        assert done_event.get("fact_check_risk") in ("LOW", "MEDIUM", "HIGH")
