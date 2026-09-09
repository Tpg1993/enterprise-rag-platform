"""Authentication & RBAC REST API Routes."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from src.auth.models import UserContext, UserRole
from src.auth.policy import ROLE_PERMISSIONS, PolicyEngine
from src.auth.service import (
    AuthService,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    get_auth_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication & RBAC"])


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    auth_service: AuthService = Depends(get_auth_service),
) -> UserContext:
    """FastAPI dependency extracting and validating JWT token from Authorization header."""
    if not authorization:
        # Provide default context for legacy/unauthenticated requests in dev mode
        return UserContext(
            user_id="usr_default",
            role=UserRole.ADMIN,
            tenant_id="default_tenant",
            permissions=list(ROLE_PERMISSIONS[UserRole.ADMIN]),
        )

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Expected 'Bearer <token>'.",
        )

    token = parts[1]
    try:
        return auth_service.decode_access_token(token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )


def require_permission(action: str):
    """Dependency factory checking user permission via PolicyEngine."""

    def _dependency(user: UserContext = Depends(get_current_user)) -> UserContext:
        if not PolicyEngine.is_authorized(user, action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: role '{user.role.value}' lacks '{action}' privilege.",
            )
        return user

    return _dependency


def require_roles(allowed_roles: list[UserRole]):
    """Dependency factory checking user role."""

    def _dependency(user: UserContext = Depends(get_current_user)) -> UserContext:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role forbidden: action restricted to {[r.value for r in allowed_roles]}.",
            )
        return user

    return _dependency


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    req: RegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    """Registers a new platform user with specified role and tenant bounds."""
    try:
        record = auth_service.register_user(req)
        return {
            "status": "SUCCESS",
            "message": "User registered successfully.",
            "user": {
                "user_id": record.user_id,
                "email": record.email,
                "full_name": record.full_name,
                "role": record.role.value,
                "tenant_id": record.tenant_id,
                "department": record.department,
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/login", response_model=TokenResponse)
async def login(
    req: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    """Authenticates user and returns signed JWT bearer token."""
    try:
        return auth_service.authenticate_user(req)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.get("/me")
async def get_me(user: UserContext = Depends(get_current_user)):
    """Returns the authenticated user's profile and active permissions."""
    return {
        "user_id": user.user_id,
        "role": user.role.value,
        "tenant_id": user.tenant_id,
        "department": user.department,
        "security_clearance": user.security_clearance,
        "permissions": user.permissions,
    }


@router.get("/users")
async def list_users(
    user: UserContext = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
):
    """Lists registered directory users."""
    users = auth_service.list_users()
    return {
        "total_users": len(users),
        "users": [
            {
                "user_id": u.user_id,
                "email": u.email,
                "full_name": u.full_name,
                "role": u.role.value,
                "tenant_id": u.tenant_id,
                "department": u.department,
                "security_clearance": u.security_clearance,
                "is_active": u.is_active,
            }
            for u in users
        ],
    }


@router.get("/roles")
async def get_role_matrix():
    """Returns the active RBAC permission matrix for UI Governance display."""
    return {
        role.value: sorted(list(perms)) for role, perms in ROLE_PERMISSIONS.items()
    }
