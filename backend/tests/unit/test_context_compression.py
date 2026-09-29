"""Unit tests for Dynamic Semantic Context Compression (Phase 33)."""

from src.context.builder import ContextBuilder, ContextBuildResult
from src.context.compression import SemanticContextCompressor


def test_compressor_basic_compression():
    """Verify that compressor reduces text token count while preserving core semantics."""
    compressor = SemanticContextCompressor()
    verbose_text = (
        "In order to understand the enterprise architecture, it is important to note that "
        "as a matter of fact, the primary database system utilizes PostgreSQL 15.4 for "
        "relational data storage and Qdrant 1.7.0 for dense vector retrieval. It should be "
        "noted that essentially, all communications are encrypted with TLS 1.3."
    )
    result = compressor.compress(
        text=verbose_text,
        query="PostgreSQL database and Qdrant version",
        target_ratio=0.6,
    )

    assert result.is_compressed is True
    assert result.compressed_token_count < result.original_token_count
    assert result.tokens_saved > 0
    assert result.compression_ratio < 1.0

    # Ensure critical entities and numbers are preserved
    lowered = result.compressed_text.lower()
    assert "postgresql" in lowered or "postgres" in lowered
    assert "qdrant" in lowered
    assert "15.4" in result.compressed_text or "1.7.0" in result.compressed_text


def test_compressor_preserves_numerical_and_currency_anchors():
    """Ensure numbers, percentages, and financial metrics are never stripped."""
    compressor = SemanticContextCompressor()
    financial_text = (
        "It is worth noting that for the fiscal year 2024, our revenue reached $12,450,000, "
        "representing an increase of 28.5% year over year, with total profit of $3.2M."
    )
    result = compressor.compress(
        text=financial_text,
        query="fiscal year 2024 revenue growth",
        target_ratio=0.5,
    )

    assert "2024" in result.compressed_text
    assert "$12,450,000" in result.compressed_text or "12,450,000" in result.compressed_text
    assert "28.5%" in result.compressed_text or "28.5" in result.compressed_text


def test_compressor_no_compression_for_short_or_compact_text():
    """Verify that already concise text below minimum threshold is not over-compressed."""
    compressor = SemanticContextCompressor()
    short_text = "System online."
    result = compressor.compress(text=short_text, target_ratio=0.5)

    assert result.compressed_text == short_text
    assert result.compression_ratio == 1.0
    assert result.tokens_saved == 0


def test_context_builder_compression_integration():
    """Verify ContextBuilder builds compressed context and exposes compression metrics."""
    builder = ContextBuilder()
    hits = [
        {
            "chunk_id": "chk_01",
            "content": (
                "It is well understood that as far as security is concerned, "
                "Tenant ID alpha_01 has strict role-based access control with "
                "zero trust guardrails enforced by OPA v0.58.0."
            ),
            "score": 0.95,
            "payload": {
                "document_id": "doc_corp_01",
                "filename": "security_whitepaper.pdf",
                "page_number": 3,
            },
        },
        {
            "chunk_id": "chk_02",
            "content": (
                "Furthermore, it should be pointed out that in addition to OPA, "
                "Presidio redaction sanitizes PII including SSN and credit card numbers."
            ),
            "score": 0.88,
            "payload": {
                "document_id": "doc_corp_02",
                "filename": "privacy_policy.pdf",
                "page_number": 7,
            },
        },
    ]

    # Without compression
    res_uncompressed = builder.build_context(hits, enable_compression=False)
    assert isinstance(res_uncompressed, ContextBuildResult)
    assert res_uncompressed.is_compressed is False
    assert res_uncompressed.tokens_saved == 0

    # With compression enabled
    res_compressed = builder.build_context(
        hits,
        enable_compression=True,
        compression_target_ratio=0.6,
        query="OPA zero trust and Presidio redaction",
    )
    assert res_compressed.is_compressed is True
    assert res_compressed.compression_ratio < 1.0
    assert res_compressed.tokens_saved > 0
    assert len(res_compressed.citations) == 2

    # Verify tuple unpacking compatibility:
    # formatted_context, citations = builder.build_context(...)
    ctx_text, citations = res_compressed
    assert isinstance(ctx_text, str)
    assert len(citations) == 2
