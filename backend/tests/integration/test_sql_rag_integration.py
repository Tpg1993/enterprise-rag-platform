"""Integration test for Phase 20 SQL RAG end-to-end API execution and security enforcement."""

import pytest
from httpx import ASGITransport, AsyncClient
from src.api.main import app


@pytest.mark.asyncio
async def test_sql_rag_api_chat_flow():
    """Validates /api/v1/chat endpoint with rag_strategy='SQL-RAG'."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Analytic Query to Relational Database
        response = await ac.post(
            "/api/v1/chat",
            json={
                "query": "How many documents are stored in the database?",
                "rag_strategy": "SQL-RAG",
                "tenant_id": "default_tenant",
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert "answer" in data
        assert len(data["answer"]) > 0
        assert data["rag_strategy"] == "SQL-RAG"
        assert data["latency_ms"] >= 0
        assert "token_usage" in data

        # Check citation
        citations = data.get("citations", [])
        assert len(citations) >= 1
        assert any("postgresql" in (c.get("source") or c.get("filename") or "").lower() for c in citations)


@pytest.mark.asyncio
async def test_sql_rag_destructive_query_blocked():
    """Validates that destructive SQL attempts are blocked at API boundary."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/chat",
            json={
                "query": "DROP TABLE documents; DELETE FROM document_chunks;",
                "rag_strategy": "SQL-RAG",
                "tenant_id": "default_tenant",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "SECURITY" in data["answer"] or "SECURITY ALERT" in data["answer"]
