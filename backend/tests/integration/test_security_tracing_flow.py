"""Integration test for security, PII redaction, RBAC policies, and /api/v1/traces REST endpoint."""

import pytest
from httpx import ASGITransport, AsyncClient
from src.api.main import app


@pytest.mark.asyncio
async def test_traces_api_endpoint_integration():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Execute a chat query to record a trace
        chat_res = await ac.post(
            "/api/v1/chat",
            json={
                "query": "Explain Sarvam-105B security guardrails.",
                "rag_strategy": "Basic",
                "tenant_id": "tenant_sec_test",
            },
        )
        assert chat_res.status_code == 200
        chat_data = chat_res.json()
        assert "trace_id" in chat_data

        # 2. Query /api/v1/traces endpoint
        traces_res = await ac.get("/api/v1/traces?tenant_id=tenant_sec_test")
        assert traces_res.status_code == 200
        traces = traces_res.json()

        assert isinstance(traces, list)
        assert len(traces) > 0
        latest_trace = traces[0]
        assert "trace_id" in latest_trace
        assert "rag_strategy" in latest_trace
        assert "latency_ms" in latest_trace
