"""Prometheus Metrics Service for Enterprise RAG & Agentic AI Platform.

Provides standard RED (Rate, Errors, Duration) metrics, token throughput,
dynamic cost accounting, and multi-tier cache telemetry for Prometheus and Grafana.
"""

import logging
import threading
from typing import Any

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    REGISTRY,
    generate_latest,
)

logger = logging.getLogger(__name__)


class PrometheusMetricsManager:
    """Enterprise Prometheus metrics collector with multi-tenant and strategy labels."""

    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        self.registry = registry or REGISTRY
        self._lock = threading.Lock()

        # 1. RED Metrics: Request Rate & Status
        self.requests_total = Counter(
            "rag_requests_total",
            "Total number of RAG and Agent execution requests processed",
            ["strategy", "tenant_id", "status"],
            registry=self.registry,
        )

        # 2. Duration / Latency Breakdown (Histogram)
        self.request_duration_seconds = Histogram(
            "rag_request_duration_seconds",
            "End-to-end execution latency for RAG requests in seconds",
            ["strategy", "tenant_id"],
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
            registry=self.registry,
        )

        # 3. Time to First Token (TTFT)
        self.ttft_seconds = Histogram(
            "rag_ttft_seconds",
            "Time-to-First-Token latency in seconds",
            ["strategy"],
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0),
            registry=self.registry,
        )

        # 4. Token Consumption (Prompt vs Completion)
        self.tokens_total = Counter(
            "rag_tokens_total",
            "Total token consumption across prompt and completion phases",
            ["type", "strategy", "tenant_id"],
            registry=self.registry,
        )

        # 5. Financial Cost Accounting ($ USD)
        self.cost_usd_total = Counter(
            "rag_cost_usd_total",
            "Cumulative estimated operational LLM cost in USD",
            ["strategy", "tenant_id"],
            registry=self.registry,
        )

        # 6. Multi-Tier Cache Telemetry (Hit vs Miss)
        self.cache_events_total = Counter(
            "rag_cache_events_total",
            "Total cache access events by tier and result",
            ["tier", "event"],
            registry=self.registry,
        )

        # 7. Operational Gauges: Active Sessions & Indexed Documents
        self.active_sessions = Gauge(
            "rag_active_sessions",
            "Current number of active conversation sessions",
            ["tenant_id"],
            registry=self.registry,
        )

        self.indexed_documents = Gauge(
            "rag_indexed_documents",
            "Total number of indexed documents in document store",
            ["tenant_id"],
            registry=self.registry,
        )

    def record_rag_request(
        self,
        strategy: str,
        tenant_id: str,
        status: str = "success",
        duration_seconds: float = 0.0,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cost_usd: float = 0.0,
        ttft_seconds: float | None = None,
    ) -> None:
        """Records a completed RAG request across RED, token, cost, and latency metrics."""
        strat = strategy or "Basic"
        tenant = tenant_id or "default_tenant"
        stat = status.lower()

        # Increment request counter
        self.requests_total.labels(strategy=strat, tenant_id=tenant, status=stat).inc()

        # Record latency
        if duration_seconds > 0:
            self.request_duration_seconds.labels(strategy=strat, tenant_id=tenant).observe(duration_seconds)

        # Record TTFT if available
        if ttft_seconds is not None and ttft_seconds > 0:
            self.ttft_seconds.labels(strategy=strat).observe(ttft_seconds)

        # Record tokens
        if prompt_tokens > 0:
            self.tokens_total.labels(type="prompt", strategy=strat, tenant_id=tenant).inc(prompt_tokens)
        if completion_tokens > 0:
            self.tokens_total.labels(type="completion", strategy=strat, tenant_id=tenant).inc(completion_tokens)

        # Record cost
        if cost_usd > 0:
            self.cost_usd_total.labels(strategy=strat, tenant_id=tenant).inc(cost_usd)

    def record_cache_event(self, tier: str, event: str) -> None:
        """Records a cache hit or miss event on a specific tier."""
        self.cache_events_total.labels(tier=tier.lower(), event=event.lower()).inc()

    def set_active_sessions(self, tenant_id: str, count: int) -> None:
        """Updates active conversation session gauge."""
        self.active_sessions.labels(tenant_id=tenant_id or "default_tenant").set(count)

    def set_indexed_documents(self, tenant_id: str, count: int) -> None:
        """Updates indexed document count gauge."""
        self.indexed_documents.labels(tenant_id=tenant_id or "default_tenant").set(count)

    def export_metrics(self) -> tuple[bytes, str]:
        """Generates Prometheus exposition format output and MIME content type."""
        return generate_latest(self.registry), CONTENT_TYPE_LATEST


# Singleton Provider
_global_prometheus_mgr: PrometheusMetricsManager | None = None
_mgr_lock = threading.Lock()


def get_prometheus_manager() -> PrometheusMetricsManager:
    """Returns process-wide PrometheusMetricsManager singleton."""
    global _global_prometheus_mgr
    if _global_prometheus_mgr is None:
        with _mgr_lock:
            if _global_prometheus_mgr is None:
                _global_prometheus_mgr = PrometheusMetricsManager()
    return _global_prometheus_mgr
