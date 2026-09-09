"""Evaluation package initialization."""

from src.evaluation.base import BaseEvaluator, EvaluationResult
from src.evaluation.engine import RAGEvaluationEngine
from src.evaluation.metrics import (
    compute_answer_relevancy,
    compute_context_precision,
    compute_context_recall,
    compute_faithfulness,
)

__all__ = [
    "BaseEvaluator",
    "EvaluationResult",
    "RAGEvaluationEngine",
    "compute_context_precision",
    "compute_context_recall",
    "compute_faithfulness",
    "compute_answer_relevancy",
]
