from typing import Any

from pydantic import BaseModel, Field


class Citation(BaseModel):
    document_id: str
    chunk_id: str
    source: str
    page: int | None = None
    section: str | None = None
    snippet: str
    relevance_score: float = 0.0
    bbox: list[float] | None = None
    page_dimensions: dict[str, float] | None = None
    is_web: bool = False
    url: str | None = None
    domain: str | None = None


class ChatRequest(BaseModel):
    query: str = Field(..., description="User query text")
    rag_strategy: str = Field(default="AUTO", description="Target RAG strategy name or AUTO")
    tenant_id: str = Field(
        default="default_tenant", description="Tenant identifier for multi-tenancy filtering"
    )
    user_id: str = Field(default="user_default", description="User identifier")
    session_id: str | None = Field(default=None, description="Optional session identifier")
    stream: bool = Field(default=False, description="Enable streaming completion")
    top_k: int = Field(default=5, description="Number of context chunks to retrieve")
    max_context_tokens: int = Field(
        default=2048, description="Target token budget for retrieved context"
    )
    enable_compression: bool = Field(
        default=False, description="Enable semantic context compression"
    )
    compression_target_ratio: float = Field(
        default=0.6, description="Target compression ratio (0.2 - 0.9)"
    )
    enable_fact_check: bool = Field(
        default=False, description="Enable automated claim-level hallucination fact-checking"
    )
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
    pii_redacted: bool = False
    pii_count: int = 0
    security_verdict: str = "ALLOWED"
    compression_ratio: float | None = None
    tokens_saved: int | None = None
    fact_check_score: float | None = None
    fact_check_risk: str | None = None
    fact_check_claims_count: int | None = None
    speculative_speedup_ratio: float | None = None
    drift_score: float | None = None


class FactCheckRequest(BaseModel):
    answer: str = Field(..., description="Answer text to verify")
    context_chunks: list[dict[str, Any]] = Field(
        default_factory=list, description="Context chunks to ground against"
    )
    strict_correction: bool = Field(
        default=False, description="Strip contradicted claims from answer"
    )


class FactCheckResponse(BaseModel):
    total_claims: int
    supported_claims: int
    contradicted_claims: int
    neutral_claims: int
    grounding_score: float
    risk_level: str
    claims: list[dict[str, Any]] = Field(default_factory=list)
    corrected_answer: str | None = None


class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str = "1.0.0"
    environment: str = "development"
    services: dict[str, str] = Field(default_factory=dict)


class RAGStrategyMetadata(BaseModel):
    id: str
    name: str
    description: str
    framework: str
    category: str
    version: str = "1.0.0"
    features: list[str] = Field(default_factory=list)


class RAGStrategiesResponse(BaseModel):
    total_strategies: int
    strategies: list[RAGStrategyMetadata]


class RAGVersionResponse(BaseModel):
    application: dict[str, Any]
    models: dict[str, Any]
    rag: dict[str, Any]
    security: dict[str, Any] = Field(default_factory=dict)
    prompts: dict[str, Any] = Field(default_factory=dict)
    evaluation_dataset: dict[str, Any] = Field(default_factory=dict)


class AuditEvent(BaseModel):
    event_id: str
    event_type: str
    user_id: str
    tenant_id: str
    action: str
    resource: str
    status: str
    details: dict[str, Any] = Field(default_factory=dict)
    timestamp: float


class AuditEventsResponse(BaseModel):
    total_events: int
    events: list[AuditEvent]


class DocumentCompareRequest(BaseModel):
    document_ids: list[str] = Field(
        ..., min_length=2, description="List of at least 2 document IDs to compare"
    )
    query: str | None = Field(
        default=None, description="Optional focus query or topic for delta synthesis"
    )
    tenant_id: str = Field(default="default_tenant", description="Tenant identifier")
    focus_areas: list[str] | None = Field(
        default=None, description="Specific comparative dimensions to prioritize"
    )


class DocumentCompareResponse(BaseModel):
    comparison_id: str
    tenant_id: str
    document_ids: list[str]
    document_titles: dict[str, str]
    query: str
    overall_summary: str
    matrix_markdown: str
    risk_assessment: str
    dimensions: list[dict[str, Any]]
    created_at: float
    latency_ms: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphStatsResponse(BaseModel):
    tenant_id: str
    total_nodes: int
    total_relationships: int
    type_counts: dict[str, int] = Field(default_factory=dict)
    top_connected: list[dict[str, Any]] = Field(default_factory=list)
    density: float = 0.0


class GraphEntityItem(BaseModel):
    name: str
    type: str
    degree: int = 0


class GraphEntitiesResponse(BaseModel):
    tenant_id: str
    total_entities: int
    entities: list[GraphEntityItem] = Field(default_factory=list)


class GraphNode(BaseModel):
    id: str
    label: str
    type: str = "CONCEPT"


class GraphLink(BaseModel):
    source: str
    target: str
    label: str
    confidence: float = 0.9


class GraphSubgraphResponse(BaseModel):
    tenant_id: str
    seed_entity: str | None = None
    total_nodes: int
    total_links: int
    nodes: list[GraphNode] = Field(default_factory=list)
    links: list[GraphLink] = Field(default_factory=list)



