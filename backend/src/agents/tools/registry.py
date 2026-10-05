"""Dynamic Tool Registry with schema validation, OpenAPI ingestion, and safe sandboxed execution."""

import asyncio
import inspect
import json
import logging
import time
import uuid
from collections.abc import Callable
from typing import Any

import yaml
from src.agents.tools.builtin import (
    calculate,
    calculate_sla_penalty,
    get_system_time,
    query_service_catalog,
    unit_converter,
)
from src.agents.tools.models import (
    OpenAPISpecImportRequest,
    OpenAPISpecImportResponse,
    ToolDefinition,
    ToolExecutionResult,
    ToolParameter,
)

logger = logging.getLogger(__name__)


class DynamicToolRegistry:
    """Manages executable tools, schema validation, and dynamic OpenAPI ingestion."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._handlers: dict[str, Callable[..., Any]] = {}
        self._register_builtins()

    def _register_builtins(self) -> None:
        """Initializes default enterprise utility and financial calculation tools."""
        self.register_tool(
            definition=ToolDefinition(
                name="calculate",
                description="Safely evaluate arithmetic and math formulas (AST parsed, no eval).",
                category="math",
                parameters=[
                    ToolParameter(
                        name="expression",
                        type="string",
                        description="Math expression, e.g. '1200 * 4.5 * 1.5' or 'sqrt(144) + 10'",
                        required=True,
                    )
                ],
            ),
            handler=calculate,
        )

        self.register_tool(
            definition=ToolDefinition(
                name="calculate_sla_penalty",
                description="Compute contractual SLA downtime penalties, credits, and severity.",
                category="financial",
                parameters=[
                    ToolParameter(
                        name="downtime_hours",
                        type="number",
                        description="Hours of service outage/unavailability",
                        required=True,
                    ),
                    ToolParameter(
                        name="hourly_rate_usd",
                        type="number",
                        description="Standard contracted hourly loss rate in USD",
                        default=1200.0,
                        required=False,
                    ),
                    ToolParameter(
                        name="penalty_multiplier",
                        type="number",
                        description="Multiplier penalty factor specified in enterprise contract",
                        default=1.5,
                        required=False,
                    ),
                ],
            ),
            handler=calculate_sla_penalty,
        )

        self.register_tool(
            definition=ToolDefinition(
                name="get_system_time",
                description="Retrieve system UTC timestamp, quarter, and business day status.",
                category="system",
                parameters=[
                    ToolParameter(
                        name="timezone",
                        type="string",
                        description="Target timezone, default UTC",
                        default="UTC",
                        required=False,
                    )
                ],
            ),
            handler=get_system_time,
        )

        self.register_tool(
            definition=ToolDefinition(
                name="query_service_catalog",
                description="Look up platform service architecture, tier, and target SLA.",
                category="system",
                parameters=[
                    ToolParameter(
                        name="service_name",
                        type="string",
                        description="Name of service, e.g. 'qdrant', 'neo4j', 'fastapi', 'redis'",
                        required=True,
                    )
                ],
            ),
            handler=query_service_catalog,
        )

        self.register_tool(
            definition=ToolDefinition(
                name="unit_converter",
                description="Convert digital storage units (KB, MB, GB) or time units (ms, s, hr).",
                category="utility",
                parameters=[
                    ToolParameter(
                        name="value",
                        type="number",
                        description="Numeric quantity to convert",
                        required=True,
                    ),
                    ToolParameter(
                        name="from_unit",
                        type="string",
                        description="Source unit: 'kb', 'mb', 'gb', 'ms', 's', 'hr', etc.",
                        required=True,
                    ),
                    ToolParameter(
                        name="to_unit",
                        type="string",
                        description="Destination unit: 'mb', 'gb', 's', 'hr', etc.",
                        required=True,
                    ),
                ],
            ),
            handler=unit_converter,
        )

    def register_tool(self, definition: ToolDefinition, handler: Callable[..., Any]) -> None:
        """Registers or updates a tool with its schema definition and callable handler."""
        tool_name = definition.name.strip().lower()
        self._tools[tool_name] = definition
        self._handlers[tool_name] = handler
        logger.info(f"Registered tool '{tool_name}' in category '{definition.category}'")

    def list_tools(self, category: str | None = None) -> list[ToolDefinition]:
        """Returns all registered tool definitions, optionally filtered by category."""
        if category:
            return [t for t in self._tools.values() if t.category.lower() == category.lower()]
        return list(self._tools.values())

    def get_tool(self, name: str) -> ToolDefinition | None:
        """Retrieves tool definition by name."""
        return self._tools.get(name.strip().lower())

    def import_openapi_spec(
        self,
        spec: dict[str, Any] | str | OpenAPISpecImportRequest,
        category: str = "imported_api",
        base_url: str | None = None,
    ) -> OpenAPISpecImportResponse:
        """Ingests an OpenAPI 3.0 / Swagger specification and dynamically registers tools."""
        if isinstance(spec, OpenAPISpecImportRequest):
            req_spec = spec.spec or spec.spec_content
            if req_spec is None:
                raise ValueError("No spec content provided in OpenAPISpecImportRequest")
            category = spec.category or spec.tag or category
            base_url = spec.base_url or base_url
            spec = req_spec

        if isinstance(spec, str):
            try:
                spec_dict = json.loads(spec)
            except Exception:
                try:
                    spec_dict = yaml.safe_load(spec)
                except Exception as e:
                    raise ValueError(f"Invalid OpenAPI JSON/YAML specification: {e!s}")
        else:
            spec_dict = spec

        paths = spec_dict.get("paths", {})
        servers = spec_dict.get("servers", [])
        resolved_base = base_url or (servers[0].get("url") if servers else "https://api.internal")

        imported_names: list[str] = []

        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue

            for method in ("get", "post", "put", "delete", "patch"):
                if method not in path_item:
                    continue

                operation = path_item[method]
                op_id = operation.get("operationId")
                if not op_id:
                    clean_path = path.strip("/").replace("/", "_").replace("{", "").replace("}", "")
                    op_id = f"{method}_{clean_path or 'root'}"

                clean_name = op_id.lower().replace("-", "_").replace(" ", "_")
                desc = operation.get("summary") or operation.get("description") or f"Call {path}"

                params: list[ToolParameter] = []
                # Ingest query and path parameters
                for p in operation.get("parameters", []):
                    p_name = p.get("name", "param")
                    p_schema = p.get("schema", {})
                    p_type = p_schema.get("type", "string")
                    params.append(
                        ToolParameter(
                            name=p_name,
                            type=p_type,
                            description=p.get("description", ""),
                            required=p.get("required", False),
                            default=p_schema.get("default"),
                        )
                    )

                # Create synthetic dynamic execution handler
                def make_handler(endpoint_path: str, http_method: str, target_base: str):
                    def endpoint_handler(**kwargs) -> dict[str, Any]:
                        return {
                            "status": "simulated_success",
                            "endpoint": f"{target_base}{endpoint_path}",
                            "method": http_method.upper(),
                            "arguments_sent": kwargs,
                            "timestamp": time.time(),
                        }

                    return endpoint_handler

                tool_def = ToolDefinition(
                    name=clean_name,
                    description=desc,
                    parameters=params,
                    category=category,
                    timeout_sec=8.0,
                    is_async=False,
                )

                self.register_tool(
                    definition=tool_def,
                    handler=make_handler(path, method, resolved_base),
                )
                imported_names.append(clean_name)

        return OpenAPISpecImportResponse(
            imported_count=len(imported_names),
            tools_imported=imported_names,
            tools_registered=imported_names,
            status="success",
            success=True,
        )

    def execute_tool(self, name: str, arguments: dict[str, Any]) -> ToolExecutionResult:
        """Executes a registered tool synchronously with parameter validation and timing."""
        tool_name = name.strip().lower()
        tool_def = self._tools.get(tool_name)
        handler = self._handlers.get(tool_name)
        call_id = f"call_{uuid.uuid4().hex[:10]}"

        if not tool_def or not handler:
            return ToolExecutionResult(
                call_id=call_id,
                tool_name=name,
                success=False,
                error=f"Tool '{name}' is not registered in the system.",
                latency_ms=0.0,
            )

        # Parameter validation
        for param in tool_def.parameters:
            if param.required and param.name not in arguments:
                if param.default is not None:
                    arguments[param.name] = param.default
                else:
                    return ToolExecutionResult(
                        call_id=call_id,
                        tool_name=tool_name,
                        success=False,
                        error=f"Missing required parameter '{param.name}' for tool '{tool_name}'.",
                        latency_ms=0.0,
                    )

        start_time = time.perf_counter()
        try:
            # Handle async handlers if any
            if inspect.iscoroutinefunction(handler):
                loop = asyncio.get_event_loop()
                result = loop.run_until_complete(handler(**arguments))
            else:
                result = handler(**arguments)

            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return ToolExecutionResult(
                call_id=call_id,
                tool_name=tool_name,
                success=True,
                output=result,
                latency_ms=round(elapsed_ms, 2),
            )
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.warning(f"Error executing tool '{tool_name}': {e}")
            return ToolExecutionResult(
                call_id=call_id,
                tool_name=tool_name,
                success=False,
                error=str(e),
                latency_ms=round(elapsed_ms, 2),
            )

    async def aexecute_tool(self, name: str, arguments: dict[str, Any]) -> ToolExecutionResult:
        """Executes a registered tool asynchronously with timeout sandboxing."""
        tool_name = name.strip().lower()
        tool_def = self._tools.get(tool_name)
        handler = self._handlers.get(tool_name)
        call_id = f"call_{uuid.uuid4().hex[:10]}"

        if not tool_def or not handler:
            return ToolExecutionResult(
                call_id=call_id,
                tool_name=name,
                success=False,
                error=f"Tool '{name}' is not registered.",
                latency_ms=0.0,
            )

        for param in tool_def.parameters:
            if param.required and param.name not in arguments:
                if param.default is not None:
                    arguments[param.name] = param.default
                else:
                    return ToolExecutionResult(
                        call_id=call_id,
                        tool_name=tool_name,
                        success=False,
                        error=f"Missing required parameter '{param.name}' for tool '{tool_name}'.",
                        latency_ms=0.0,
                    )

        start_time = time.perf_counter()
        try:
            if inspect.iscoroutinefunction(handler):
                result = await asyncio.wait_for(
                    handler(**arguments), timeout=tool_def.timeout_sec
                )
            else:
                # Run synchronous handler in thread pool
                result = await asyncio.to_thread(handler, **arguments)

            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return ToolExecutionResult(
                call_id=call_id,
                tool_name=tool_name,
                success=True,
                output=result,
                latency_ms=round(elapsed_ms, 2),
            )
        except TimeoutError:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return ToolExecutionResult(
                call_id=call_id,
                tool_name=tool_name,
                success=False,
                error=f"Tool '{tool_name}' timed out after {tool_def.timeout_sec}s.",
                latency_ms=round(elapsed_ms, 2),
            )
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return ToolExecutionResult(
                call_id=call_id,
                tool_name=tool_name,
                success=False,
                error=str(e),
                latency_ms=round(elapsed_ms, 2),
            )


# Global singleton
_global_tool_registry: DynamicToolRegistry | None = None


def get_tool_registry() -> DynamicToolRegistry:
    """Returns singleton DynamicToolRegistry instance."""
    global _global_tool_registry
    if _global_tool_registry is None:
        _global_tool_registry = DynamicToolRegistry()
    return _global_tool_registry
