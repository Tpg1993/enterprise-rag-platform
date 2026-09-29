import asyncio
import json
import time
import uuid

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from src.api.schemas import ChatRequest, ChatResponse
from src.rag import RAGRequest, get_rag_strategy

router = APIRouter(tags=["Chat"])


class SessionCreateRequest(BaseModel):
    user_id: str = "usr_default"
    tenant_id: str = "default_tenant"
    title: str = "New Conversation"


@router.post("/chat", response_model=ChatResponse)
async def execute_chat(payload: ChatRequest, request: Request) -> ChatResponse:
    """Executes a chat completion query through the RAG strategy engine."""
    correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))

    start_time = time.perf_counter()

    # Rate Limiting & Financial Budget Guardrails (Phase 32)
    from src.security.quotas import TenantQuotaService

    quota_svc = TenantQuotaService.get_instance()
    allowed, remaining_rpm, retry_after = quota_svc.check_rate_limit(payload.tenant_id)
    if not allowed:
        t_limit = quota_svc.get_tenant_config(payload.tenant_id).rate_limit_rpm
        detail_msg = (
            f"Rate limit exceeded for tenant '{payload.tenant_id}'. "
            f"Retry after {retry_after}s."
        )
        raise HTTPException(
            status_code=429,
            detail=detail_msg,
            headers={
                "X-RateLimit-Limit": str(t_limit),
                "X-RateLimit-Remaining": "0",
                "Retry-After": str(int(retry_after)),
            },
        )

    budget_ok, budget_reason, _ = quota_svc.check_budget(
        payload.tenant_id, estimated_tokens=500
    )
    if not budget_ok:
        raise HTTPException(
            status_code=429,
            detail=budget_reason or "Tenant budget quota exceeded.",
            headers={
                "X-RateLimit-Remaining": str(remaining_rpm),
                "X-Budget-Exceeded": "true",
            },
        )

    from src.security.opa_engine import OPAEvalRequest, get_opa_engine
    from src.storage.history import get_history_store

    opa_engine = get_opa_engine()
    user_role = payload.metadata.get("role", "USER") if payload.metadata else "USER"
    opa_res = await opa_engine.evaluate_async(
        OPAEvalRequest(
            query=payload.query,
            role=user_role,
            tenant_id=payload.tenant_id,
            rag_strategy=payload.rag_strategy,
        )
    )
    if not opa_res.allow:
        store = get_history_store()
        store.record_audit_event(
            event_type="SECURITY_BLOCK",
            user_id=payload.user_id,
            tenant_id=payload.tenant_id,
            action="OPA_BLOCK",
            resource="chat",
            status="BLOCKED",
            details={"query": payload.query, "reason": opa_res.block_reason},
        )
        blocked_msg = (
            f"⚠️ [SECURITY ALERT]: Query blocked by Zero Trust OPA Security Policy: "
            f"{opa_res.block_reason}"
        )
        return ChatResponse(
            answer=blocked_msg,
            citations=[],
            sources=[],
            rag_strategy=f"{payload.rag_strategy} (OPA Intercepted)",
            rag_version="1.0.0",
            framework="none",
            model="opa-security-guardrail",
            latency_ms=1.2,
            ttft_ms=0.5,
            token_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            estimated_cost_usd=0.0,
            retrieval_count=0,
            reranked_count=0,
            cache_hit=False,
            trace_id=correlation_id,
            pii_redacted=False,
            pii_count=0,
            security_verdict="BLOCKED",
        )

    # 2. Presidio PII Analysis & Redaction
    from src.security.pii import get_pii_redactor
    pii_redactor = get_pii_redactor()
    pii_report = pii_redactor.analyze_and_redact(payload.query)
    effective_query = pii_report.redacted_text if pii_report.has_pii else payload.query
    pii_redacted = pii_report.has_pii
    pii_count = pii_report.total_redacted

    from src.cache.service import get_cache_manager
    cache_mgr = get_cache_manager()

    cached_payload = cache_mgr.get_llm_response(
        prompt=effective_query,
        strategy=payload.rag_strategy,
        tenant_id=payload.tenant_id,
    )

    if cached_payload:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        from src.api.schemas import Citation
        citations = [Citation(**c) for c in cached_payload.get("citations", [])]

        from src.storage.history import get_history_store
        store = get_history_store()
        session_id = payload.session_id or f"sess_{payload.tenant_id}"
        store.save_chat_message(
            session_id=session_id,
            user_id=payload.user_id,
            tenant_id=payload.tenant_id,
            role="user",
            content=payload.query,
            rag_strategy=payload.rag_strategy,
        )
        store.save_chat_message(
            session_id=session_id,
            user_id="assistant",
            tenant_id=payload.tenant_id,
            role="assistant",
            content=cached_payload["answer"],
            rag_strategy=payload.rag_strategy,
            latency_ms=elapsed_ms,
            cost_usd=0.0,
            prompt_tokens=0,
            completion_tokens=0,
            citations=[c.model_dump() for c in citations],
        )

        from src.observability.prometheus_service import get_prometheus_manager
        prom_mgr = get_prometheus_manager()
        prom_mgr.record_rag_request(
            strategy=cached_payload.get("rag_strategy", payload.rag_strategy),
            tenant_id=payload.tenant_id,
            status="success",
            duration_seconds=elapsed_ms / 1000.0,
            prompt_tokens=0,
            completion_tokens=0,
            cost_usd=0.0,
            ttft_seconds=(elapsed_ms * 0.2) / 1000.0,
        )
        prom_mgr.record_cache_event(tier="llm_response", event="hit")

        return ChatResponse(
            answer=cached_payload["answer"],
            citations=citations,
            sources=[c.snippet for c in citations],
            rag_strategy=cached_payload.get("rag_strategy", payload.rag_strategy),
            rag_version="1.0.0",
            framework="none",
            model=cached_payload.get("model", "sarvam-105b"),
            latency_ms=elapsed_ms,
            ttft_ms=elapsed_ms * 0.2,
            token_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            estimated_cost_usd=0.0,
            retrieval_count=len(citations),
            reranked_count=0,
            cache_hit=True,
            trace_id=f"cache_{correlation_id}",
            pii_redacted=pii_redacted,
            pii_count=pii_count,
            security_verdict="ALLOWED",
        )

    # Route query through strategy (defaults to BasicRAGStrategy)
    strategy = get_rag_strategy(payload.rag_strategy)
    rag_req = RAGRequest(
        query=effective_query,
        tenant_id=payload.tenant_id,
        rag_strategy=payload.rag_strategy,
        max_context_tokens=payload.max_context_tokens,
        enable_compression=payload.enable_compression,
        compression_target_ratio=payload.compression_target_ratio,
    )
    rag_res = await strategy.execute(rag_req)

    elapsed_ms = (time.perf_counter() - start_time) * 1000

    from src.observability.tracing import Tracer
    Tracer.record_span(
        trace_id=rag_res.trace_id,
        name=f"RAG_Execution_{rag_res.rag_strategy}",
        rag_strategy=rag_res.rag_strategy,
        latency_ms=elapsed_ms,
        tenant_id=payload.tenant_id,
        user_id=payload.user_id,
        metadata={
            "query": payload.query,
            "answer": rag_res.answer,
            "prompt_tokens": rag_res.prompt_tokens,
            "completion_tokens": rag_res.completion_tokens,
            "total_tokens": rag_res.prompt_tokens + rag_res.completion_tokens,
            "estimated_cost_usd": rag_res.estimated_cost_usd,
            "model": rag_res.model,
            "citations_count": len(rag_res.citations),
        },
    )

    from src.api.schemas import Citation

    citations = [
        Citation(
            document_id=c.document_id,
            chunk_id=c.chunk_id,
            source=c.filename,
            page=c.page_number,
            section=c.section_title or None,
            snippet=c.content_snippet,
            relevance_score=c.relevance_score,
            bbox=c.bbox,
            page_dimensions=c.page_dimensions,
        )
        for c in rag_res.citations
    ]
    from src.storage.history import get_history_store

    store = get_history_store()
    session_id = payload.session_id or f"sess_{payload.tenant_id}"
    store.save_chat_message(
        session_id=session_id,
        user_id=payload.user_id,
        tenant_id=payload.tenant_id,
        role="user",
        content=payload.query,
        rag_strategy=rag_res.rag_strategy,
    )
    store.save_chat_message(
        session_id=session_id,
        user_id="assistant",
        tenant_id=payload.tenant_id,
        role="assistant",
        content=rag_res.answer,
        rag_strategy=rag_res.rag_strategy,
        latency_ms=elapsed_ms,
        cost_usd=rag_res.estimated_cost_usd,
        prompt_tokens=rag_res.prompt_tokens,
        completion_tokens=rag_res.completion_tokens,
        citations=[c.model_dump() for c in citations],
    )

    sources = [c.content_snippet for c in rag_res.citations]

    # Populate Tier 3 LLM Response Cache for subsequent identical queries
    cache_mgr.set_llm_response(
        prompt=effective_query,
        strategy=payload.rag_strategy,
        tenant_id=payload.tenant_id,
        response_dict={
            "answer": rag_res.answer,
            "citations": [c.model_dump() for c in citations],
            "model": rag_res.model,
            "rag_strategy": rag_res.rag_strategy,
        },
        ttl=3600,
    )

    # Record Prometheus metrics for strategy execution
    from src.observability.prometheus_service import get_prometheus_manager
    prom_mgr = get_prometheus_manager()
    prom_mgr.record_rag_request(
        strategy=rag_res.rag_strategy,
        tenant_id=payload.tenant_id,
        status="success",
        duration_seconds=elapsed_ms / 1000.0,
        prompt_tokens=rag_res.prompt_tokens,
        completion_tokens=rag_res.completion_tokens,
        cost_usd=rag_res.estimated_cost_usd,
        ttft_seconds=(elapsed_ms * 0.25) / 1000.0,
    )

    quota_svc.record_usage(
        tenant_id=payload.tenant_id,
        prompt_tokens=rag_res.prompt_tokens,
        completion_tokens=rag_res.completion_tokens,
        cost_usd=rag_res.estimated_cost_usd,
    )
    strat_name = rag_res.rag_strategy
    agentic_keywords = (
        "ADAPTIVE", "CORRECTIVE", "SELF-RAG", "REACT", "GRAPH", "SQL", "AGENTIC"
    )
    framework = "langgraph" if any(k in strat_name.upper() for k in agentic_keywords) else "none"

    return ChatResponse(
        answer=rag_res.answer,
        citations=citations,
        sources=sources,
        rag_strategy=rag_res.rag_strategy,
        rag_version="1.0.0",
        framework=framework,
        model=rag_res.model,
        latency_ms=elapsed_ms,
        ttft_ms=elapsed_ms * 0.25,
        token_usage={
            "prompt_tokens": rag_res.prompt_tokens,
            "completion_tokens": rag_res.completion_tokens,
            "total_tokens": rag_res.prompt_tokens + rag_res.completion_tokens,
        },
        estimated_cost_usd=rag_res.estimated_cost_usd,
        retrieval_count=len(rag_res.citations),
        reranked_count=0,
        cache_hit=False,
        trace_id=rag_res.trace_id or correlation_id,
        pii_redacted=pii_redacted,
        pii_count=pii_count,
        security_verdict="ALLOWED",
        compression_ratio=rag_res.compression_ratio,
        tokens_saved=rag_res.tokens_saved,
    )


@router.post("/chat/stream")
async def execute_chat_stream(payload: ChatRequest, request: Request):
    """Executes chat completion with Server-Sent Events (SSE) token streaming

    and inter-token latency (ITL) tracking.
    """
    correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    start_time = time.perf_counter()

    async def event_generator():
        # Rate Limiting & Financial Budget Guardrails (Phase 32)
        from src.security.quotas import TenantQuotaService

        quota_svc = TenantQuotaService.get_instance()
        allowed, remaining_rpm, retry_after = quota_svc.check_rate_limit(payload.tenant_id)
        if not allowed:
            err_msg = (
                f"Rate limit exceeded for tenant '{payload.tenant_id}'. "
                f"Retry after {retry_after}s."
            )
            event_data = {
                "type": "error",
                "error": err_msg,
                "security_verdict": "BLOCKED",
                "done": True,
            }
            yield f"data: {json.dumps(event_data)}\n\n"
            return

        budget_ok, budget_reason, _ = quota_svc.check_budget(
            payload.tenant_id, estimated_tokens=500
        )
        if not budget_ok:
            event_data = {
                "type": "error",
                "error": budget_reason or "Tenant budget quota exceeded.",
                "security_verdict": "BLOCKED",
                "done": True,
            }
            yield f"data: {json.dumps(event_data)}\n\n"
            return

        # 1. OPA Security Evaluation
        from src.security.opa_engine import OPAEvalRequest, get_opa_engine
        from src.storage.history import get_history_store

        store = get_history_store()
        opa_engine = get_opa_engine()
        user_role = payload.metadata.get("role", "USER") if payload.metadata else "USER"
        opa_res = await opa_engine.evaluate_async(
            OPAEvalRequest(
                query=payload.query,
                role=user_role,
                tenant_id=payload.tenant_id,
                rag_strategy=payload.rag_strategy,
            )
        )
        if not opa_res.allow:
            store.record_audit_event(
                event_type="SECURITY_BLOCK",
                user_id=payload.user_id,
                tenant_id=payload.tenant_id,
                action="OPA_BLOCK",
                resource="chat_stream",
                status="BLOCKED",
                details={"query": payload.query, "reason": opa_res.block_reason},
            )
            blocked_msg = (
                f"⚠️ [SECURITY ALERT]: Query blocked by Zero Trust OPA Security Policy: "
                f"{opa_res.block_reason}"
            )
            event_data = {
                "type": "error",
                "error": blocked_msg,
                "security_verdict": "BLOCKED",
                "done": True,
            }
            yield f"data: {json.dumps(event_data)}\n\n"
            return

        # 2. Presidio PII Analysis & Redaction
        from src.security.pii import get_pii_redactor

        pii_redactor = get_pii_redactor()
        pii_report = pii_redactor.analyze_and_redact(payload.query)
        effective_query = pii_report.redacted_text if pii_report.has_pii else payload.query
        pii_redacted = pii_report.has_pii
        pii_count = pii_report.total_redacted
        if pii_redacted:
            store.record_audit_event(
                event_type="PII_DETECTED",
                user_id=payload.user_id,
                tenant_id=payload.tenant_id,
                action="PII_REDACT",
                resource="chat_stream",
                status="REDACTED",
                details={"total_redacted": pii_count},
            )

        # 3. Check Tier 3 LLM Response Cache
        from src.cache.service import get_cache_manager

        cache_mgr = get_cache_manager()
        cached_payload = cache_mgr.get_llm_response(
            prompt=effective_query,
            strategy=payload.rag_strategy,
            tenant_id=payload.tenant_id,
        )

        from src.api.schemas import Citation

        if cached_payload:
            answer = cached_payload.get("answer", "")
            citations = [Citation(**c) for c in cached_payload.get("citations", [])]
            words = answer.split(" ")
            last_time = time.perf_counter()
            first_token_time = None
            itls = []

            for i, w in enumerate(words):
                now = time.perf_counter()
                if first_token_time is None:
                    first_token_time = now
                itl_ms = round((now - last_time) * 1000, 2)
                itls.append(itl_ms)
                last_time = now
                token_text = w + (" " if i < len(words) - 1 else "")
                chunk_data = {
                    "type": "token",
                    "token": token_text,
                    "itl_ms": itl_ms,
                    "done": False,
                }
                yield f"data: {json.dumps(chunk_data)}\n\n"
                await asyncio.sleep(0.01)

            elapsed_ms = (time.perf_counter() - start_time) * 1000
            ttft_ms = round((first_token_time - start_time) * 1000, 2) if first_token_time else 1.0
            avg_itl = round(sum(itls) / max(len(itls), 1), 2)

            session_id = payload.session_id or f"sess_{payload.tenant_id}"
            store.save_chat_message(
                session_id=session_id,
                user_id=payload.user_id,
                tenant_id=payload.tenant_id,
                role="user",
                content=payload.query,
                rag_strategy=payload.rag_strategy,
            )
            store.save_chat_message(
                session_id=session_id,
                user_id="assistant",
                tenant_id=payload.tenant_id,
                role="assistant",
                content=answer,
                rag_strategy=payload.rag_strategy,
                latency_ms=elapsed_ms,
                cost_usd=0.0,
                prompt_tokens=0,
                completion_tokens=0,
                citations=[c.model_dump() for c in citations],
            )

            done_data = {
                "type": "done",
                "answer": answer,
                "citations": [c.model_dump() for c in citations],
                "sources": [c.snippet for c in citations],
                "rag_strategy": cached_payload.get("rag_strategy", payload.rag_strategy),
                "rag_version": "1.0.0",
                "framework": "none",
                "model": cached_payload.get("model", "sarvam-105b"),
                "latency_ms": round(elapsed_ms, 2),
                "ttft_ms": ttft_ms,
                "avg_itl_ms": avg_itl,
                "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "estimated_cost_usd": 0.0,
                "retrieval_count": len(citations),
                "cache_hit": True,
                "trace_id": f"cache_{correlation_id}",
                "pii_redacted": pii_redacted,
                "pii_count": pii_count,
                "security_verdict": "ALLOWED",
                "done": True,
            }
            yield f"data: {json.dumps(done_data)}\n\n"
            return

        # 4. Execute RAG Strategy
        strategy = get_rag_strategy(payload.rag_strategy)
        rag_req = RAGRequest(
            query=effective_query,
            tenant_id=payload.tenant_id,
            rag_strategy=payload.rag_strategy,
            max_context_tokens=payload.max_context_tokens,
            enable_compression=payload.enable_compression,
            compression_target_ratio=payload.compression_target_ratio,
        )
        rag_res = await strategy.execute(rag_req)

        citations = [
            Citation(
                document_id=c.document_id,
                chunk_id=c.chunk_id,
                source=c.filename,
                page=c.page_number,
                section=c.section_title or None,
                snippet=c.content_snippet,
                relevance_score=c.relevance_score,
                bbox=c.bbox,
                page_dimensions=c.page_dimensions,
            )
            for c in rag_res.citations
        ]

        words = rag_res.answer.split(" ")
        last_time = time.perf_counter()
        first_token_time = None
        itls = []

        for i, w in enumerate(words):
            now = time.perf_counter()
            if first_token_time is None:
                first_token_time = now
            itl_ms = round((now - last_time) * 1000, 2)
            itls.append(itl_ms)
            last_time = now
            token_text = w + (" " if i < len(words) - 1 else "")
            chunk_data = {
                "type": "token",
                "token": token_text,
                "itl_ms": itl_ms,
                "done": False,
            }
            yield f"data: {json.dumps(chunk_data)}\n\n"
            await asyncio.sleep(0.015)

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        ttft_ms = round((first_token_time - start_time) * 1000, 2) if first_token_time else 1.0
        avg_itl = round(sum(itls) / max(len(itls), 1), 2)

        from src.observability.tracing import Tracer

        Tracer.record_span(
            trace_id=rag_res.trace_id,
            name=f"RAG_Execution_{rag_res.rag_strategy}",
            rag_strategy=rag_res.rag_strategy,
            latency_ms=elapsed_ms,
            tenant_id=payload.tenant_id,
            user_id=payload.user_id,
            metadata={
                "query": payload.query,
                "answer": rag_res.answer,
                "prompt_tokens": rag_res.prompt_tokens,
                "completion_tokens": rag_res.completion_tokens,
                "total_tokens": rag_res.prompt_tokens + rag_res.completion_tokens,
                "estimated_cost_usd": rag_res.estimated_cost_usd,
                "model": rag_res.model,
                "streaming": True,
            },
        )

        session_id = payload.session_id or f"sess_{payload.tenant_id}"
        store.save_chat_message(
            session_id=session_id,
            user_id=payload.user_id,
            tenant_id=payload.tenant_id,
            role="user",
            content=payload.query,
            rag_strategy=rag_res.rag_strategy,
        )
        store.save_chat_message(
            session_id=session_id,
            user_id="assistant",
            tenant_id=payload.tenant_id,
            role="assistant",
            content=rag_res.answer,
            rag_strategy=rag_res.rag_strategy,
            latency_ms=elapsed_ms,
            cost_usd=rag_res.estimated_cost_usd,
            prompt_tokens=rag_res.prompt_tokens,
            completion_tokens=rag_res.completion_tokens,
            citations=[c.model_dump() for c in citations],
        )

        cache_mgr.set_llm_response(
            prompt=effective_query,
            strategy=payload.rag_strategy,
            tenant_id=payload.tenant_id,
            response_dict={
                "answer": rag_res.answer,
                "citations": [c.model_dump() for c in citations],
                "model": rag_res.model,
                "rag_strategy": rag_res.rag_strategy,
            },
            ttl=3600,
        )

        from src.observability.prometheus_service import get_prometheus_manager

        prom_mgr = get_prometheus_manager()
        prom_mgr.record_rag_request(
            strategy=rag_res.rag_strategy,
            tenant_id=payload.tenant_id,
            status="success",
            duration_seconds=elapsed_ms / 1000.0,
            prompt_tokens=rag_res.prompt_tokens,
            completion_tokens=rag_res.completion_tokens,
            cost_usd=rag_res.estimated_cost_usd,
            ttft_seconds=ttft_ms / 1000.0,
        )

        quota_svc.record_usage(
            tenant_id=payload.tenant_id,
            prompt_tokens=rag_res.prompt_tokens,
            completion_tokens=rag_res.completion_tokens,
            cost_usd=rag_res.estimated_cost_usd,
        )

        strat_name = rag_res.rag_strategy
        framework = (
            "langgraph"
            if any(
                k in strat_name.upper()
                for k in (
                    "ADAPTIVE",
                    "CORRECTIVE",
                    "SELF-RAG",
                    "REACT",
                    "GRAPH",
                    "SQL",
                    "AGENTIC",
                )
            )
            else "none"
        )

        done_data = {
            "type": "done",
            "answer": rag_res.answer,
            "citations": [c.model_dump() for c in citations],
            "sources": [c.content_snippet for c in rag_res.citations],
            "rag_strategy": rag_res.rag_strategy,
            "rag_version": "1.0.0",
            "framework": framework,
            "model": rag_res.model,
            "latency_ms": round(elapsed_ms, 2),
            "ttft_ms": ttft_ms,
            "avg_itl_ms": avg_itl,
            "token_usage": {
                "prompt_tokens": rag_res.prompt_tokens,
                "completion_tokens": rag_res.completion_tokens,
                "total_tokens": rag_res.prompt_tokens + rag_res.completion_tokens,
            },
            "estimated_cost_usd": rag_res.estimated_cost_usd,
            "retrieval_count": len(rag_res.citations),
            "cache_hit": False,
            "trace_id": rag_res.trace_id or correlation_id,
            "pii_redacted": pii_redacted,
            "pii_count": pii_count,
            "security_verdict": "ALLOWED",
            "compression_ratio": rag_res.compression_ratio,
            "tokens_saved": rag_res.tokens_saved,
            "done": True,
        }
        yield f"data: {json.dumps(done_data)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/chat/history")
async def get_chat_history(
    session_id: str,
    tenant_id: str = "default_tenant",
):
    """Returns conversation history for a given session."""
    from src.storage.history import get_history_store

    messages = get_history_store().get_chat_history(session_id=session_id, tenant_id=tenant_id)
    return {
        "session_id": session_id,
        "tenant_id": tenant_id,
        "total_messages": len(messages),
        "messages": messages,
    }


@router.get("/chat/sessions")
async def list_chat_sessions(
    tenant_id: str = "default_tenant",
    user_id: str | None = None,
    limit: int = 50,
):
    """Lists saved chat sessions."""
    from src.storage.history import get_history_store

    sessions = get_history_store().list_sessions(tenant_id=tenant_id, user_id=user_id, limit=limit)
    return {
        "tenant_id": tenant_id,
        "total_sessions": len(sessions),
        "sessions": sessions,
    }


@router.post("/chat/sessions", status_code=201)
async def create_chat_session(payload: SessionCreateRequest):
    """Creates a new persistent conversation session."""
    from src.storage.history import get_history_store

    session = get_history_store().create_session(
        user_id=payload.user_id,
        tenant_id=payload.tenant_id,
        title=payload.title,
    )
    return {
        "status": "SUCCESS",
        "session": session,
    }

