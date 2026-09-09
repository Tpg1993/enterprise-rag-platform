"""Factory loader for reranker instances with caching."""

import logging

from src.reranking.base import BaseReranker
from src.reranking.cross_encoder import CrossEncoderReranker

logger = logging.getLogger(__name__)

# Single instance cache
_reranker_instance: BaseReranker | None = None


def get_reranker(model_name: str = "BAAI/bge-reranker-large") -> BaseReranker:
    """Returns singleton BaseReranker instance.

    Defaults to CrossEncoderReranker.
    """
    global _reranker_instance

    if _reranker_instance is None:
        logger.info(f"Initializing Reranker factory with model '{model_name}'...")
        _reranker_instance = CrossEncoderReranker(model_name=model_name)

    return _reranker_instance
