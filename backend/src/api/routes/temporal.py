"""REST API endpoints for Temporal-Aware Time-Travel RAG & Version Diff Retrieval."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from src.retrieval.temporal import (
    DocumentVersionEntry,
    TemporalFilter,
    VersionDiffResult,
    get_diff_synthesizer,
    get_temporal_parser,
    get_timeline_registry,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/temporal", tags=["Temporal RAG & Version Diff"])


class TemporalParseRequest(BaseModel):
    """Request payload to parse natural language temporal expressions."""

    query: str = Field(..., description="Query containing temporal terms or dates")
    default_as_of: str | None = Field(default=None, description="Fallback as_of date YYYY-MM-DD")
    default_mode: str | None = Field(default=None, description="Fallback temporal mode")


class TemporalParseResponse(BaseModel):
    """Structured response from temporal query parsing."""

    original_query: str
    cleaned_query: str
    temporal_filter: TemporalFilter
    has_temporal_intent: bool


class VersionDiffRequest(BaseModel):
    """Request to compute side-by-side difference between document versions or points in time."""

    document_id: str | None = Field(
        default=None, description="Target document ID to diff versions of"
    )
    version_a: str | None = Field(default=None, description="Base/source revision (e.g. 1.0)")
    version_b: str | None = Field(default=None, description="Target revision (e.g. 2.0)")
    as_of_a: str | None = Field(
        default=None, description="Snapshot date A for time-travel comparison"
    )
    as_of_b: str | None = Field(
        default=None, description="Snapshot date B for time-travel comparison"
    )
    raw_text_a: str | None = Field(
        default=None, description="Optional raw text for version A"
    )
    raw_text_b: str | None = Field(
        default=None, description="Optional raw text for version B"
    )
    tenant_id: str = Field(default="default_tenant", description="Tenant identifier")


@router.post("/parse", response_model=TemporalParseResponse)
async def parse_temporal_query(payload: TemporalParseRequest) -> TemporalParseResponse:
    """Extracts date bounds, quarters, and version tags from natural language queries."""
    parser = get_temporal_parser()
    cleaned_query, temporal_filter = parser.parse(
        query=payload.query,
        default_as_of=payload.default_as_of,
        default_mode=payload.default_mode,
    )
    has_intent = (
        bool(temporal_filter.as_of_date)
        or bool(temporal_filter.start_date)
        or bool(temporal_filter.target_version)
        or len(temporal_filter.extracted_expressions) > 0
    )
    return TemporalParseResponse(
        original_query=payload.query,
        cleaned_query=cleaned_query,
        temporal_filter=temporal_filter,
        has_temporal_intent=has_intent,
    )


@router.get("/timeline", response_model=list[DocumentVersionEntry])
async def get_document_timeline(
    document_id: str | None = Query(default=None, description="Optional document ID filter"),
    tenant_id: str = Query(default="default_tenant", description="Tenant ID filter"),
) -> list[DocumentVersionEntry]:
    """Retrieves chronological version history for documents, revisions, and amendments."""
    registry = get_timeline_registry()
    return registry.get_timeline(document_id=document_id, tenant_id=tenant_id)


@router.post("/diff", response_model=VersionDiffResult)
async def compute_version_diff(payload: VersionDiffRequest) -> VersionDiffResult:
    """Computes side-by-side or line-level revision diff between two document versions."""
    registry = get_timeline_registry()
    synthesizer = get_diff_synthesizer()

    # Case 1: Raw text diff provided explicitly
    if payload.raw_text_a is not None and payload.raw_text_b is not None:
        label_a = f"Version {payload.version_a or 'A'}"
        label_b = f"Version {payload.version_b or 'B'}"
        return synthesizer.synthesize_diff(payload.raw_text_a, payload.raw_text_b, label_a, label_b)

    # Case 2: Document ID and version strings provided
    if payload.document_id:
        v_a = registry.get_version(payload.document_id, payload.version_a or "1.0")
        v_b = registry.get_version(payload.document_id, payload.version_b or "2.0")

        text_a = (
            v_a.summary + "\n\nKey Provisions: " + v_a.change_description
            if v_a
            else f"Document {payload.document_id} baseline revision {payload.version_a}."
        )
        text_b = (
            v_b.summary + "\n\nKey Provisions: " + v_b.change_description
            if v_b
            else f"Document {payload.document_id} amended revision {payload.version_b}."
        )
        label_a = f"{payload.document_id} (v{payload.version_a or '1.0'})"
        label_b = f"{payload.document_id} (v{payload.version_b or '2.0'})"
        return synthesizer.synthesize_diff(text_a, text_b, label_a, label_b)

    # Case 3: Point-in-time diff (e.g. As of 2023 vs As of 2025)
    date_a = payload.as_of_a or "2023-01-01"
    date_b = payload.as_of_b or "2025-01-01"

    timelines = registry.get_timeline(tenant_id=payload.tenant_id)
    active_at_a = [e for e in timelines if e.effective_from <= date_a <= e.effective_until]
    active_at_b = [e for e in timelines if e.effective_from <= date_b <= e.effective_until]

    text_a = "\n".join(f"- {e.filename} v{e.version}: {e.summary}" for e in active_at_a)
    text_b = "\n".join(f"- {e.filename} v{e.version}: {e.summary}" for e in active_at_b)

    label_a = f"Knowledge State as of {date_a}"
    label_b = f"Knowledge State as of {date_b}"
    return synthesizer.synthesize_diff(text_a, text_b, label_a, label_b)
