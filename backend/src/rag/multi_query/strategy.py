"""Multi-Query Expansion RAG Strategy.

Generates 3 perspective variations of an input query, executes parallel 
vector search streams, fuses results using Reciprocal Rank Fusion (RRF), 
and synthesizes a grounded response using Sarvam AI.
"""

import asyncio
import logging
import time
import uuid
from typing import Any

from src.config.pricing import calculate_llm_cost
from src.context.builder import ContextBuilder
from src.embeddings import BaseEmbeddingProvider, get_embedding_provider
from src.llm import LLMProvider, get_llm_provider
from src.prompting.builder import PromptBuilder
from src.rag.base import BaseRAGStrategy, RAGRequest, RAGResponse
from src.retrieval.vector_store import QdrantVectorStore, get_vector_store

logger = logging.getLogger(__name__)


def reciprocal_rank_fusion_multi_query(
    hits_per_query: list[list[dict[str, Any]]], rrf_k: int = 60
) -> list[dict[str, Any]]:
    """Applies Reciprocal Rank Fusion (RRF) math across multiple query retrieval streams."""
    rrf_scores: dict[str, float] = {}
    doc_map: dict[str, dict[str, Any]] = {}

    for query_hits in hits_per_query:
        for rank, hit in enumerate(query_hits):
            payload = hit.get("payload", {})
            chunk_id = hit.get("chunk_id") or payload.get("chunk_id") or f"hit_{rank}"

            if chunk_id not in doc_map:
                doc_map[chunk_id] = hit
                rrf_scores[chunk_id] = 0.0

            rrf_scores[chunk_id] += 1.0 / (rrf_k + rank + 1)

    sorted_chunk_ids = sorted(rrf_scores.keys(), key=lambda cid: rrf_scores[cid], reverse=True)
    fused_results: list[dict[str, Any]] = []

    for cid in sorted_chunk_ids:
        item = dict(doc_map[cid])
        item["score"] = round(rrf_scores[cid], 4)
        fused_results.append(item)

    return fused_results


class MultiQueryRAGStrategy(BaseRAGStrategy):
    """Multi-Query Expansion RAG strategy executing multi-perspective parallel search and RRF fusion."""

    def __init__(
        self,
        embedding_provider: BaseEmbeddingProvider | None = None,
        vector_store: QdrantVectorStore | None = None,
        llm_provider: LLMProvider | None = None,
        context_builder: ContextBuilder | None = None,
        prompt_builder: PromptBuilder | None = None,
    ):
        self.embedding_provider = embedding_provider or get_embedding_provider()
        self.vector_store = vector_store or get_vector_store()
        self.llm_provider = llm_provider or get_llm_provider()
        self.context_builder = context_builder or ContextBuilder()
        self.prompt_builder = prompt_builder or PromptBuilder()

    async def _generate_query_variations(self, user_query: str) -> list[str]:
        """Prompts LLM to generate 3 alternative perspective variations of user query."""
        system_prompt = (
            "You are an AI search query assistant. Given a user query, generate exactly 3 alternative "
            "search query variations from different technical perspectives to improve document retrieval. "
            "Output each query variation on a separate new line without numbers, bullet points, or commentary."
        )
        user_prompt = f"User Query: {user_query}"

        try:
            res = await self.llm_provider.agenerate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.7,
                max_tokens=256,
            )
            content = res.content or ""
            lines = [line.strip() for line in content.split("\n") if line.strip()]
            variations = [line for line in lines if not line.startswith(("#", "-", "*"))][:3]
            if len(variations) < 3:
                variations = [
                    f"{user_query} technical details",
                    f"{user_query} setup and specifications",
                    f"{user_query} guidelines and overview",
                ][:3]
            return variations
        except Exception as e:
            logger.warning(f"Failed to generate query variations via LLM: {e}. Using fallback variations.")
            return [
                f"{user_query} technical details",
                f"{user_query} setup and specifications",
                f"{user_query} guidelines and overview",
            ]

    async def execute(self, request: RAGRequest) -> RAGResponse:
        start_time = time.perf_counter()
        trace_id = f"trace_{uuid.uuid4().hex[:12]}"

        # 1. Generate 3 query variations
        variations = await self._generate_query_variations(request.query)
        all_queries = [request.query] + variations

        # 2. Parallel Embedding & Search Streams via asyncio.gather
        async def _search_single_query(query_text: str) -> list[dict[str, Any]]:
            query_vector = self.embedding_provider.embed_query(query_text)
            return self.vector_store.search(
                query_vector=query_vector,
                tenant_id=request.tenant_id,
                top_k=request.top_k,
            )

        search_tasks = [_search_single_query(q) for q in all_queries]
        hits_per_query: list[list[dict[str, Any]]] = await asyncio.gather(*search_tasks)

        # 3. Reciprocal Rank Fusion (RRF) across all query streams
        fused_hits = reciprocal_rank_fusion_multi_query(hits_per_query, rrf_k=60)

        # 4. Context Assembly & Deduplication
        context_str, citations = self.context_builder.build_context(
            fused_hits, max_context_tokens=request.max_context_tokens
        )

        # 5. Prompt Construction (OWASP XML isolation & grounding rules)
        prompts = self.prompt_builder.build_prompt(request.query, context_str)

        # 6. LLM Completion via Sarvam AI
        llm_response = await self.llm_provider.agenerate(
            prompt=prompts["user"],
            system_prompt=prompts["system"],
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        cost = calculate_llm_cost(
            model=llm_response.model_name,
            prompt_tokens=llm_response.prompt_tokens,
            completion_tokens=llm_response.completion_tokens,
        )

        logger.info(
            f"Multi-Query RAG executed in {elapsed_ms:.1f}ms | "
            f"Queries: {len(all_queries)} | Fused Hits: {len(fused_hits)} | Cost: ${cost:.5f}"
        )

        return RAGResponse(
            query=request.query,
            answer=llm_response.content,
            citations=citations,
            rag_strategy="Multi-Query",
            model=llm_response.model_name,
            latency_ms=elapsed_ms,
            prompt_tokens=llm_response.prompt_tokens,
            completion_tokens=llm_response.completion_tokens,
            estimated_cost_usd=cost,
            trace_id=trace_id,
            tenant_id=request.tenant_id,
        )
