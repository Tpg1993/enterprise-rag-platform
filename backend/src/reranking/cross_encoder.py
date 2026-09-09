"""Local Cross-Encoder reranking provider supporting BGE Reranker and SentenceTransformers CrossEncoder."""

import logging
import os
from typing import Any

from src.reranking.base import BaseReranker

logger = logging.getLogger(__name__)


class CrossEncoderReranker(BaseReranker):
    """Local Cross-Encoder reranker evaluating query-chunk pairs via deep cross-attention."""

    def __init__(
        self,
        model_name: str = "BAAI/bge-reranker-large",
        max_length: int = 512,
        use_model: bool = True,
    ):
        self.model_name = model_name
        self.max_length = max_length
        self._model = None

        if use_model and os.getenv("MOCK_LLM", "true").lower() not in ("true", "1"):
            try:
                from sentence_transformers import CrossEncoder

                logger.info(f"Loading local CrossEncoder model '{model_name}'...")
                self._model = CrossEncoder(model_name, max_length=max_length)
                logger.info(f"CrossEncoder model '{model_name}' loaded successfully.")
            except Exception as e:
                logger.warning(
                    f"Could not load CrossEncoder model '{model_name}': {e}. Using deterministic score generator."
                )

    def rerank(
        self,
        query: str,
        hits: list[dict[str, Any]],
        top_n: int = 5,
    ) -> list[dict[str, Any]]:
        if not hits:
            return []

        # Prepare (query, content) pairs for batch scoring
        pairs = [(query, hit.get("content", "")) for hit in hits]

        scores: list[float] = []

        if self._model is not None:
            try:
                raw_scores = self._model.predict(pairs, show_progress_bar=False)
                scores = [float(s) for s in raw_scores]
            except Exception as e:
                logger.warning(f"CrossEncoder inference failed ({e}). Falling back to score generator.")
                scores = [self._fallback_score(query, hit.get("content", "")) for hit in hits]
        else:
            scores = [self._fallback_score(query, hit.get("content", "")) for hit in hits]

        # Attach rerank score to hit copy and sort
        reranked_hits = []
        for hit, score in zip(hits, scores):
            hit_copy = hit.copy()
            hit_copy["rerank_score"] = float(score)
            # Retain original vector score if present, update display score
            hit_copy["score"] = float(score)
            reranked_hits.append(hit_copy)

        reranked_hits.sort(key=lambda x: x["rerank_score"], reverse=True)
        return reranked_hits[:top_n]

    def _fallback_score(self, query: str, content: str) -> float:
        """Deterministic term-overlap cross-attention score for fast offline testing."""
        if not query or not content:
            return 0.0

        q_terms = set(query.lower().split())
        c_terms = content.lower().split()

        if not q_terms or not c_terms:
            return 0.0

        match_count = sum(1 for t in c_terms if t in q_terms)
        overlap_ratio = match_count / float(len(q_terms))
        density_ratio = match_count / float(len(c_terms))

        # Hybrid fallback cross score calculation
        score = (overlap_ratio * 0.7) + (density_ratio * 0.3)
        return round(score, 4)
