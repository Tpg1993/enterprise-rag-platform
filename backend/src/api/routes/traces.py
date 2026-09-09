"""Traces API router exposing internal execution trace timelines and metadata."""

import logging
from fastapi import APIRouter, Query
from src.observability.tracing import TraceSpan, Tracer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/traces", tags=["Observability & Tracing"])


@router.get("", response_model=list[TraceSpan])
async def get_execution_traces(
    limit: int = Query(default=20, ge=1, le=100),
    tenant_id: str | None = Query(default=None),
) -> list[TraceSpan]:
    """Returns recent execution trace spans matching tenant_id."""
    return Tracer.get_recent_traces(limit=limit, tenant_id=tenant_id)
