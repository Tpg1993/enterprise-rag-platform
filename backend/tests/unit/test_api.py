"""Unit tests for FastAPI endpoints: /api/v1/health and /api/v1/chat."""

import pytest
from httpx import ASGITransport, AsyncClient
from src.api.main import app


@pytest.mark.asyncio
async def test_health_check_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "X-Correlation-ID" in response.headers


@pytest.mark.asyncio
async def test_chat_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/chat",
            json={
                "query": "Explain Sarvam-105b RAG architecture.",
                "rag_strategy": "AUTO",
                "tenant_id": "tenant_test",
            },
        )
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert data["model"] in ("sarvam-105b", "sarvam-105b-mock")
    assert data["trace_id"] != ""
