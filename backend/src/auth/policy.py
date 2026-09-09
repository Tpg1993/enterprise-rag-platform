"""RBAC/ABAC Policy Engine enforcing least-privilege role permissions and tenant boundaries."""

import logging
from src.auth.models import UserContext, UserRole

logger = logging.getLogger(__name__)

# Permission matrix matching AGENTS.md Section 5
ROLE_PERMISSIONS: dict[UserRole, set[str]] = {
    UserRole.ADMIN: {
        "upload_documents",
        "delete_documents",
        "execute_chat",
        "view_traces",
        "view_system_costs",
        "compare_strategies",
    },
    UserRole.ANALYST: {
        "upload_documents",
        "execute_chat",
        "view_traces",
        "compare_strategies",
    },
    UserRole.USER: {
        "execute_chat",
        "view_documents",
    },
    UserRole.VIEWER: {
        "view_documents",
        "view_dashboards",
    },
}


class PolicyEngine:
    """Enforces fine-grained server-side authorization policies."""

    @staticmethod
    def is_authorized(user: UserContext, action: str) -> bool:
        """Evaluates whether user role grants permission for action."""
        allowed = ROLE_PERMISSIONS.get(user.role, set())
        has_perm = action in allowed or action in user.permissions
        if not has_perm:
            logger.warning(
                f"Unauthorized access attempt! User '{user.user_id}' ({user.role}) denied action '{action}'."
            )
        return has_perm

    @staticmethod
    def enforce_tenant_isolation(user: UserContext, target_tenant_id: str) -> bool:
        """ABAC policy enforcing query-level tenant data isolation."""
        if user.role == UserRole.ADMIN:
            return True
        return user.tenant_id == target_tenant_id
