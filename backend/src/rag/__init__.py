"""RAG package initialization."""

from src.rag.base import BaseRAGStrategy, Citation, RAGRequest, RAGResponse


def get_rag_strategy(strategy_name: str = "AUTO") -> BaseRAGStrategy:
    from src.rag.router import get_rag_strategy as _get_rag_strategy
    return _get_rag_strategy(strategy_name)


__all__ = [
    "BaseRAGStrategy",
    "RAGRequest",
    "RAGResponse",
    "Citation",
    "get_rag_strategy",
]
