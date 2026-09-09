import logging
import os
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

try:
    from langsmith import Client, traceable
    _ls_client: Client | None = None

    def get_langsmith_client() -> Client | None:
        global _ls_client
        if _ls_client is None:
            api_key = os.environ.get("LANGCHAIN_API_KEY")
            if api_key:
                try:
                    _ls_client = Client()
                except Exception as e:
                    logger.warning(f"Failed to initialize LangSmith client: {e}")
        return _ls_client
except ImportError:
    traceable = None

    def get_langsmith_client() -> None:
        return None


class TraceSpan(BaseModel):
    """Structured execution trace span matching LangSmith metadata specifications."""

    trace_id: str
    request_id: str
    name: str
    rag_strategy: str
    latency_ms: float
    tenant_id: str
    user_id: str
    llm_provider: str = "sarvam"
    llm_model: str = "sarvam-105b"
    rag_version: str = "1.7.0"
    status: str = "SUCCESS"
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)


_trace_store: list[TraceSpan] = []
MAX_TRACE_STORE_SIZE = 100


class Tracer:
    """Manages execution trace lifecycle and records metadata for UI inspection and LangSmith export."""

    @staticmethod
    def start_trace(
        name: str,
        rag_strategy: str,
        tenant_id: str = "tenant_default",
        user_id: str = "usr_default",
    ) -> str:
        """Starts a new execution trace and returns trace_id."""
        trace_id = f"trace_{rag_strategy.lower()}_{uuid.uuid4().hex[:12]}"
        logger.info(f"Started trace '{trace_id}' for strategy '{rag_strategy}'.")
        return trace_id

    @staticmethod
    def record_span(
        trace_id: str,
        name: str,
        rag_strategy: str,
        latency_ms: float,
        tenant_id: str = "tenant_default",
        user_id: str = "usr_default",
        status: str = "SUCCESS",
        metadata: dict[str, Any] | None = None,
    ) -> TraceSpan:
        """Records completed execution span into trace repository and exports to LangSmith."""
        span_meta = metadata or {}
        span = TraceSpan(
            trace_id=trace_id,
            request_id=f"req_{uuid.uuid4().hex[:8]}",
            name=name,
            rag_strategy=rag_strategy,
            latency_ms=round(latency_ms, 2),
            tenant_id=tenant_id,
            user_id=user_id,
            status=status,
            metadata=span_meta,
        )

        global _trace_store
        _trace_store.append(span)
        if len(_trace_store) > MAX_TRACE_STORE_SIZE:
            _trace_store.pop(0)

        # Export run trace to LangSmith if API key & tracing enabled
        client = get_langsmith_client()
        if client and os.environ.get("LANGCHAIN_TRACING_V2", "").lower() == "true":
            try:
                project_name = os.environ.get("LANGCHAIN_PROJECT", "enterprise-rag-platform")
                client.create_run(
                    name=span.name,
                    run_type="chain",
                    inputs={
                        "trace_id": trace_id,
                        "rag_strategy": rag_strategy,
                        "tenant_id": tenant_id,
                        "user_id": user_id,
                        "query": span_meta.get("query", ""),
                    },
                    outputs={
                        "status": status,
                        "latency_ms": span.latency_ms,
                        "answer": span_meta.get("answer", ""),
                        "prompt_tokens": span_meta.get("prompt_tokens", 0),
                        "completion_tokens": span_meta.get("completion_tokens", 0),
                        "total_tokens": span_meta.get("total_tokens", 0),
                        "estimated_cost_usd": span_meta.get("estimated_cost_usd", 0.0),
                    },
                    project_name=project_name,
                    extra={
                        "metadata": {
                            "llm_provider": span.llm_provider,
                            "llm_model": span.llm_model,
                            "rag_strategy": span.rag_strategy,
                            "rag_version": span.rag_version,
                            "tenant_id": span.tenant_id,
                            "user_id": span.user_id,
                            "request_id": span.request_id,
                        }
                    },
                )
            except Exception as ex:
                logger.warning(f"Failed to export trace span to LangSmith: {ex}")

        logger.info(f"Recorded span '{span.name}' [{span.status}] in {span.latency_ms}ms.")
        return span

    @staticmethod
    def get_recent_traces(limit: int = 20, tenant_id: str | None = None) -> list[TraceSpan]:
        """Returns recent recorded execution trace spans filtered by tenant_id."""
        spans = list(_trace_store)
        if tenant_id:
            spans = [s for s in spans if s.tenant_id == tenant_id]
        return spans[::-1][:limit]

