"""Operational metrics collector for latency breakdown, token consumption, and system costs."""

from typing import Any
from pydantic import BaseModel, Field


class MetricsSummary(BaseModel):
    """Aggregated platform performance metrics."""

    total_requests: int = 0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_cost_usd: float = 0.0
    strategies_breakdown: dict[str, int] = Field(default_factory=dict)


class MetricsCollector:
    """Collects and aggregates real-time operational execution metrics."""

    def __init__(self):
        self.records: list[dict[str, Any]] = []

    def record_request(
        self,
        strategy: str,
        latency_ms: float,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float,
    ) -> None:
        self.records.append({
            "strategy": strategy,
            "latency_ms": latency_ms,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost_usd": cost_usd,
        })

    def get_summary(self) -> MetricsSummary:
        if not self.records:
            return MetricsSummary()

        total_reqs = len(self.records)
        latencies = sorted([r["latency_ms"] for r in self.records])
        avg_lat = sum(latencies) / float(total_reqs)
        p95_idx = int(total_reqs * 0.95)
        p95_lat = latencies[min(p95_idx, total_reqs - 1)]

        p_tokens = sum(r["prompt_tokens"] for r in self.records)
        c_tokens = sum(r["completion_tokens"] for r in self.records)
        cost = sum(r["cost_usd"] for r in self.records)

        breakdown: dict[str, int] = {}
        for r in self.records:
            strat = r["strategy"]
            breakdown[strat] = breakdown.get(strat, 0) + 1

        return MetricsSummary(
            total_requests=total_reqs,
            avg_latency_ms=round(avg_lat, 2),
            p95_latency_ms=round(p95_lat, 2),
            total_prompt_tokens=p_tokens,
            total_completion_tokens=c_tokens,
            total_cost_usd=round(cost, 6),
            strategies_breakdown=breakdown,
        )
