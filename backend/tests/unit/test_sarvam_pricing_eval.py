"""Unit tests for Phase 9 Sarvam LLM Provider, dynamic YAML pricing, and RAG evaluation engine."""

import pytest
from src.config.pricing import calculate_llm_cost, get_pricing_config
from src.evaluation.engine import RAGEvaluationEngine
from src.evaluation.metrics import (
    compute_answer_relevancy,
    compute_context_precision,
    compute_context_recall,
    compute_faithfulness,
)
from src.llm.sarvam import SarvamLLMProvider


def test_pricing_yaml_loader_and_llm_cost_calculation():
    config = get_pricing_config()
    assert "models" in config
    assert "sarvam-105b" in config["models"]

    # 1000 prompt tokens ($0.0015/1k) + 500 completion tokens ($0.0030/1k) = $0.0030
    cost = calculate_llm_cost(
        model="sarvam-105b",
        prompt_tokens=1000,
        completion_tokens=500,
        cached_tokens=0,
    )
    assert cost == 0.0030


def test_sarvam_provider_calculate_cost():
    provider = SarvamLLMProvider(api_key="test_key")
    cost = provider.calculate_cost(prompt_tokens=2000, completion_tokens=1000)
    # (2000 * 0.0015 / 1000) + (1000 * 0.0030 / 1000) = 0.0060
    assert cost == 0.0060


@pytest.mark.asyncio
async def test_evaluation_engine_metrics_scoring():
    evaluator = RAGEvaluationEngine()

    query = "What is Sarvam-105B multilingual AI model?"
    contexts = [
        "Sarvam-105B is an enterprise multilingual LLM for Indic languages.",
        "Qdrant vector store manages dense vector index HNSW structures.",
    ]
    answer = "Sarvam-105B is an enterprise multilingual LLM for Indic languages."
    ground_truth = "Sarvam-105B is an Indic multilingual model."

    result = await evaluator.evaluate(
        query=query,
        answer=answer,
        contexts=contexts,
        ground_truth=ground_truth,
        strategy="Hybrid",
        latency_ms=120.5,
        total_cost_usd=0.0015,
    )

    assert result.strategy == "Hybrid"
    assert result.context_precision == 0.5  # 1 out of 2 contexts relevant to query
    assert result.context_recall > 0.5
    assert result.faithfulness == 1.0  # Answer terms 100% grounded in context
    assert result.answer_relevancy > 0.5
    assert 0.0 <= result.overall_score <= 1.0
