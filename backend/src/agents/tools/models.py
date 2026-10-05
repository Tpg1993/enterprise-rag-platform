"""Pydantic data models for the Dynamic Tool Registry and OpenAPI function calling."""

from typing import Any

from pydantic import BaseModel, Field


class ToolParameter(BaseModel):
    """Specification of an individual tool input parameter."""

    name: str
    type: str = "string"  # string, number, integer, boolean, object, array
    description: str = ""
    required: bool = True
    default: Any = None
    enum: list[str] | None = None


class ToolDefinition(BaseModel):
    """Declarative specification of an executable agentic tool."""

    name: str
    description: str
    parameters: list[ToolParameter] = Field(default_factory=list)
    category: str = "general"
    timeout_sec: float = 10.0
    is_async: bool = False
    requires_confirmation: bool = False


class ToolCall(BaseModel):
    """An invocation instruction for an authorized tool."""

    call_id: str
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolExecutionResult(BaseModel):
    """Outcome and telemetry of a tool invocation."""

    call_id: str
    tool_name: str
    success: bool
    output: Any = None
    result: Any = None
    error: str | None = None
    latency_ms: float = 0.0

    def model_post_init(self, __context: Any) -> None:
        if self.result is None and self.output is not None:
            self.result = self.output
        elif self.output is None and self.result is not None:
            self.output = self.result


class ToolExecutionRequest(BaseModel):
    """Direct invocation request payload for testing tools."""

    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class OpenAPISpecImportRequest(BaseModel):
    """Request payload to parse and register tools from an OpenAPI/Swagger document."""

    spec: dict[str, Any] | str | None = None
    spec_content: str | None = None
    category: str = "imported_api"
    tag: str | None = None
    base_url: str | None = None

    def model_post_init(self, __context: Any) -> None:
        if self.spec is None and self.spec_content is not None:
            self.spec = self.spec_content
        elif self.spec_content is None and isinstance(self.spec, str):
            self.spec_content = self.spec
        if self.tag and (not self.category or self.category == "imported_api"):
            self.category = self.tag


class OpenAPISpecImportResponse(BaseModel):
    """Summary of endpoints successfully ingested into the tool registry."""

    imported_count: int
    tools_imported: list[str] = Field(default_factory=list)
    tools_registered: list[str] = Field(default_factory=list)
    status: str = "success"
    success: bool = True

    def model_post_init(self, __context: Any) -> None:
        if not self.tools_registered and self.tools_imported:
            self.tools_registered = self.tools_imported
        elif not self.tools_imported and self.tools_registered:
            self.tools_imported = self.tools_registered

    def __iter__(self):
        return iter(self.tools_imported)

    def __len__(self) -> int:
        return len(self.tools_imported)

