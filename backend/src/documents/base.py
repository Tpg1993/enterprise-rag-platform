"""Abstract base class and schemas for document parsers."""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class ParsedChunk(BaseModel):
    chunk_index: int
    content: str
    page_number: int | None = None
    section_title: str | None = None
    bbox: list[float] | None = None
    page_dimensions: dict[str, float] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ParsedDocument(BaseModel):
    document_id: str
    filename: str
    file_type: str
    total_pages: int | None = None
    full_text: str
    chunks: list[ParsedChunk] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    checksum: str = ""


class DocumentParser(ABC):
    """Abstract interface for multi-format document parsers."""

    @abstractmethod
    def parse(self, file_bytes: bytes, filename: str, document_id: str) -> ParsedDocument:
        """Parses file content into a structured ParsedDocument."""
        pass
