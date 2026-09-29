"""Document Comparison API routes for Multi-Document Comparative Matrix & Delta Synthesis."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from src.api.schemas import DocumentCompareRequest, DocumentCompareResponse
from src.rag.comparative.comparator import get_document_comparator
from src.storage.history import get_history_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents/compare", tags=["Document Comparisons"])


@router.post("", response_model=DocumentCompareResponse)
async def compare_documents(payload: DocumentCompareRequest) -> DocumentCompareResponse:
    """Performs multi-document partitioned retrieval, alignment, and delta matrix synthesis."""
    if len(payload.document_ids) < 2:
        raise HTTPException(
            status_code=400,
            detail="Comparative synthesis requires at least 2 distinct document IDs.",
        )

    comparator = get_document_comparator()
    try:
        result = await comparator.compare_documents(
            document_ids=payload.document_ids,
            query=payload.query,
            tenant_id=payload.tenant_id,
            focus_areas=payload.focus_areas,
        )

        # Persist comparison outcome in historical audit store
        try:
            history_store = get_history_store()
            history_store.save_document_comparison(result.model_dump())
        except Exception as store_err:
            logger.warning(f"Failed to persist comparison in history store: {store_err}")

        return DocumentCompareResponse(
            comparison_id=result.comparison_id,
            tenant_id=result.tenant_id,
            document_ids=result.document_ids,
            document_titles=result.document_titles,
            query=result.query,
            overall_summary=result.overall_summary,
            matrix_markdown=result.matrix_markdown,
            risk_assessment=result.risk_assessment,
            dimensions=[dim.model_dump() for dim in result.dimensions],
            created_at=result.created_at,
            latency_ms=result.latency_ms,
            metadata=result.metadata,
        )
    except Exception as exc:
        logger.error(f"Error executing multi-document comparison: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/history")
async def list_comparison_history(
    tenant_id: str = Query(default="default_tenant", description="Tenant identifier"),
    limit: int = Query(default=20, ge=1, le=100, description="Max history records to return"),
) -> dict[str, Any]:
    """Returns historical multi-document comparison records for the specified tenant."""
    history_store = get_history_store()
    comparisons = history_store.list_document_comparisons(tenant_id=tenant_id, limit=limit)
    return {
        "tenant_id": tenant_id,
        "total_comparisons": len(comparisons),
        "comparisons": comparisons,
    }


@router.get("/{comparison_id}", response_model=DocumentCompareResponse)
async def get_comparison_by_id(comparison_id: str) -> DocumentCompareResponse:
    """Retrieves an existing multi-document comparison record by ID."""
    history_store = get_history_store()
    rec = history_store.get_document_comparison_by_id(comparison_id)
    if not rec:
        raise HTTPException(status_code=404, detail=f"Comparison '{comparison_id}' not found.")

    return DocumentCompareResponse(
        comparison_id=rec["comparison_id"],
        tenant_id=rec["tenant_id"],
        document_ids=rec["document_ids"],
        document_titles=rec["document_titles"],
        query=rec["query"],
        overall_summary=rec["overall_summary"],
        matrix_markdown=rec["matrix_markdown"],
        risk_assessment=rec["risk_assessment"],
        dimensions=rec["dimensions"],
        created_at=rec["created_at"],
        latency_ms=rec["latency_ms"],
    )
