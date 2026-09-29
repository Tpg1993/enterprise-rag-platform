"""Integration tests for Dynamic Context Compression via FastAPI Endpoints (Phase 33)."""

import pytest
from httpx import ASGITransport, AsyncClient
from src.api.main import app


@pytest.mark.asyncio
async def test_chat_with_compression_enabled():
    """Verify POST /api/v1/chat returns compression metrics when enable_compression=True."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/chat",
            json={
                "query": "Explain enterprise security and OPA policies",
                "rag_strategy": "Basic",
                "tenant_id": "premium_tenant",
                "enable_compression": True,
                "compression_target_ratio": 0.6,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "compression_ratio" in data
        assert "tokens_saved" in data
        assert data["security_verdict"] == "ALLOWED"


@pytest.mark.asyncio
async def test_chat_stream_with_compression_enabled():
    """Verify POST /api/v1/chat/stream includes compression metrics in the final done SSE event."""
    import json

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/chat/stream",
            json={
                "query": "Explain architecture of enterprise microservices and databases",
                "rag_strategy": "Basic",
                "tenant_id": "premium_tenant",
                "enable_compression": True,
                "compression_target_ratio": 0.5,
            },
        )
        assert response.status_code == 200

        lines = response.text.split("\n\n")
        done_event_found = False
        for line in lines:
            line = line.strip()
            if line.startswith("data: "):
                payload = json.loads(line[6:])
                if payload.get("type") == "done":
                    done_event_found = True
                    assert "compression_ratio" in payload
                    assert "tokens_saved" in payload

        assert done_event_found is True
