"""Data models for Multi-Document Comparative Matrix & Delta Synthesis Engine."""

from typing import Any

from pydantic import BaseModel, Field


class ComparisonDimension(BaseModel):
    """Represents a comparative feature, clause, or attribute evaluated across documents."""

    name: str = Field(
        ..., description="Dimension title (e.g., Liability Cap, SLA Guarantee, Pricing)"
    )
    description: str = Field(
        default="", description="Brief explanation of the comparative dimension"
    )
    document_values: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of document_id or title to extracted textual content/value",
    )
    delta_summary: str = Field(
        default="", description="Granular diff explaining variance across documents"
    )
    impact_level: str = Field(
        default="LOW", description="Risk or organizational impact: LOW, MEDIUM, or HIGH"
    )


class ComparisonMatrixResult(BaseModel):
    """Comprehensive structured outcome of a multi-document comparison."""

    comparison_id: str
    tenant_id: str = "default_tenant"
    document_ids: list[str]
    document_titles: dict[str, str] = Field(default_factory=dict)
    query: str
    dimensions: list[ComparisonDimension] = Field(default_factory=list)
    overall_summary: str
    matrix_markdown: str
    risk_assessment: str
    created_at: float = 0.0
    latency_ms: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)
