"""Integration tests for Dynamic Tools and OpenAPI Ingestion REST endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient
from src.api.main import app


@pytest.mark.asyncio
async def test_get_tools_endpoint():
    """Verifies that GET /api/v1/tools lists all registered tools."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/tools")
        assert res.status_code == 200
        tools = res.json()
        assert isinstance(tools, list)
        assert len(tools) >= 5
        names = [t["name"] for t in tools]
        assert "calculate" in names
        assert "calculate_sla_penalty" in names
        assert "get_system_time" in names
        assert "query_service_catalog" in names
        assert "unit_converter" in names


@pytest.mark.asyncio
async def test_execute_tool_endpoint_success():
    """Verifies POST /api/v1/tools/execute executes a tool synchronously."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "tool_name": "calculate",
            "arguments": {"expression": "100 * 5 + 25"},
        }
        res = await client.post("/api/v1/tools/execute", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["tool_name"] == "calculate"
        assert data["success"] is True
        assert data["result"]["result"] == 525
        assert data["latency_ms"] >= 0.0


@pytest.mark.asyncio
async def test_execute_tool_endpoint_not_found():
    """Verifies POST /api/v1/tools/execute returns 404 for unknown tool."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "tool_name": "non_existent_tool_123",
            "arguments": {},
        }
        res = await client.post("/api/v1/tools/execute", json=payload)
        assert res.status_code == 404
        assert "not found" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_import_openapi_spec_endpoint():
    """Verifies POST /api/v1/tools/import-openapi ingests Swagger/OpenAPI specs."""
    spec_yaml = """
openapi: 3.0.0
info:
  title: Microservice Ops API
  version: 1.0.0
paths:
  /system/metrics:
    get:
      summary: Retrieve cluster health metrics
      operationId: get_cluster_metrics
      parameters:
        - name: cluster_id
          in: query
          required: true
          schema:
            type: string
"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "spec_content": spec_yaml,
            "tag": "cluster_ops",
            "base_url": "https://ops.internal.enterprise.com",
        }
        res = await client.post("/api/v1/tools/import-openapi", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["imported_count"] >= 1
        assert "get_cluster_metrics" in data["tools_registered"]

        # Confirm tool appears in GET /api/v1/tools
        get_res = await client.get("/api/v1/tools")
        assert get_res.status_code == 200
        all_tools = [t["name"] for t in get_res.json()]
        assert "get_cluster_metrics" in all_tools
