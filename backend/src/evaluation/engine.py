"""RAGEvaluationEngine executing multi-dimensional evaluation across Quality, Latency, and Cost."""

import logging
from src.evaluation.base import BaseEvaluator, EvaluationResult
from src.evaluation.metrics import (
    compute_answer_relevancy,
    compute_context_precision,
    compute_context_recall,
    compute_faithfulness,
)

logger = logging.getLogger(__name__)


class RAGEvaluationEngine(BaseEvaluator):
    """Production evaluation engine calculating Context Precision, Recall, Faithfulness, and Relevancy."""

    async def evaluate(
        self,
        query: str,
        answer: str,
        contexts: list[str],
        ground_truth: str | None = None,
        strategy: str = "AUTO",
        latency_ms: float = 0.0,
        total_cost_usd: float = 0.0,
    ) -> EvaluationResult:
        precision = compute_context_precision(query, contexts)
        recall = compute_context_recall(ground_truth, contexts)
        faithfulness = compute_faithfulness(answer, contexts)
        relevancy = compute_answer_relevancy(query, answer)

        # Weighted aggregate overall score
        overall = round(
            (precision * 0.25) + (recall * 0.25) + (faithfulness * 0.30) + (relevancy * 0.20),
            4,
        )

        logger.info(
            f"Evaluation [{strategy}]: Precision={precision}, Recall={recall}, "
            f"Faithfulness={faithfulness}, Relevancy={relevancy}, Overall={overall}"
        )

        return EvaluationResult(
            strategy=strategy,
            query=query,
            context_precision=precision,
            context_recall=recall,
            faithfulness=faithfulness,
            answer_relevancy=relevancy,
            overall_score=overall,
            latency_ms=latency_ms,
            total_cost_usd=total_cost_usd,
            metadata={"contexts_count": len(contexts)},
        )
