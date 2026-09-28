"""Audit Trail API router exposing system and security audit logs."""

import logging

from fastapi import APIRouter, Query
from src.api.schemas import AuditEvent, AuditEventsResponse
from src.storage.history import get_history_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/audit", tags=["Security & Governance"])


@router.get("", response_model=AuditEventsResponse)
async def get_audit_trail(
    limit: int = Query(default=50, ge=1, le=200),
    tenant_id: str | None = Query(default=None),
) -> AuditEventsResponse:
    """Returns security, access, and pipeline audit events filtered by tenant_id."""
    store = get_history_store()
    raw_events = store.get_audit_events(tenant_id=tenant_id, limit=limit)
    events = [AuditEvent(**r) for r in raw_events]
    return AuditEventsResponse(total_events=len(events), events=events)
