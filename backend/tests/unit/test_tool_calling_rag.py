"""Unit tests for Dynamic Tool Registry, Builtin Tools, and Tool-Calling Agentic RAG."""

import pytest
from src.agents.tools.models import (
    OpenAPISpecImportRequest,
)
from src.agents.tools.registry import DynamicToolRegistry
from src.rag.tool_calling.strategy import ToolCallingAgenticRAGStrategy


@pytest.fixture
def clean_registry():
    """Provides an isolated clean registry for unit testing."""
    return DynamicToolRegistry()


def test_builtin_tool_registration(clean_registry):
    """Verifies that default builtin tools are registered upon initialization."""
    tools = clean_registry.list_tools()
    tool_names = [t.name for t in tools]
    assert "calculate" in tool_names
    assert "calculate_sla_penalty" in tool_names
    assert "get_system_time" in tool_names
    assert "query_service_catalog" in tool_names
    assert "unit_converter" in tool_names
    assert len(tools) >= 5


def test_builtin_calculate_safe_eval(clean_registry):
    """Verifies AST-based safe arithmetic calculation tool."""
    res = clean_registry.execute_tool("calculate", {"expression": "(10 + 20) * 3 - 5"})
    assert res.success is True
    assert res.result["result"] == 85

    # Safe error on zero division
    res_err = clean_registry.execute_tool("calculate", {"expression": "10 / 0"})
    assert res_err.success is False
    assert "division by zero" in res_err.error.lower()


def test_builtin_calculate_sla_penalty(clean_registry):
    """Verifies financial SLA penalty calculator tool."""
    res = clean_registry.execute_tool(
        "calculate_sla_penalty",
        {"downtime_hours": 4.5, "hourly_rate_usd": 200.0, "penalty_multiplier": 1.5},
    )
    assert res.success is True
    assert res.result["downtime_hours"] == 4.5
    assert res.result["total_penalty_credit_usd"] == 1350.0
    assert res.result["severity"] == "CRITICAL"


def test_builtin_system_time(clean_registry):
    """Verifies system time and timezone reporting tool."""
    res = clean_registry.execute_tool("get_system_time", {})
    assert res.success is True
    assert "iso_timestamp" in res.result
    assert res.result["timezone"] == "UTC"
    assert "quarter" in res.result


def test_builtin_service_catalog(clean_registry):
    """Verifies IT service catalog query tool."""
    res = clean_registry.execute_tool(
        "query_service_catalog",
        {"service_name": "qdrant"},
    )
    assert res.success is True
    assert res.result["name"] == "Qdrant Vector DB"
    assert "Tier-1" in res.result["tier"]

    # Non-existent service
    res_missing = clean_registry.execute_tool(
        "query_service_catalog",
        {"service_name": "quantum_computer"},
    )
    assert res_missing.success is True
    assert res_missing.result["status"] == "UNKNOWN"


def test_builtin_unit_converter(clean_registry):
    """Verifies unit conversion utility tool."""
    res = clean_registry.execute_tool(
        "unit_converter",
        {"value": 2048, "from_unit": "mb", "to_unit": "gb"},
    )
    assert res.success is True
    assert res.result["result"] == 2.0


def test_openapi_spec_import(clean_registry):
    """Verifies OpenAPI 3.0 / Swagger specification parsing and tool registration."""
    spec_yaml = """
openapi: 3.0.0
info:
  title: Weather and Geo API
  version: 1.0.0
paths:
  /weather/current:
    get:
      summary: Get current weather for a city
      description: Returns temperature and humidity
      operationId: get_current_weather
      parameters:
        - name: city
          in: query
          required: true
          schema:
            type: string
        - name: units
          in: query
          required: false
          schema:
            type: string
  /geo/coordinates:
    post:
      summary: Resolve address coordinates
      operationId: resolve_geo_coordinates
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                address:
                  type: string
"""
    req = OpenAPISpecImportRequest(spec_content=spec_yaml, tag="weather_geo")
    resp = clean_registry.import_openapi_spec(req)
    assert resp.success is True
    assert resp.imported_count >= 2

    # Check that tools exist in registry
    tool_names = [t.name for t in clean_registry.list_tools()]
    assert "get_current_weather" in tool_names
    assert "resolve_geo_coordinates" in tool_names

    # Check parameters
    weather_tool = clean_registry.get_tool("get_current_weather")
    assert weather_tool is not None
    param_names = [p.name for p in weather_tool.parameters]
    assert "city" in param_names


@pytest.mark.asyncio
async def test_tool_calling_strategy_execution():
    """Verifies ToolCallingAgenticRAGStrategy execution with detected tools and retrieval."""
    from src.rag.base import RAGRequest

    strategy = ToolCallingAgenticRAGStrategy()

    # Query triggering calculate_sla_penalty and calculate
    query = (
        "Our API had 3 hours downtime at 150 rate with multiplier 1.2. "
        "What is the total SLA penalty and enterprise compliance status?"
    )
    req = RAGRequest(
        query=query,
        tenant_id="test_tenant",
        top_k=3,
        temperature=0.0,
    )
    response = await strategy.execute(req)
    assert response.answer
    assert "tool_executions" in response.metadata
    tool_execs = response.metadata["tool_executions"]
    assert len(tool_execs) >= 1

    executed_names = [tx["tool_name"] for tx in tool_execs]
    assert any("calculate" in n for n in executed_names)
    assert response.metadata["strategy"] == "Tool-Calling-Agentic"

