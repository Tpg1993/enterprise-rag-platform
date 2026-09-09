"""Unit test suite for Phase 22 User Authentication, JWT, and RBAC/ABAC Policies."""

import pytest
from src.auth.models import UserContext, UserRole
from src.auth.policy import PolicyEngine
from src.auth.service import (
    AuthService,
    LoginRequest,
    RegisterRequest,
    hash_password,
    verify_password,
)


def test_password_hashing():
    """Verifies that PBKDF2 salt and hash generation verifies correctly."""
    pw = "SuperSecurePassword123!"
    h = hash_password(pw)
    assert ":" in h
    assert verify_password(pw, h) is True
    assert verify_password("WrongPassword", h) is False


def test_auth_service_registration():
    """Verifies user registration in directory."""
    service = AuthService()
    req = RegisterRequest(
        email="test_dev@enterprise.ai",
        password="DevPassword456!",
        full_name="Developer One",
        role=UserRole.USER,
        tenant_id="tenant_engineering",
    )
    user = service.register_user(req)
    assert user.email == "test_dev@enterprise.ai"
    assert user.role == UserRole.USER
    assert user.tenant_id == "tenant_engineering"

    # Duplicate registration should raise ValueError
    with pytest.raises(ValueError):
        service.register_user(req)


def test_auth_service_login_and_jwt():
    """Verifies login, token generation, and JWT decoding."""
    service = AuthService()
    login_req = LoginRequest(
        email="admin@enterprise.ai",
        password="Password123!",
    )
    token_res = service.authenticate_user(login_req)
    assert token_res.access_token is not None
    assert token_res.token_type == "bearer"
    assert token_res.user["role"] == "ADMIN"

    # Decode and verify context
    user_context = service.decode_access_token(token_res.access_token)
    assert user_context.role == UserRole.ADMIN
    assert user_context.tenant_id == "default_tenant"
    assert "upload_documents" in user_context.permissions
    assert "delete_documents" in user_context.permissions


def test_auth_service_login_invalid_password():
    """Verifies rejection of invalid password."""
    service = AuthService()
    req = LoginRequest(email="admin@enterprise.ai", password="WrongPassword!")
    with pytest.raises(ValueError, match="Invalid email or password"):
        service.authenticate_user(req)


def test_policy_engine_rbac_matrix():
    """Verifies RBAC permission matrix for all 4 roles."""
    admin = UserContext(role=UserRole.ADMIN)
    analyst = UserContext(role=UserRole.ANALYST)
    user = UserContext(role=UserRole.USER)
    viewer = UserContext(role=UserRole.VIEWER)

    # Admin has upload, delete, chat, traces, compare
    assert PolicyEngine.is_authorized(admin, "upload_documents") is True
    assert PolicyEngine.is_authorized(admin, "delete_documents") is True
    assert PolicyEngine.is_authorized(admin, "execute_chat") is True

    # Analyst can upload, chat, compare, view traces, but not delete
    assert PolicyEngine.is_authorized(analyst, "upload_documents") is True
    assert PolicyEngine.is_authorized(analyst, "delete_documents") is False
    assert PolicyEngine.is_authorized(analyst, "execute_chat") is True

    # User can execute chat, view documents, but not upload or view traces
    assert PolicyEngine.is_authorized(user, "execute_chat") is True
    assert PolicyEngine.is_authorized(user, "upload_documents") is False
    assert PolicyEngine.is_authorized(user, "view_traces") is False

    # Viewer cannot upload or execute chat, only view dashboards
    assert PolicyEngine.is_authorized(viewer, "view_dashboards") is True
    assert PolicyEngine.is_authorized(viewer, "execute_chat") is False
    assert PolicyEngine.is_authorized(viewer, "upload_documents") is False


def test_policy_engine_tenant_isolation():
    """Verifies ABAC tenant boundary rules."""
    user = UserContext(role=UserRole.USER, tenant_id="tenant_alpha")
    admin = UserContext(role=UserRole.ADMIN, tenant_id="tenant_admin")

    # Regular user can only access their own tenant
    assert PolicyEngine.enforce_tenant_isolation(user, "tenant_alpha") is True
    assert PolicyEngine.enforce_tenant_isolation(user, "tenant_beta") is False

    # Admin has cross-tenant access privilege
    assert PolicyEngine.enforce_tenant_isolation(admin, "tenant_alpha") is True
    assert PolicyEngine.enforce_tenant_isolation(admin, "tenant_beta") is True
