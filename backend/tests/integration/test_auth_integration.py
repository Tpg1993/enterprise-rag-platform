"""Integration tests for Authentication & RBAC API endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient
from src.api.main import app


@pytest.mark.asyncio
async def test_auth_register_and_login_flow():
    """Tests registration, login, and bearer token retrieval via REST API."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Register new analyst user
        reg_payload = {
            "email": "test_analyst@enterprise.ai",
            "password": "Password123!",
            "full_name": "Integration Analyst",
            "role": "ANALYST",
            "tenant_id": "tenant_test",
            "department": "Security Ops",
        }
        reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
        assert reg_res.status_code == 201
        reg_data = reg_res.json()
        assert reg_data["status"] == "SUCCESS"
        assert reg_data["user"]["role"] == "ANALYST"

        # 2. Login
        login_payload = {
            "email": "test_analyst@enterprise.ai",
            "password": "Password123!",
        }
        login_res = await client.post("/api/v1/auth/login", json=login_payload)
        assert login_res.status_code == 200
        token_data = login_res.json()
        assert "access_token" in token_data
        assert token_data["token_type"] == "bearer"
        token = token_data["access_token"]

        # 3. Access /api/v1/auth/me with Bearer token
        headers = {"Authorization": f"Bearer {token}"}
        me_res = await client.get("/api/v1/auth/me", headers=headers)
        assert me_res.status_code == 200
        me_data = me_res.json()
        assert me_data["role"] == "ANALYST"
        assert me_data["tenant_id"] == "tenant_test"
        assert "upload_documents" in me_data["permissions"]


@pytest.mark.asyncio
async def test_auth_roles_and_directory():
    """Tests RBAC role matrix endpoint and user directory listing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Get role matrix
        roles_res = await client.get("/api/v1/auth/roles")
        assert roles_res.status_code == 200
        roles_data = roles_res.json()
        assert "ADMIN" in roles_data
        assert "ANALYST" in roles_data
        assert "USER" in roles_data
        assert "VIEWER" in roles_data

        # Get directory users
        users_res = await client.get("/api/v1/auth/users")
        assert users_res.status_code == 200
        users_data = users_res.json()
        assert users_data["total_users"] >= 4
