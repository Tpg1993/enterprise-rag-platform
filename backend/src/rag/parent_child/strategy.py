"""Parent-Child Hierarchical RAG Strategy.

Retrieves precise child vector matches and resolves them to their surrounding 
parent background context before prompt construction.
"""

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


class ParentChildRAGStrategy(BaseRAGStrategy):
    """Parent-Child Hierarchical RAG strategy resolving child vector matches to parent context."""

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

    async def execute(self, request: RAGRequest) -> RAGResponse:
        start_time = time.perf_counter()
        trace_id = f"trace_{uuid.uuid4().hex[:12]}"

        # 1. Embed query
        query_vector = self.embedding_provider.embed_query(request.query)

        # 2. Vector search on child chunks
        child_hits = self.vector_store.search(
            query_vector=query_vector,
            tenant_id=request.tenant_id,
            top_k=request.top_k,
        )

        # 3. Resolve Child Hits to Parent Chunks
        resolved_hits: list[dict[str, Any]] = []
        seen_parents: set[str] = set()

        for hit in child_hits:
            payload = hit.get("payload", {})
            meta = payload.get("metadata", {}) if isinstance(payload.get("metadata"), dict) else {}
            parent_id = payload.get("parent_id") or meta.get("parent_id")
            parent_content = payload.get("parent_content") or meta.get("parent_content")

            # Check if this hit is already a parent or has resolvable parent content
            if parent_id and parent_id in seen_parents:
                continue

            if parent_id:
                seen_parents.add(parent_id)

            resolved_content = parent_content or hit.get("content", "") or payload.get("content", "")
            resolved_hit = dict(hit)
            resolved_hit["content"] = resolved_content
            if "payload" in resolved_hit:
                resolved_hit["payload"]["content"] = resolved_content

            resolved_hits.append(resolved_hit)

        # 4. Context Assembly & Deduplication
        context_str, citations = self.context_builder.build_context(
            resolved_hits, max_context_tokens=request.max_context_tokens
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
            f"Parent-Child RAG executed in {elapsed_ms:.1f}ms | "
            f"Child Hits: {len(child_hits)} -> Resolved Parents: {len(resolved_hits)} | Cost: ${cost:.5f}"
        )

        return RAGResponse(
            query=request.query,
            answer=llm_response.content,
            citations=citations,
            rag_strategy="Parent-Child",
            model=llm_response.model_name,
            latency_ms=elapsed_ms,
            prompt_tokens=llm_response.prompt_tokens,
            completion_tokens=llm_response.completion_tokens,
            estimated_cost_usd=cost,
            trace_id=trace_id,
            tenant_id=request.tenant_id,
        )
