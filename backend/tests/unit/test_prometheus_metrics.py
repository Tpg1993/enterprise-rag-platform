"""Unit tests for Prometheus Metrics & OpenTelemetry Services."""

import pytest
from prometheus_client import CollectorRegistry
from src.observability.otel_service import get_otel_tracer, init_opentelemetry, trace_span
from src.observability.prometheus_service import (
    PrometheusMetricsManager,
    get_prometheus_manager,
)


@pytest.fixture
def custom_prom_mgr():
    """Creates an isolated PrometheusMetricsManager with a dedicated registry."""
    registry = CollectorRegistry()
    return PrometheusMetricsManager(registry=registry)


def test_prometheus_metrics_registration(custom_prom_mgr):
    """Verifies that all standard RED, token, cost, and cache metrics are properly registered."""
    mgr = custom_prom_mgr
    assert mgr.requests_total is not None
    assert mgr.request_duration_seconds is not None
    assert mgr.ttft_seconds is not None
    assert mgr.tokens_total is not None
    assert mgr.cost_usd_total is not None
    assert mgr.cache_events_total is not None
    assert mgr.active_sessions is not None
    assert mgr.indexed_documents is not None


def test_record_rag_request(custom_prom_mgr):
    """Tests recording RAG requests across labels, duration, tokens, and costs."""
    mgr = custom_prom_mgr
    mgr.record_rag_request(
        strategy="Hybrid",
        tenant_id="tenant_alpha",
        status="success",
        duration_seconds=0.145,
        prompt_tokens=150,
        completion_tokens=50,
        cost_usd=0.00045,
        ttft_seconds=0.035,
    )

    data, content_type = mgr.export_metrics()
    text = data.decode("utf-8")

    assert "rag_requests_total" in text
    assert 'strategy="Hybrid"' in text
    assert 'tenant_id="tenant_alpha"' in text
    assert 'status="success"' in text
    assert "rag_request_duration_seconds" in text
    assert "rag_tokens_total" in text
    assert 'type="prompt"' in text
    assert 'type="completion"' in text
    assert "rag_cost_usd_total" in text
    assert "rag_ttft_seconds" in text


def test_record_cache_event(custom_prom_mgr):
    """Tests recording cache hit and miss events."""
    mgr = custom_prom_mgr
    mgr.record_cache_event(tier="retrieval", event="hit")
    mgr.record_cache_event(tier="llm_response", event="miss")

    data, _ = mgr.export_metrics()
    text = data.decode("utf-8")

    assert "rag_cache_events_total" in text
    assert 'tier="retrieval"' in text
    assert 'event="hit"' in text
    assert 'tier="llm_response"' in text
    assert 'event="miss"' in text


def test_operational_gauges(custom_prom_mgr):
    """Tests updating operational active sessions and indexed documents gauges."""
    mgr = custom_prom_mgr
    mgr.set_active_sessions(tenant_id="tenant_beta", count=7)
    mgr.set_indexed_documents(tenant_id="tenant_beta", count=42)

    data, _ = mgr.export_metrics()
    text = data.decode("utf-8")

    assert "rag_active_sessions" in text
    assert "7.0" in text
    assert "rag_indexed_documents" in text
    assert "42.0" in text


def test_metrics_export_mime_type(custom_prom_mgr):
    """Verifies that exported metrics conform to standard Prometheus MIME type."""
    _, content_type = custom_prom_mgr.export_metrics()
    assert "text/plain" in content_type


def test_prometheus_singleton_provider():
    """Tests process-wide Prometheus manager singleton."""
    mgr1 = get_prometheus_manager()
    mgr2 = get_prometheus_manager()
    assert mgr1 is mgr2


def test_opentelemetry_tracer_and_span():
    """Tests OpenTelemetry initialization and safe span context execution."""
    init_opentelemetry(service_name="test-rag-service")
    tracer = get_otel_tracer("test.pipeline")
    assert tracer is not None

    with trace_span("execute_rag_pipeline", attributes={"rag.strategy": "Adaptive", "tokens": 120}) as span:
        # Code executed within span context
        pass
