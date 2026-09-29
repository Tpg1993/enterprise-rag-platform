"""API endpoints for Tenant Quota, Rate Limiting, and Financial Budget Management."""

import logging

from fastapi import APIRouter, HTTPException, Path
from src.security.quotas import TenantQuotaService, TenantQuotaStatus

logger = logging.getLogger("QuotaRouter")

router = APIRouter(prefix="/tenants", tags=["Tenants & Quotas"])


@router.get(
    "/{tenant_id}/quota",
    response_model=TenantQuotaStatus,
    summary="Get tenant quota, rate limit, and budget status",
)
async def get_tenant_quota(
    tenant_id: str = Path(..., description="Tenant identifier to inspect"),
) -> TenantQuotaStatus:
    """Returns live token consumption, rate limit status, and daily/monthly budget metrics."""
    service = TenantQuotaService.get_instance()
    try:
        return service.get_quota_status(tenant_id)
    except Exception as e:
        logger.error(f"Error retrieving quota status for tenant '{tenant_id}': {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post(
    "/{tenant_id}/quota/reset",
    summary="Reset quota and budget consumption for a tenant",
)
async def reset_tenant_quota(
    tenant_id: str = Path(..., description="Tenant identifier to reset"),
) -> dict[str, str]:
    """Resets daily and monthly token and dollar budget counters for a tenant."""
    service = TenantQuotaService.get_instance()
    try:
        service.reset_tenant_usage(tenant_id)
        return {"status": "success", "message": f"Quota reset for tenant '{tenant_id}'."}
    except Exception as e:
        logger.error(f"Error resetting quota for tenant '{tenant_id}': {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
