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
    sources = [c.content_snippet for c in rag_res.citations]

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
