"""Abstract Base Class and Request/Response schemas for all RAG Strategies."""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class Citation(BaseModel):
    document_id: str
    filename: str
    chunk_id: str
    content_snippet: str
    page_number: int | None = None
    section_title: str | None = None
    relevance_score: float = 0.0
    bbox: list[float] | None = None
    page_dimensions: dict[str, float] | None = None


class RAGRequest(BaseModel):
    query: str
    tenant_id: str = "default_tenant"
    rag_strategy: str = "Basic"
    top_k: int = 5
    temperature: float = 0.1
    max_tokens: int = 1024
    max_context_tokens: int = 2048
    enable_compression: bool = False
    compression_target_ratio: float = 0.6
    metadata: dict[str, Any] = Field(default_factory=dict)


class RAGResponse(BaseModel):
    answer: str
    query: str
    rag_strategy: str
    citations: list[Citation] = Field(default_factory=list)
    latency_ms: float
    prompt_tokens: int = 0
    completion_tokens: int = 0
    estimated_cost_usd: float = 0.0
    model: str = "sarvam-105b"
    trace_id: str = ""
    tenant_id: str = "default_tenant"
    compression_ratio: float | None = None
    tokens_saved: int | None = None


class BaseRAGStrategy(ABC):
    """Abstract interface for all modular, interchangeable RAG strategies."""

    @abstractmethod
    async def execute(self, request: RAGRequest) -> RAGResponse:
        """Executes RAG strategy and returns structured RAGResponse."""
        pass
