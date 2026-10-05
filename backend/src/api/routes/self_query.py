"""API endpoints for autonomous self-querying and metadata filter synthesis."""

import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field
from src.retrieval.self_query import (
    DEFAULT_METADATA_CATALOG,
    MetadataFieldSchema,
    ParsedSelfQuery,
    get_self_query_compiler,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/retrieval/self-query", tags=["Self-Query Retrieval"])


class SelfQueryParseRequest(BaseModel):
    """Payload for self-query parsing and filter compilation."""

    query: str = Field(..., description="Natural language query containing metadata constraints")


@router.post("/parse", response_model=ParsedSelfQuery)
async def parse_self_query(payload: SelfQueryParseRequest) -> ParsedSelfQuery:
    """Deconstructs user query into clean semantic text and structured Qdrant filters."""
    compiler = get_self_query_compiler()
    return compiler.compile(payload.query)


@router.get("/schema", response_model=list[MetadataFieldSchema])
async def get_self_query_schema() -> list[MetadataFieldSchema]:
    """Returns the catalog of filterable metadata attributes."""
    compiler = get_self_query_compiler()
    return compiler.catalog or DEFAULT_METADATA_CATALOG
