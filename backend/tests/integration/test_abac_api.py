"""Integration tests for Multi-Level ABAC Security & Redaction REST endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient
from src.api.main import app


@pytest.mark.asyncio
async def test_get_abac_policies_endpoint():
    """Verifies that GET /api/v1/security/abac-policies returns active policy matrix."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/security/abac-policies")
        assert res.status_code == 200
        data = res.json()
        assert "clearance_hierarchy" in data
        assert data["clearance_hierarchy"]["ADMIN"] == 4
        assert data["clearance_hierarchy"]["VIEWER"] == 1
        assert "CONFIDENTIAL" in data["classification_rules"]
        assert len(data["differential_privacy_rules"]) >= 3


@pytest.mark.asyncio
async def test_simulate_abac_endpoint_user_redaction():
    """Verifies POST /api/v1/security/simulate-abac redacts confidential figures for USER."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "text": "The contract base compensation is $450,000 annually.",
            "user_role": "USER",
            "classification": "CONFIDENTIAL",
        }
        res = await client.post("/api/v1/security/simulate-abac", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["has_redactions"] is True
        assert data["user_role"] == "USER"
        assert data["clearance_level"] == 2
        assert "$450,000" not in data["masked_text"]
        assert "[REDACTED:" in data["masked_text"]


@pytest.mark.asyncio
async def test_simulate_abac_endpoint_admin_bypass():
    """Verifies POST /api/v1/security/simulate-abac preserves raw fidelity for ADMIN."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        text = (
            "The contract base compensation is $450,000 annually with sk-live-secret-key-123456789."
        )
        payload = {
            "text": text,
            "user_role": "ADMIN",
            "classification": "SECRET",
        }
        res = await client.post("/api/v1/security/simulate-abac", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["has_redactions"] is False
        assert data["masked_text"] == text
        assert data["user_role"] == "ADMIN"
        assert data["clearance_level"] == 4


@pytest.mark.asyncio
async def test_simulate_abac_endpoint_viewer_full_redaction():
    """Verifies POST /api/v1/security/simulate-abac full chunk redaction for VIEWER."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "text": "Critical internal architectural diagrams.",
            "user_role": "VIEWER",
            "classification": "SECRET",
        }
        res = await client.post("/api/v1/security/simulate-abac", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["has_redactions"] is True
        assert "[REDACTED: CLEARANCE_REQUIRED" in data["masked_text"]
        assert "Critical internal" not in data["masked_text"]
