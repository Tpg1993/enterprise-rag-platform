"""Unit tests for Multi-Document Comparative Matrix & Delta Synthesis Engine."""

import pytest
from src.rag.comparative.comparator import MultiDocumentComparator, get_document_comparator
from src.rag.comparative.models import ComparisonDimension, ComparisonMatrixResult


def test_comparator_singleton():
    c1 = get_document_comparator()
    c2 = get_document_comparator()
    assert c1 is c2
    assert isinstance(c1, MultiDocumentComparator)


@pytest.mark.asyncio
async def test_comparator_requires_at_least_two_documents():
    comparator = get_document_comparator()
    with pytest.raises(ValueError, match="at least 2 distinct document_ids"):
        await comparator.compare_documents(document_ids=["doc_single"])


@pytest.mark.asyncio
async def test_comparator_basic_matrix_synthesis():
    comparator = get_document_comparator()
    doc_ids = ["doc_agreement_2025", "doc_agreement_2026"]
    result = await comparator.compare_documents(
        document_ids=doc_ids,
        query="Compare SLA uptime and liability indemnity clauses",
        tenant_id="test_tenant",
    )

    assert isinstance(result, ComparisonMatrixResult)
    assert result.comparison_id.startswith("cmp_")
    assert result.tenant_id == "test_tenant"
    assert result.document_ids == doc_ids
    assert len(result.dimensions) >= 5
    assert "Comparative Dimension" in result.matrix_markdown
    assert "|" in result.matrix_markdown
    assert result.overall_summary != ""
    assert result.risk_assessment != ""
    assert result.latency_ms >= 0.0


@pytest.mark.asyncio
async def test_comparator_custom_focus_areas():
    comparator = get_document_comparator()
    doc_ids = ["doc_alpha", "doc_beta"]
    custom_focus = ["Data Sovereignty & Localization", "IP Ownership Rights"]

    result = await comparator.compare_documents(
        document_ids=doc_ids,
        focus_areas=custom_focus,
        tenant_id="test_tenant",
    )

    dim_names = [d.name.lower() for d in result.dimensions]
    assert any("sovereignty" in name for name in dim_names)
    assert any("ownership" in name for name in dim_names)


def test_delta_and_impact_evaluation():
    comparator = get_document_comparator()

    # Identical
    delta, impact = comparator._evaluate_delta_and_impact(
        {"d1": "Strict 99.9% uptime SLA.", "d2": "Strict 99.9% uptime SLA."},
        "SLA Guarantee",
    )
    assert impact == "LOW"
    assert "Identical" in delta

    # High Risk
    delta_high, impact_high = comparator._evaluate_delta_and_impact(
        {
            "d1": "Standard capped liability at 1x fee.",
            "d2": "Unlimited liability and broad indemnity.",
        },
        "Liability Allocation",
    )
    assert impact_high == "HIGH"
    assert "liability" in delta_high.lower() or "variance" in delta_high.lower()

    # Medium
    delta_med, impact_med = comparator._evaluate_delta_and_impact(
        {"d1": "Compute budget $500 monthly.", "d2": "Budget allocation $1500 monthly."},
        "Financial & Resource Consumption",
    )
    assert impact_med == "MEDIUM"


def test_markdown_matrix_formatting():
    comparator = get_document_comparator()
    titles = {"doc_1": "SLA 2025.pdf", "doc_2": "SLA 2026.pdf"}
    dims = [
        ComparisonDimension(
            name="SLA Uptime",
            description="Guaranteed availability percentage",
            document_values={"doc_1": "99.5%", "doc_2": "99.99%"},
            delta_summary="Upgraded SLA from 99.5% to 99.99%.",
            impact_level="MEDIUM",
        ),
        ComparisonDimension(
            name="Liability Cap",
            description="Contractual damage limits",
            document_values={"doc_1": "$10,000", "doc_2": "Unlimited liability"},
            delta_summary="Unlimited liability variance detected.",
            impact_level="HIGH",
        ),
    ]

    table_md = comparator._build_markdown_matrix(titles, dims)
    expected_header = (
        "| Comparative Dimension | SLA 2025.pdf | SLA 2026.pdf | Key Differences / Delta | Impact |"
    )
    assert expected_header in table_md
    assert "| --- | --- | --- | --- | --- |" in table_md
    assert "**SLA Uptime**" in table_md
    assert "**Liability Cap**" in table_md
    assert "`HIGH`" in table_md
