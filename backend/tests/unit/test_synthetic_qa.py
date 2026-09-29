"""Unit tests for Autonomous Synthetic QA Dataset Generator & Tenant Benchmark (Phase 35)."""

import pytest
from src.evaluation.synthetic_generator import SyntheticQAGenerator, SyntheticQAPair
from src.evaluation.tenant_benchmark import TenantBenchmarkReport, TenantBenchmarkRunner


def test_synthetic_qa_extract_facts():
    """Verify factual statements extraction containing entities or numbers."""
    generator = SyntheticQAGenerator()
    text = (
        "Enterprise Multi-Architecture RAG achieves 99.8% precision with Sarvam AI 105B. "
        "The system incorporates Qdrant 1.7.0 and PostgreSQL 15.4. "
        "Short phrase. "
        "A regular sentence without any key numeric metrics."
    )
    facts = generator._extract_key_facts(text)
    assert len(facts) >= 2
    assert any("99.8%" in f["sentence"] for f in facts)
    assert any("Qdrant" in f["sentence"] for f in facts)


def test_synthetic_qa_generation_types():
    """Verify generation of diverse question types (factoid, multi-hop, comparative, etc)."""
    generator = SyntheticQAGenerator()
    content = (
        "The system operates with 60 RPM token limits under sliding-window rate limiters. "
        "PostgreSQL 15.4 maintains strict ACID compliance for all audit events and logs. "
        "Vector indexing in Qdrant executes with HNSW scalar quantization at 1536 dimensions. "
        "Zero-trust security enforces Presidio PII redaction across all ingest pipelines."
    )
    pairs = generator.generate_pairs_from_text(
        content=content,
        document_id="doc_test_101",
        filename="system_spec.pdf",
        chunk_id="chunk_01",
        page=2,
        target_count=4,
    )

    assert len(pairs) == 4
    types_found = {p.question_type for p in pairs}
    assert "factoid" in types_found
    assert "multi_hop" in types_found
    assert "comparative" in types_found
    assert "unanswerable" in types_found

    for p in pairs:
        assert isinstance(p, SyntheticQAPair)
        assert p.source_document == "system_spec.pdf"
        assert p.page_number == 2
        assert len(p.question) > 10
        assert len(p.ground_truth_answer) > 5


def test_synthetic_qa_fallback_generation():
    """Verify fallback generation when content contains no complex entities or numbers."""
    generator = SyntheticQAGenerator()
    content = "A simple overview of generalized components without any specific data."
    pairs = generator.generate_pairs_from_text(
        content=content,
        document_id="doc_fallback",
        filename="simple.txt",
        target_count=1,
    )
    assert len(pairs) == 1
    assert pairs[0].question_type == "factoid"
    assert "simple.txt" in pairs[0].question


def test_synthetic_qa_tenant_generation_default():
    """Verify tenant QA generation returns high-quality synthetic pairs."""
    generator = SyntheticQAGenerator()
    pairs = generator.generate_for_tenant(tenant_id="test_nonexistent_tenant", target_count=3)
    assert len(pairs) == 3
    for p in pairs:
        assert p.id.startswith("syn_")
        assert len(p.ground_truth_answer) > 0


@pytest.mark.asyncio
async def test_tenant_benchmark_runner_execution():
    """Verify multi-strategy benchmark runner executes and produces ranked leaderboard."""
    runner = TenantBenchmarkRunner()
    report = await runner.run_benchmark(
        tenant_id="test_tenant_bench",
        strategies=["Basic", "Hybrid"],
        num_samples=2,
    )

    assert isinstance(report, TenantBenchmarkReport)
    assert report.tenant_id == "test_tenant_bench"
    assert len(report.leaderboard) == 2
    assert report.total_eval_samples == 2

    # Leaderboard should be ordered by overall_score descending
    assert report.leaderboard[0].rank == 1
    assert report.leaderboard[1].rank == 2
    assert report.leaderboard[0].overall_score >= report.leaderboard[1].overall_score
    assert report.recommended_strategy in ["Basic", "Hybrid"]
    assert len(report.leaderboard[0].strengths) > 0
