"""OpenTelemetry Distributed Tracing Service for Enterprise RAG & Agentic AI Platform.

Initializes OTel TracerProvider and provides context managers for span tracing across
ingestion, retrieval, reranking, and LLM generation pipelines.
"""

import contextlib
import logging
import os
from typing import Any, Generator

logger = logging.getLogger(__name__)

_is_otel_initialized = False
_otel_tracer = None


def init_opentelemetry(service_name: str = "enterprise-rag-platform") -> None:
    """Initializes OpenTelemetry TracerProvider with optional OTLP exporter."""
    global _is_otel_initialized, _otel_tracer
    if _is_otel_initialized:
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

        resource = Resource.create({
            "service.name": service_name,
            "service.version": "3.2.0",
            "deployment.environment": os.getenv("ENVIRONMENT", "development"),
        })

        provider = TracerProvider(resource=resource)

        # Connect OTLP gRPC/HTTP exporter if endpoint is configured
        otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        if otlp_endpoint:
            try:
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
                otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
                provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
                logger.info(f"OpenTelemetry connected to OTLP collector at {otlp_endpoint}.")
            except Exception as exp_err:
                logger.warning(f"Could not initialize OTLP exporter: {exp_err}")

        trace.set_tracer_provider(provider)
        _otel_tracer = trace.get_tracer(service_name)
        _is_otel_initialized = True
        logger.info(f"OpenTelemetry TracerProvider initialized for '{service_name}'.")
    except Exception as e:
        logger.warning(f"OpenTelemetry initialization skipped/failed: {e}")
        _is_otel_initialized = False


def get_otel_tracer(name: str = "rag.pipeline"):
    """Returns initialized OpenTelemetry tracer or a fallback object."""
    global _otel_tracer
    if not _is_otel_initialized:
        init_opentelemetry()
    if _otel_tracer is not None:
        return _otel_tracer

    try:
        from opentelemetry import trace
        return trace.get_tracer(name)
    except Exception:
        return None


@contextlib.contextmanager
def trace_span(
    span_name: str,
    attributes: dict[str, Any] | None = None
) -> Generator[Any, None, None]:
    """Context manager for tracing RAG operations with OpenTelemetry."""
    tracer = get_otel_tracer()
    if tracer is not None:
        with tracer.start_as_current_span(span_name) as span:
            if attributes:
                for k, v in attributes.items():
                    if isinstance(v, (str, bool, int, float)):
                        span.set_attribute(k, v)
                    else:
                        span.set_attribute(k, str(v))
            yield span
    else:
        # No-op fallback when OTel is not active
        yield None
