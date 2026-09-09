"""Authentication and JWT Token Service with PBKDF2 Password Hashing and RBAC Context."""

import hashlib
import logging
import os
import secrets
import time
from typing import Any

import jwt
from pydantic import BaseModel, EmailStr, Field
from src.auth.models import UserContext, UserRole
from src.auth.policy import ROLE_PERMISSIONS

logger = logging.getLogger(__name__)

JWT_SECRET = os.getenv("JWT_SECRET_KEY", "super-secret-enterprise-jwt-key-2026-prod")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_SECONDS = 3600 * 24  # 24 hours


class UserRecord(BaseModel):
    user_id: str
    email: str
    full_name: str
    role: UserRole
    tenant_id: str = "default_tenant"
    department: str = "Engineering"
    security_clearance: str = "Internal"
    password_hash: str
    is_active: bool = True
    created_at: float = Field(default_factory=time.time)


class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str
    role: UserRole = UserRole.USER
    tenant_id: str = "default_tenant"
    department: str = "Operations"
    security_clearance: str = "Internal"


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict[str, Any]


def hash_password(password: str) -> str:
    """Generates a PBKDF2-HMAC-SHA256 salted hash for password storage."""
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100_000,
    )
    return f"{salt}:{key.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against stored salt:hash string."""
    try:
        salt, expected_hash = hashed_password.split(":", 1)
        key = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt.encode("utf-8"),
            100_000,
        )
        return secrets.compare_digest(key.hex(), expected_hash)
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False


class AuthService:
    """Authentication and User Management Service."""

    def __init__(self) -> None:
        self._users: dict[str, UserRecord] = {}
        self._init_default_users()

    def _init_default_users(self) -> None:
        """Seeds enterprise role users defined in AGENTS.md."""
        seed_accounts = [
            ("usr_admin", "admin@enterprise.ai", "Admin Administrator", UserRole.ADMIN, "Executive", "TopSecret"),
            ("usr_analyst", "analyst@enterprise.ai", "Security Analyst", UserRole.ANALYST, "Analytics", "Confidential"),
            ("usr_user", "user@enterprise.ai", "Knowledge Worker", UserRole.USER, "Engineering", "Internal"),
            ("usr_viewer", "viewer@enterprise.ai", "Audit Viewer", UserRole.VIEWER, "Compliance", "Public"),
        ]
        default_pw = "Password123!"
        for uid, email, name, role, dept, clearance in seed_accounts:
            self._users[email.lower()] = UserRecord(
                user_id=uid,
                email=email.lower(),
                full_name=name,
                role=role,
                tenant_id="default_tenant",
                department=dept,
                security_clearance=clearance,
                password_hash=hash_password(default_pw),
            )

    def register_user(self, req: RegisterRequest) -> UserRecord:
        """Registers a new user in the platform directory."""
        email_key = req.email.strip().lower()
        if email_key in self._users:
            raise ValueError(f"User with email '{req.email}' already exists.")

        user_id = f"usr_{secrets.token_hex(6)}"
        record = UserRecord(
            user_id=user_id,
            email=email_key,
            full_name=req.full_name,
            role=req.role,
            tenant_id=req.tenant_id,
            department=req.department,
            security_clearance=req.security_clearance,
            password_hash=hash_password(req.password),
        )
        self._users[email_key] = record
        logger.info(f"Registered user '{record.email}' with role {record.role} for tenant {record.tenant_id}.")
        return record

    def authenticate_user(self, req: LoginRequest) -> TokenResponse:
        """Authenticates user credentials and returns signed JWT token."""
        email_key = req.email.strip().lower()
        user = self._users.get(email_key)
        if not user or not verify_password(req.password, user.password_hash):
            raise ValueError("Invalid email or password.")

        if not user.is_active:
            raise ValueError("User account is inactive.")

        user_context = UserContext(
            user_id=user.user_id,
            role=user.role,
            tenant_id=user.tenant_id,
            department=user.department,
            security_clearance=user.security_clearance,
            permissions=list(ROLE_PERMISSIONS.get(user.role, set())),
        )

        token = self.create_access_token(user_context)
        return TokenResponse(
            access_token=token,
            expires_in=JWT_EXPIRATION_SECONDS,
            user={
                "user_id": user.user_id,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role.value,
                "tenant_id": user.tenant_id,
                "department": user.department,
                "permissions": user_context.permissions,
            },
        )

    def create_access_token(
        self, user: UserContext, expires_delta_seconds: int = JWT_EXPIRATION_SECONDS
    ) -> str:
        """Encodes UserContext into a cryptographically signed JWT token."""
        now = time.time()
        payload = {
            "sub": user.user_id,
            "role": user.role.value,
            "tenant_id": user.tenant_id,
            "department": user.department,
            "security_clearance": user.security_clearance,
            "permissions": user.permissions,
            "iat": int(now),
            "exp": int(now + expires_delta_seconds),
        }
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    def decode_access_token(self, token: str) -> UserContext:
        """Decodes and verifies signed JWT token into UserContext."""
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            return UserContext(
                user_id=payload.get("sub", "usr_anonymous"),
                role=UserRole(payload.get("role", UserRole.USER.value)),
                tenant_id=payload.get("tenant_id", "default_tenant"),
                department=payload.get("department"),
                security_clearance=payload.get("security_clearance", "Internal"),
                permissions=payload.get("permissions", []),
            )
        except jwt.ExpiredSignatureError:
            raise ValueError("Access token has expired. Please log in again.")
        except jwt.PyJWTError as e:
            raise ValueError(f"Invalid access token: {e}")

    def get_user_by_id(self, user_id: str) -> UserRecord | None:
        for record in self._users.values():
            if record.user_id == user_id:
                return record
        return None

    def list_users(self) -> list[UserRecord]:
        return list(self._users.values())


# Global singleton
_auth_service = AuthService()


def get_auth_service() -> AuthService:
    """Returns global AuthService singleton."""
    return _auth_service
