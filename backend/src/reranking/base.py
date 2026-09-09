"""Abstract Base Class for all Reranking Providers."""

from abc import ABC, abstractmethod
from typing import Any


class BaseReranker(ABC):
    """Abstract base class for cross-encoder and bi-encoder reranking models."""

    @abstractmethod
    def rerank(
        self,
        query: str,
        hits: list[dict[str, Any]],
        top_n: int = 5,
    ) -> list[dict[str, Any]]:
        """Re-scores candidate hits using query-document cross-attention matching.

        Args:
            query: User search query.
            hits: List of candidate retrieval hit dictionaries.
            top_n: Number of highest scoring hits to return.

        Returns:
            Re-ranked and sorted list of top_n hit dictionaries.
        """
        pass
