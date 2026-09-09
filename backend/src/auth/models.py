"""Role-Based (RBAC) and Attribute-Based (ABAC) Access Control Data Models."""

from enum import Enum
from pydantic import BaseModel, Field


class UserRole(str, Enum):
    """Platform RBAC user roles."""

    ADMIN = "ADMIN"
    ANALYST = "ANALYST"
    USER = "USER"
    VIEWER = "VIEWER"


class UserContext(BaseModel):
    """Authentication and tenant context passed with API requests."""

    user_id: str = "usr_default"
    role: UserRole = UserRole.USER
    tenant_id: str = "tenant_default"
    department: str | None = None
    security_clearance: str = "Internal"
    permissions: list[str] = Field(default_factory=list)
