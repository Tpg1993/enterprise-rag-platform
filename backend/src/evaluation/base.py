"""Abstract Base Class and Result Models for RAG Evaluation Engine (RAGAS & DeepEval metrics)."""

from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel, Field


class EvaluationResult(BaseModel):
    """Structured result containing RAG quality, operational, and financial metrics."""

    strategy: str
    query: str
    context_precision: float = Field(ge=0.0, le=1.0)
    context_recall: float = Field(ge=0.0, le=1.0)
    faithfulness: float = Field(ge=0.0, le=1.0)
    answer_relevancy: float = Field(ge=0.0, le=1.0)
    overall_score: float = Field(ge=0.0, le=1.0)
    latency_ms: float = Field(ge=0.0)
    total_cost_usd: float = Field(ge=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BaseEvaluator(ABC):
    """Abstract interface for RAG evaluation engines."""

    @abstractmethod
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
        """Evaluates a single RAG execution across Quality, Latency, and Cost metrics."""
        pass
