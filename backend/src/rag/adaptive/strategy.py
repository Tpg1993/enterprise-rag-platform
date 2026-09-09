"""Adaptive RAG Strategy with Query Classification and Dynamic Pipeline Routing.

Classifies incoming query complexity and intent to route execution to the 
optimal sub-strategy (Basic, Hybrid, Multi-Query, or Reranked).
"""

import logging
import time
import uuid

from src.llm import LLMProvider, get_llm_provider
from src.rag.base import BaseRAGStrategy, RAGRequest, RAGResponse
from src.rag.router import get_rag_strategy

logger = logging.getLogger(__name__)


class AdaptiveRAGStrategy(BaseRAGStrategy):
    """Adaptive RAG strategy analyzing query semantics to route execution dynamically."""

    def __init__(self, llm_provider: LLMProvider | None = None):
        self.llm_provider = llm_provider or get_llm_provider()

    async def _classify_query_intent(self, query: str) -> str:
        """Classifies query complexity into target strategy: 'BASIC', 'HYBRID', 'MULTI_QUERY', or 'RERANKED'."""
        system_prompt = (
            "You are an expert query classifier for an enterprise RAG system. "
            "Classify the input query into exactly one of these strategies:\n"
            "- BASIC: Simple, direct factual questions.\n"
            "- HYBRID: Queries containing specific keywords, acronyms, or codes.\n"
            "- MULTI_QUERY: Complex, multi-part, or ambiguous conceptual questions.\n"
            "- RERANKED: In-depth analytical questions requiring precise ranking.\n"
            "Output ONLY the category name in capital letters."
        )
        user_prompt = f"Query: {query}"

        try:
            res = await self.llm_provider.agenerate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.0,
                max_tokens=20,
            )
            intent = res.content.strip().upper()
            if intent in ("BASIC", "HYBRID", "MULTI_QUERY", "RERANKED"):
                return intent
        except Exception as e:
            logger.warning(f"Adaptive query classification failed ({e}). Defaulting to HYBRID.")

        # Heuristic fallback
        words = query.split()
        if len(words) > 10:
            return "MULTI_QUERY"
        elif any(char.isdigit() for char in query):
            return "HYBRID"
        return "BASIC"

    async def execute(self, request: RAGRequest) -> RAGResponse:
        start_time = time.perf_counter()

        # 1. Classify query intent
        target_strategy_name = await self._classify_query_intent(request.query)
        logger.info(f"Adaptive RAG routed query '{request.query[:40]}...' to '{target_strategy_name}'.")

        # 2. Delegate to target RAG strategy
        sub_strategy = get_rag_strategy(target_strategy_name)
        response = await sub_strategy.execute(request)

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        # Wrap response with Adaptive metadata
        return RAGResponse(
            query=request.query,
            answer=response.answer,
            citations=response.citations,
            rag_strategy=f"Adaptive ({target_strategy_name})",
            model=response.model,
            latency_ms=elapsed_ms,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            estimated_cost_usd=response.estimated_cost_usd,
            trace_id=response.trace_id,
            tenant_id=request.tenant_id,
        )
