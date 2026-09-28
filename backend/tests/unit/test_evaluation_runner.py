"""Unit tests for the Golden QA Evaluation & Benchmarking Suite (Phase 29)."""

import json
from pathlib import Path

import pytest
from src.evaluation.run_benchmarks import (
    ALL_STRATEGIES,
    evaluate_strategy_on_dataset,
    generate_markdown_report,
    load_golden_dataset,
    percentile,
    run_benchmark_pipeline,
)


def test_golden_qa_dataset_structure_and_categories() -> None:
    """Verifies that the Golden QA dataset exists, has at least 50 curated items,

    and adheres strictly to schema with all five required categories.
    """
    dataset_path = Path("backend/data/evaluation/golden_qa.json")
    if not dataset_path.exists():
        dataset_path = Path("data/evaluation/golden_qa.json")

    assert dataset_path.exists(), f"Golden QA dataset missing at {dataset_path}"

    items = load_golden_dataset(str(dataset_path))
    assert len(items) >= 50, f"Expected at least 50 golden QA items, got {len(items)}"

    required_keys = {"id", "category", "query", "ground_truth", "expected_contexts"}
    categories = set()

    for item in items:
        assert required_keys.issubset(item.keys()), f"Item {item.get('id')} missing required keys"
        assert item["query"].strip(), "Query must not be empty"
        assert item["ground_truth"].strip(), "Ground truth must not be empty"
        assert isinstance(item["expected_contexts"], list), "expected_contexts must be a list"
        categories.add(item["category"])

    expected_categories = {"factual", "multi_hop", "tabular", "comparative", "exploratory"}
    diff = expected_categories - categories
    assert expected_categories.issubset(categories), f"Missing categories: {diff}"


def test_percentile_calculation() -> None:
    """Tests mathematical correctness of percentile computation including edge cases."""
    assert percentile([], 50) == 0.0
    assert percentile([42.0], 50) == 42.0
    assert percentile([42.0], 95) == 42.0

    data = [10.0, 20.0, 30.0, 40.0, 50.0]
    p50 = percentile(data, 50)
    assert p50 == 30.0

    p90 = percentile(data, 90)
    assert p90 > 40.0


@pytest.mark.asyncio
async def test_evaluate_strategy_on_dataset() -> None:
    """Tests strategy benchmark execution against golden items."""
    sample_dataset = [
        {
            "id": "test-1",
            "category": "factual",
            "query": "What is the token dimension of BGE-M3?",
            "ground_truth": "The dense dimension is 1024.",
            "expected_contexts": ["BGE-M3 uses 1024-dimensional dense vectors."],
        }
    ]

    summary = await evaluate_strategy_on_dataset(
        strategy_name="Basic",
        dataset=sample_dataset,
        tenant_id="test_bench_tenant",
    )

    assert summary["strategy"] == "Basic"
    assert summary["evaluated_queries"] == 1
    assert "mean_overall_score" in summary
    assert "mean_precision" in summary
    assert "mean_recall" in summary
    assert "mean_faithfulness" in summary
    assert "mean_relevancy" in summary
    assert "latency_p50_ms" in summary
    assert "latency_p95_ms" in summary
    assert "mean_cost_usd" in summary
    assert len(summary["items"]) == 1
    assert summary["items"][0]["query_id"] == "test-1"


def test_generate_markdown_report(tmp_path: Path) -> None:
    """Tests generation of the Markdown executive comparison report."""
    mock_results = [
        {
            "strategy": "Hybrid-Graph-Agentic",
            "mean_overall_score": 0.942,
            "mean_precision": 0.95,
            "mean_recall": 0.93,
            "mean_faithfulness": 0.96,
            "mean_relevancy": 0.93,
            "latency_p50_ms": 32.5,
            "latency_p95_ms": 55.0,
            "mean_tokens": 420.0,
            "mean_cost_usd": 0.00015,
        },
        {
            "strategy": "Basic",
            "mean_overall_score": 0.812,
            "mean_precision": 0.80,
            "mean_recall": 0.78,
            "mean_faithfulness": 0.85,
            "mean_relevancy": 0.82,
            "latency_p50_ms": 12.0,
            "latency_p95_ms": 18.0,
            "mean_tokens": 250.0,
            "mean_cost_usd": 0.00008,
        },
    ]

    out_file = tmp_path / "test_report.md"
    content = generate_markdown_report(mock_results, str(out_file))

    assert out_file.exists()
    assert "# Enterprise RAG Multi-Architecture Benchmark Report" in content
    assert "Hybrid-Graph-Agentic" in content
    assert "Basic" in content
    assert "🏆 (Pinnacle)" in content
    assert "| Rank | Strategy | Overall Score |" in content


@pytest.mark.asyncio
async def test_run_benchmark_pipeline(tmp_path: Path) -> None:
    """Tests complete end-to-end benchmark pipeline execution."""
    sample_dataset = [
        {
            "id": "bm-1",
            "category": "factual",
            "query": "What is the dense vector dimension?",
            "ground_truth": "1024 dimensions",
            "expected_contexts": ["Dense vectors are 1024 dimensional."],
        }
    ]
    data_file = tmp_path / "temp_qa.json"
    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(sample_dataset, f)

    out_json = tmp_path / "results.json"
    out_md = tmp_path / "results.md"

    results = await run_benchmark_pipeline(
        dataset_path=str(data_file),
        strategies=["Basic", "Hybrid"],
        limit=1,
        output_json=str(out_json),
        output_md=str(out_md),
    )

    assert len(results) == 2
    assert out_json.exists()
    assert out_md.exists()

    with open(out_json, encoding="utf-8") as f:
        saved_data = json.load(f)
        assert len(saved_data["summaries"]) == 2
        assert saved_data["total_strategies"] == 2


def test_all_strategies_list() -> None:
    """Verifies that all 15 enterprise RAG strategies are configured for benchmarking."""
    assert len(ALL_STRATEGIES) == 15
    assert "Basic" in ALL_STRATEGIES
    assert "Hybrid" in ALL_STRATEGIES
    assert "GraphRAG" in ALL_STRATEGIES
    assert "SQL-RAG" in ALL_STRATEGIES
    assert "Hybrid-Graph-Agentic" in ALL_STRATEGIES
