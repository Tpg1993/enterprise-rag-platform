"""Reciprocal Rank Fusion (RRF) engine for merging dense vector and sparse lexical retrieval results."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ReciprocalRankFusion:
    """Combines multiple ranked result lists using Reciprocal Rank Fusion (RRF)."""

    def __init__(self, rrf_k: int = 60) -> None:
        self.rrf_k = rrf_k

    def fuse(
        self,
        retrieval_runs: list[list[dict[str, Any]]],
        top_k: int = 5,
        weights: list[float] | None = None,
    ) -> list[dict[str, Any]]:
        """Fuses multiple ordered hit lists using RRF algorithm.

        Args:
            retrieval_runs: List of hit lists from different retrievers (e.g. [dense_hits, bm25_hits]).
            top_k: Final top-K hits to return.
            weights: Optional per-retriever weight multipliers.

        Returns:
            Combined and re-ranked list of hits sorted by fused RRF score.
        """
        if not retrieval_runs:
            return []

        if weights is None:
            weights = [1.0] * len(retrieval_runs)

        rrf_scores: dict[str, float] = {}
        chunk_map: dict[str, dict[str, Any]] = {}

        for run_idx, hits in enumerate(retrieval_runs):
            weight = weights[run_idx] if run_idx < len(weights) else 1.0

            for rank_0based, hit in enumerate(hits):
                cid = hit.get("chunk_id") or hit.get("payload", {}).get("chunk_id", "")
                if not cid:
                    continue

                rank_1based = rank_0based + 1
                rrf_increment = weight * (1.0 / (self.rrf_k + rank_1based))

                rrf_scores[cid] = rrf_scores.get(cid, 0.0) + rrf_increment

                if cid not in chunk_map:
                    chunk_map[cid] = hit

        # Build fused list
        fused_hits = []
        for cid, score in rrf_scores.items():
            base_hit = chunk_map[cid].copy()
            base_hit["score"] = float(score)
            base_hit["rrf_score"] = float(score)
            fused_hits.append(base_hit)

        fused_hits.sort(key=lambda x: x["score"], reverse=True)
        return fused_hits[:top_k]
