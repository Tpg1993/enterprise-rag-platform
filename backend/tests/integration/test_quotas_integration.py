"""Integration tests for Tenant Quotas, Rate Limiting, and Budget Control API (Phase 32)."""

import pytest
from httpx import ASGITransport, AsyncClient
from src.api.main import app
from src.security.quotas import TenantQuotaService


@pytest.fixture(autouse=True)
def clean_quotas():
    """Resets tenant usage state before and after each test."""
    svc = TenantQuotaService.get_instance()
    svc.reset_tenant_usage("default_tenant")
    svc.reset_tenant_usage("restricted_tenant")
    yield
    svc.reset_tenant_usage("default_tenant")
    svc.reset_tenant_usage("restricted_tenant")


@pytest.mark.asyncio
async def test_get_tenant_quota_endpoint():
    """Verifies that GET /api/v1/tenants/{tenant_id}/quota returns HTTP 200

    with full quota metrics.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/tenants/default_tenant/quota")
        assert res.status_code == 200
        data = res.json()
        assert data["tenant_id"] == "default_tenant"
        assert "rate_limit_rpm" in data
        assert "daily_tokens_used" in data
        assert "daily_spend_usd" in data
        assert "daily_token_percent" in data
        assert data["is_budget_exceeded"] is False


@pytest.mark.asyncio
async def test_reset_tenant_quota_endpoint():
    """Verifies that POST /api/v1/tenants/{tenant_id}/quota/reset clears usage counters."""
    svc = TenantQuotaService.get_instance()
    svc.record_usage("default_tenant", prompt_tokens=500, completion_tokens=500, cost_usd=0.01)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/v1/tenants/default_tenant/quota/reset")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"

        # Verify quota is indeed reset
        status_res = await client.get("/api/v1/tenants/default_tenant/quota")
        assert status_res.status_code == 200
        status_data = status_res.json()
        assert status_data["daily_tokens_used"] == 0
        assert status_data["daily_spend_usd"] == 0.0


@pytest.mark.asyncio
async def test_chat_endpoint_updates_quota_consumption():
    """Verifies that executing chat queries automatically updates tenant quota and spend."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        chat_payload = {
            "query": "What is the dense vector dimension in BGE-M3?",
            "rag_strategy": "Basic",
            "tenant_id": "default_tenant",
            "user_id": "test_user",
        }
        chat_res = await client.post("/api/v1/chat", json=chat_payload)
        assert chat_res.status_code == 200

        # Check quota status reflects usage
        quota_res = await client.get("/api/v1/tenants/default_tenant/quota")
        assert quota_res.status_code == 200
        data = quota_res.json()
        assert data["daily_tokens_used"] > 0
        assert data["daily_spend_usd"] > 0


@pytest.mark.asyncio
async def test_chat_endpoint_budget_exceeded_returns_429():
    """Verifies that when a tenant exceeds daily token/financial budget, HTTP 429 is returned."""
    svc = TenantQuotaService.get_instance()
    # Artificially exhaust restricted_tenant's tiny daily limit ($0.01)
    svc.record_usage("restricted_tenant", prompt_tokens=2000, completion_tokens=2000, cost_usd=0.02)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        chat_payload = {
            "query": "Tell me about RAG architecture.",
            "rag_strategy": "Basic",
            "tenant_id": "restricted_tenant",
            "user_id": "test_user",
        }
        res = await client.post("/api/v1/chat", json=chat_payload)
        assert res.status_code == 429
        assert "exceeded" in res.json()["detail"].lower()
