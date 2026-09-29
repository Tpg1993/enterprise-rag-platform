"""Base chunker abstractions and Chunk schema."""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class Chunk(BaseModel):
    chunk_id: str
    document_id: str
    tenant_id: str = "default_tenant"
    parent_id: str | None = None
    chunk_index: int
    content: str
    token_count: int = 0
    page_number: int | None = None
    section_title: str | None = None
    bbox: list[float] | None = None
    page_dimensions: dict[str, float] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class BaseChunker(ABC):
    """Abstract interface for pluggable text chunkers."""

    @abstractmethod
    def chunk(self, text: str, document_id: str, tenant_id: str = "default_tenant") -> list[Chunk]:
        """Splits document text into a list of Chunk objects."""
        pass
