"""Pydantic v2 schemas for API requests, chat completions, citations, and health metrics."""

from pydantic import BaseModel, Field


class Citation(BaseModel):
    document_id: str
    chunk_id: str
    source: str
    page: int | None = None
    section: str | None = None
    snippet: str
    relevance_score: float = 0.0


class ChatRequest(BaseModel):
    query: str = Field(..., description="User query text")
    rag_strategy: str = Field(default="AUTO", description="Target RAG strategy name or AUTO")
    tenant_id: str = Field(
        default="default_tenant", description="Tenant identifier for multi-tenancy filtering"
    )
    user_id: str = Field(default="user_default", description="User identifier")
    stream: bool = Field(default=False, description="Enable streaming completion")
    top_k: int = Field(default=5, description="Number of context chunks to retrieve")
    max_context_tokens: int = Field(default=2048, description="Target token budget for retrieved context")
    metadata: dict[str, str] = Field(default_factory=dict, description="Custom request metadata")


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    rag_strategy: str = "Basic"
    rag_version: str = "1.0.0"
    framework: str = "none"
    model: str = "sarvam-105b"
    latency_ms: float = 0.0
    ttft_ms: float | None = None
    token_usage: dict[str, int] = Field(default_factory=dict)
    estimated_cost_usd: float = 0.0
    retrieval_count: int = 0
    reranked_count: int = 0
    cache_hit: bool = False
    trace_id: str = ""


class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str = "1.0.0"
    environment: str = "development"
    services: dict[str, str] = Field(default_factory=dict)
