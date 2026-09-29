"""Unit tests for Automated Claim-Level Hallucination Guardrail & NLI Fact-Checker."""

from src.security.fact_checker import (
    ClaimExtractor,
    FactCheckReport,
    NLIFactChecker,
    get_fact_checker,
)


def test_claim_extractor_splits_and_strips_preamble():
    """Verifies that ClaimExtractor extracts discrete claims and strips filler preambles."""
    extractor = ClaimExtractor()
    sample_text = (
        "Based on the provided documents, Sarvam AI develops enterprise foundational models. "
        "The primary model sarvam-105b supports high-throughput multilingual inference. "
        "In conclusion, the architecture enforces zero-trust data boundaries."
    )
    claims = extractor.extract_claims(sample_text)
    assert len(claims) == 3
    assert not claims[0].lower().startswith("based on the provided documents")
    assert not claims[2].lower().startswith("in conclusion")
    assert "sarvam ai develops enterprise foundational models" in claims[0].lower()


def test_claim_extractor_handles_empty_or_short_input():
    """Verifies that ClaimExtractor handles blank text gracefully."""
    extractor = ClaimExtractor()
    assert extractor.extract_claims("") == []
    assert extractor.extract_claims("   ") == []


def test_nli_fact_checker_supported_claim():
    """Verifies that a claim with strong contextual overlap receives SUPPORTED verdict."""
    checker = NLIFactChecker()
    context = [
        {
            "chunk_id": "chk_101",
            "content": (
                "Sarvam AI developed sarvam-105b with 105 billion parameters for Indian languages."
            ),
        }
    ]
    claim = "Sarvam AI released sarvam-105b with 105 billion parameters."
    item = checker.verify_claim(claim, context)

    assert item.verdict == "SUPPORTED"
    assert item.confidence >= 0.70
    assert "chk_101" in item.grounding_chunk_ids


def test_nli_fact_checker_contradicted_or_unsupported_claim():
    """Verifies that claims with negative absolute assertions receive CONTRADICTED verdict."""
    checker = NLIFactChecker()
    context = [
        {
            "chunk_id": "chk_201",
            "content": (
                "The platform strictly enforces Qdrant dense vector search with tenant isolation."
            ),
        }
    ]
    claim = "The system never supports vector databases and refused any search indexing."
    item = checker.verify_claim(claim, context)

    assert item.verdict in ("CONTRADICTED", "NEUTRAL")


def test_nli_fact_checker_full_report_and_strict_correction():
    """Verifies verify() generates FactCheckReport and supports strict correction."""
    checker = NLIFactChecker()
    context = [
        {
            "chunk_id": "c1",
            "content": "The enterprise platform uses FastAPI for asynchronous REST endpoints.",
        },
        {
            "chunk_id": "c2",
            "content": "LangGraph orchestrates cyclical state machines for autonomous agents.",
        },
    ]

    answer = (
        "FastAPI powers the asynchronous REST endpoints. "
        "LangGraph manages cyclical agent state machines. "
        "The system never supports any asynchronous operations."
    )

    report = checker.verify(answer, context, strict_correction=True)
    assert isinstance(report, FactCheckReport)
    assert report.total_claims == 3
    assert report.supported_claims >= 2
    assert report.grounding_score > 0.50
    assert report.risk_level in ("LOW", "MEDIUM", "HIGH")
    assert report.corrected_answer is not None


def test_get_fact_checker_singleton():
    """Verifies that get_fact_checker returns a valid singleton instance."""
    c1 = get_fact_checker()
    c2 = get_fact_checker()
    assert isinstance(c1, NLIFactChecker)
    assert c1 is c2
