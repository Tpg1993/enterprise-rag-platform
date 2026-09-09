"""Factory router for embedding providers with default fallback to local BGE-M3."""

import logging

from src.embeddings.base import BaseEmbeddingProvider
from src.embeddings.bge import BGEEmbeddingProvider
from src.embeddings.ollama import OllamaEmbeddingProvider
from src.embeddings.sarvam_embed import SarvamEmbeddingProvider
from src.embeddings.tei import TEIEmbeddingProvider

import os

logger = logging.getLogger(__name__)

# Single instance cache for BGE-M3 model
_bge_instance: BaseEmbeddingProvider | None = None


def get_embedding_provider(provider_type: str = "bge-m3", dim: int = 1024) -> BaseEmbeddingProvider:
    """Returns BaseEmbeddingProvider instance based on provider selection string.

    Defaults to 'bge-m3' (Local BGE-M3) if nothing is selected or provider is unknown.
    """
    global _bge_instance
    p_lower = (provider_type or "bge-m3").strip().lower()

    if os.getenv("MOCK_LLM", "true").lower() in ("true", "1") and p_lower in ("bge-m3", "bge", "default"):
        p_lower = "mock-fast"

    if p_lower in ("bge-m3", "bge", "default"):
        if _bge_instance is None:
            _bge_instance = BGEEmbeddingProvider(model_name="BAAI/bge-m3", dim=dim)
        return _bge_instance
    elif p_lower == "tei-local":
        return TEIEmbeddingProvider(endpoint_url="http://localhost:8080", dim=dim)
    elif p_lower == "ollama-local":
        return OllamaEmbeddingProvider(
            endpoint_url="http://localhost:11434", model_name="bge-m3", dim=dim
        )
    elif p_lower in ("sarvam-api", "sarvam"):
        return SarvamEmbeddingProvider(dim=dim)
    elif p_lower == "mock-fast":
        return BGEEmbeddingProvider(use_sentence_transformers=False, dim=dim)
    else:
        logger.info(f"Unrecognized embedding provider '{provider_type}'. Defaulting to 'bge-m3'.")
        if _bge_instance is None:
            _bge_instance = BGEEmbeddingProvider(model_name="BAAI/bge-m3", dim=dim)
        return _bge_instance
