"""Embeddings package initialization."""

from src.embeddings.base import BaseEmbeddingProvider
from src.embeddings.bge import BGEEmbeddingProvider
from src.embeddings.factory import get_embedding_provider

__all__ = ["BaseEmbeddingProvider", "BGEEmbeddingProvider", "get_embedding_provider"]
