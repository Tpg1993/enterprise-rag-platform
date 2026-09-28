"""Traces API router exposing internal execution trace timelines and metadata."""

import logging

from fastapi import APIRouter, HTTPException, Query
from src.observability.tracing import Tracer, TraceSpan

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/traces", tags=["Observability & Tracing"])


@router.get("", response_model=list[TraceSpan])
async def get_execution_traces(
    limit: int = Query(default=20, ge=1, le=100),
    tenant_id: str | None = Query(default=None),
) -> list[TraceSpan]:
    """Returns recent execution trace spans matching tenant_id."""
    return Tracer.get_recent_traces(limit=limit, tenant_id=tenant_id)


@router.get("/{trace_id}", response_model=TraceSpan)
async def get_trace_by_id(trace_id: str) -> TraceSpan:
    """Returns single execution trace span by trace_id."""
    span = Tracer.get_trace_by_id(trace_id)
    if not span:
        raise HTTPException(status_code=404, detail=f"Trace '{trace_id}' not found")
    return span

