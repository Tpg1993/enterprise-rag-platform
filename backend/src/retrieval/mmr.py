"""Maximal Marginal Relevance (MMR) selection algorithm for diversity-focused re-ranking."""

import logging
import math
from typing import Any

logger = logging.getLogger(__name__)


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """Computes cosine similarity between two float vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0

    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))

    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0

    return dot / (norm1 * norm2)


class MaximalMarginalRelevance:
    """Maximal Marginal Relevance selector balancing relevance to query with diversity."""

    def __init__(self, lambda_mult: float = 0.7) -> None:
        self.lambda_mult = max(0.0, min(1.0, lambda_mult))

    def select(
        self,
        query_vector: list[float],
        candidate_hits: list[dict[str, Any]],
        candidate_vectors: list[list[float]],
        final_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Selects top final_k non-redundant hits using MMR.

        Args:
            query_vector: Dense embedding vector for user query.
            candidate_hits: List of retrieved hit payloads/dicts.
            candidate_vectors: List of dense embedding vectors matching candidate_hits.
            final_k: Number of diverse candidates to select.

        Returns:
            Re-ranked list of top final_k hits balancing relevance and diversity.
        """
        if not candidate_hits or not candidate_vectors:
            return []

        num_candidates = min(len(candidate_hits), len(candidate_vectors))
        target_k = min(final_k, num_candidates)

        # Precompute similarity to query vector
        query_sims = [
            cosine_similarity(query_vector, candidate_vectors[i]) for i in range(num_candidates)
        ]

        selected_indices: list[int] = []
        unselected_indices: set[int] = set(range(num_candidates))

        # First selection: Highest similarity to query
        first_idx = max(range(num_candidates), key=lambda i: query_sims[i])
        selected_indices.append(first_idx)
        unselected_indices.remove(first_idx)

        # Iterative selection of remaining target_k - 1 candidates
        while len(selected_indices) < target_k and unselected_indices:
            best_score = -float("inf")
            best_idx = -1

            for candidate_idx in unselected_indices:
                sim_query = query_sims[candidate_idx]

                # Max similarity to any already selected candidate
                max_sim_doc = max(
                    cosine_similarity(
                        candidate_vectors[candidate_idx], candidate_vectors[selected_idx]
                    )
                    for selected_idx in selected_indices
                )

                # MMR score formula
                mmr_score = (self.lambda_mult * sim_query) - ((1.0 - self.lambda_mult) * max_sim_doc)

                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = candidate_idx

            if best_idx != -1:
                selected_indices.append(best_idx)
                unselected_indices.remove(best_idx)
            else:
                break

        return [candidate_hits[i] for i in selected_indices]
