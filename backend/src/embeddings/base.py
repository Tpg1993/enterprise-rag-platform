"""Abstract interface and result schemas for embedding providers."""

from abc import ABC, abstractmethod


class BaseEmbeddingProvider(ABC):
    """Abstract base class for local embedding generators."""

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Generates embedding vectors for a list of document texts."""
        pass

    @abstractmethod
    def embed_query(self, query: str) -> list[float]:
        """Generates an embedding vector for a single search query."""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Returns vector dimension size (e.g. 1024)."""
        pass
