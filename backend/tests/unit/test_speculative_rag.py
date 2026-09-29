"""Unit tests for Speculative Draft-and-Verify RAG Pipeline and Drift Detector."""

import pytest
from src.rag.base import RAGRequest
from src.rag.speculative.drift_detector import SpeculativeDriftDetector
from src.rag.speculative.strategy import SpeculativeDraftVerifyRAGStrategy


def test_drift_detector_aligned():
    """Verify that closely matching draft and context yields ALIGNED status."""
    detector = SpeculativeDriftDetector(drift_threshold=0.35)
    draft = "The platform delivers enterprise RAG with Qdrant vector retrieval and BGE embeddings."
    context = [
        "Enterprise RAG platform integrates Qdrant vector retrieval with local BGE embeddings."
    ]

    report = detector.evaluate_drift(draft_text=draft, verified_chunks=context)
    assert report.status == "ALIGNED"
    assert report.drift_score < 0.35
    assert not report.correction_needed
    assert "qdrant" in report.overlapping_terms
    assert "embeddings" in report.overlapping_terms


def test_drift_detector_missing_critical_clauses():
    """Verify that omission of critical liability/SLA clauses triggers drift correction."""
    detector = SpeculativeDriftDetector(drift_threshold=0.35)
    draft = "The system offers basic support and standard server hosting."
    context = [
        "Contractual SLA guarantees 99.99% uptime with unlimited liability and breach penalties."
    ]

    report = detector.evaluate_drift(draft_text=draft, verified_chunks=context)
    assert report.status in ("MODERATE_DRIFT", "HIGH_DRIFT")
    assert report.correction_needed is True
    assert any(term in report.missing_critical_terms for term in ("liability", "penalty", "sla"))


def test_drift_detector_empty_handling():
    """Verify safe fallback for empty inputs."""
    detector = SpeculativeDriftDetector()
    report = detector.evaluate_drift(draft_text="", verified_chunks=[])
    assert report.status == "ALIGNED"
    assert report.drift_score == 0.1


@pytest.mark.asyncio
async def test_speculative_strategy_execution():
    """Verify speculative dual-path execution, telemetry, and speedup ratios."""
    strategy = SpeculativeDraftVerifyRAGStrategy()
    request = RAGRequest(
        query="What are the supported chunking strategies and latency guarantees?",
        tenant_id="test_speculative_tenant",
        rag_strategy="Speculative-Draft-Verify",
        top_k=3,
    )

    response = await strategy.execute(request)
    assert response.rag_strategy == "Speculative-Draft-Verify"
    assert response.answer != ""
    assert "speedup_ratio" in response.metadata
    assert response.metadata["speedup_ratio"] >= 1.0
    assert "speculative_ttft_ms" in response.metadata
    assert "verified_ttft_ms" in response.metadata
    assert response.metadata["drift_status"] in ("ALIGNED", "MODERATE_DRIFT", "HIGH_DRIFT")
