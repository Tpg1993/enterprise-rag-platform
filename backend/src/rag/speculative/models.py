"""Data models for Speculative Draft-and-Verify RAG Pipeline."""

from typing import Any

from pydantic import BaseModel, Field


class DriftAssessment(BaseModel):
    """Evaluation of semantic divergence between draft tokens and verified context."""

    drift_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Divergence score (0.0 = perfect alignment, 1.0 = diverged)",
    )
    status: str = Field(
        default="ALIGNED",
        description="Alignment classification: ALIGNED, MODERATE_DRIFT, HIGH_DRIFT",
    )
    overlapping_terms: list[str] = Field(
        default_factory=list,
        description="Shared terms between draft and verified context",
    )
    missing_critical_terms: list[str] = Field(
        default_factory=list,
        description="Key clauses present in verified context but missing in draft",
    )
    correction_needed: bool = Field(
        default=False,
        description="Flag indicating if a verified correction addendum is required",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class SpeculativeTelemetry(BaseModel):
    """Operational latency and acceleration metrics for speculative execution."""

    speculative_ttft_ms: float = Field(default=0.0, description="Draft Time-To-First-Token in ms")
    verified_ttft_ms: float = Field(default=0.0, description="Verified full pipeline TTFT in ms")
    speedup_ratio: float = Field(default=1.0, description="Latency acceleration multiplier")
    drift_score: float = Field(default=0.0, description="Semantic drift score")
    drift_status: str = Field(default="ALIGNED", description="Drift classification")
