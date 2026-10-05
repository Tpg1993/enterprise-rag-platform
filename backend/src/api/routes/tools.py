"""REST API routes for the Dynamic Tool Registry and OpenAPI function calling."""

import logging

from fastapi import APIRouter, HTTPException, Query
from src.agents.tools.models import (
    OpenAPISpecImportRequest,
    OpenAPISpecImportResponse,
    ToolDefinition,
    ToolExecutionRequest,
    ToolExecutionResult,
)
from src.agents.tools.registry import get_tool_registry
from src.storage.history import get_history_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tools", tags=["Tools"])


@router.get("", response_model=list[ToolDefinition])
async def list_registered_tools(
    category: str | None = Query(None, description="Optional category filter"),
) -> list[ToolDefinition]:
    """Returns catalog of all registered tools with parameter schemas and bounds."""
    registry = get_tool_registry()
    return registry.list_tools(category=category)


@router.post("/execute", response_model=ToolExecutionResult)
async def execute_tool(payload: ToolExecutionRequest) -> ToolExecutionResult:
    """Executes a registered tool in a sandboxed runtime with parameter validation."""
    registry = get_tool_registry()
    if not registry.get_tool(payload.tool_name):
        raise HTTPException(
            status_code=404,
            detail=f"Tool '{payload.tool_name}' not found in registry",
        )
    result = await registry.aexecute_tool(payload.tool_name, payload.arguments)

    get_history_store().record_audit_event(
        event_type="TOOL_EXECUTION",
        user_id="analyst",
        tenant_id="default_tenant",
        action="TOOL_CALL",
        resource=f"tool:{payload.tool_name}",
        status="SUCCESS" if result.success else "FAILED",
        details={
            "tool_name": payload.tool_name,
            "success": result.success,
            "latency_ms": result.latency_ms,
            "error": result.error,
        },
    )

    return result


@router.post("/import-openapi", response_model=OpenAPISpecImportResponse)
async def import_openapi_specification(
    payload: OpenAPISpecImportRequest,
) -> OpenAPISpecImportResponse:
    """Parses an OpenAPI 3.0 / Swagger document and dynamically registers endpoint tools."""
    registry = get_tool_registry()
    try:
        import_resp = registry.import_openapi_spec(spec=payload)

        get_history_store().record_audit_event(
            event_type="OPENAPI_IMPORT",
            user_id="admin",
            tenant_id="default_tenant",
            action="IMPORT",
            resource="openapi_spec",
            status="SUCCESS",
            details={
                "imported_count": import_resp.imported_count,
                "tools": import_resp.tools_imported,
            },
        )

        return import_resp
    except Exception as e:
        logger.error(f"Failed to import OpenAPI spec: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to import OpenAPI spec: {e!s}")
