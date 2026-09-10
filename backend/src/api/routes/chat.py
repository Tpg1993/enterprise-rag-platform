"""Chat execution router handling RAG queries."""

import time
import uuid

from fastapi import APIRouter, Request
from src.api.schemas import ChatRequest, ChatResponse

from src.rag import RAGRequest, get_rag_strategy

router = APIRouter(tags=["Chat"])


@router.post("/chat", response_model=ChatResponse)
async def execute_chat(payload: ChatRequest, request: Request) -> ChatResponse:
    """Executes a chat completion query through the RAG strategy engine."""
    correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))

    start_time = time.perf_counter()

    from src.security.guardrails import PromptInjectionGuardrail

    guardrail = PromptInjectionGuardrail()
    sec_check = guardrail.inspect(payload.query)
    if not sec_check.is_safe:
        return ChatResponse(
            answer="⚠️ [SECURITY ALERT]: Malicious prompt injection instruction detected and intercepted. Query blocked by OWASP LLM security policy.",
            citations=[],
            sources=[],
            rag_strategy=f"{payload.rag_strategy} (Security Intercepted)",
            rag_version="1.0.0",
            framework="none",
            model="security-guardrail",
            latency_ms=1.2,
            ttft_ms=0.5,
            token_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            estimated_cost_usd=0.0,
            retrieval_count=0,
            reranked_count=0,
            cache_hit=False,
            trace_id=correlation_id,
        )

    from src.cache.service import get_cache_manager
    cache_mgr = get_cache_manager()

    cached_payload = cache_mgr.get_llm_response(
        prompt=payload.query,
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
        )

    # Route query through strategy (defaults to BasicRAGStrategy)
    strategy = get_rag_strategy(payload.rag_strategy)
    rag_req = RAGRequest(
        query=payload.query,
        tenant_id=payload.tenant_id,
        rag_strategy=payload.rag_strategy,
        max_context_tokens=payload.max_context_tokens,
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
        prompt=payload.query,
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

    return ChatResponse(
        answer=rag_res.answer,
        citations=citations,
        sources=sources,
        rag_strategy=rag_res.rag_strategy,
        rag_version="1.0.0",
        framework="none",
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


from pydantic import BaseModel


class SessionCreateRequest(BaseModel):
    user_id: str = "usr_default"
    tenant_id: str = "default_tenant"
    title: str = "New Conversation"


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

