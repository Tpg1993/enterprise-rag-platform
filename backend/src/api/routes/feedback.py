"""Active User Feedback & Continuous Retrieval Fine-Tuning API (Phase 36).

Captures explicit user thumbs up / down feedback, calculates retrieval boost
multipliers on cited chunks, and exposes continuous tuning analytics.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from src.storage.history import get_history_store

logger = logging.getLogger("FeedbackAPI")

router = APIRouter(tags=["Feedback & Continuous Fine-Tuning"])


class FeedbackSubmitRequest(BaseModel):
    """Payload for submitting thumbs up / down user feedback on assistant answers."""

    user_id: str = "default_user"
    tenant_id: str = "default_tenant"
    rating: int = Field(..., description="+1 for thumbs up, -1 for thumbs down")
    message_id: str | None = None
    session_id: str | None = None
    query: str | None = None
    response_snippet: str | None = None
    category: str = "general"
    comment: str | None = None
    chunk_ids: list[str] = Field(default_factory=list)


class FeedbackResponse(BaseModel):
    """Result of recorded user feedback."""

    status: str = "SUCCESS"
    feedback_id: str
    tenant_id: str
    rating: int
    category: str
    boost_applied_to_chunks: list[dict[str, Any]] = Field(default_factory=list)


@router.post("/chat/feedback", response_model=FeedbackResponse)
async def submit_feedback(payload: FeedbackSubmitRequest):
    """Records explicit user feedback and recalculates retrieval boost multipliers."""
    if payload.rating not in [1, -1]:
        raise HTTPException(
            status_code=400,
            detail="Rating must be +1 (thumbs up) or -1 (thumbs down)",
        )

    store = get_history_store()
    record = store.record_feedback(
        user_id=payload.user_id,
        tenant_id=payload.tenant_id,
        rating=payload.rating,
        message_id=payload.message_id,
        session_id=payload.session_id,
        query=payload.query,
        response_snippet=payload.response_snippet,
        category=payload.category,
        comment=payload.comment,
        chunk_ids=payload.chunk_ids,
    )

    # Calculate updated boost factor for each cited chunk
    boosts = []
    for cid in payload.chunk_ids:
        boost_factor = store.get_chunk_boost_factor(cid, payload.tenant_id)
        boosts.append({"chunk_id": cid, "new_boost_factor": boost_factor})

    return FeedbackResponse(
        status="SUCCESS",
        feedback_id=record["feedback_id"],
        tenant_id=payload.tenant_id,
        rating=record["rating"],
        category=record["category"] or "general",
        boost_applied_to_chunks=boosts,
    )


@router.get("/chat/feedback/analytics")
async def get_feedback_analytics(
    tenant_id: str = Query("default_tenant", description="Tenant ID to filter analytics"),
):
    """Returns aggregated satisfaction metrics, category counts, and top praised/flagged chunks."""
    store = get_history_store()
    analytics = store.get_feedback_analytics(tenant_id=tenant_id)
    return analytics


@router.get("/chat/feedback/history")
async def list_feedback_history(
    tenant_id: str = Query("default_tenant", description="Tenant ID to filter history"),
    limit: int = Query(50, ge=1, le=200),
):
    """Lists historical user feedback entries for compliance and auditability."""
    store = get_history_store()
    items = store.list_feedback(tenant_id=tenant_id, limit=limit)
    return {
        "tenant_id": tenant_id,
        "total": len(items),
        "feedback": items,
    }


@router.get("/chat/feedback/boost/{chunk_id}")
async def get_chunk_boost(
    chunk_id: str,
    tenant_id: str = Query("default_tenant", description="Tenant ID"),
):
    """Returns current retrieval boost multiplier for a specific chunk."""
    store = get_history_store()
    factor = store.get_chunk_boost_factor(chunk_id, tenant_id=tenant_id)
    return {
        "chunk_id": chunk_id,
        "tenant_id": tenant_id,
        "boost_factor": factor,
        "status": "BOOSTED" if factor > 1.0 else ("PENALIZED" if factor < 1.0 else "NEUTRAL"),
    }
