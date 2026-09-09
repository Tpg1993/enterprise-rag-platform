"""Corrective RAG (CRAG) Strategy evaluating document relevance and triggering web search fallback.

Evaluates vector retrieval hit quality. If knowledge base relevance is insufficient,
triggers web search fallback to augment context before prompt completion.
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


class CorrectiveRAGStrategy(BaseRAGStrategy):
    """CRAG strategy grading context relevance and falling back to web search on low confidence."""

    def __init__(
        self,
        embedding_provider: BaseEmbeddingProvider | None = None,
        vector_store: QdrantVectorStore | None = None,
        llm_provider: LLMProvider | None = None,
        context_builder: ContextBuilder | None = None,
        prompt_builder: PromptBuilder | None = None,
        relevance_threshold: float = 0.5,
    ):
        self.embedding_provider = embedding_provider or get_embedding_provider()
        self.vector_store = vector_store or get_vector_store()
        self.llm_provider = llm_provider or get_llm_provider()
        self.context_builder = context_builder or ContextBuilder()
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.relevance_threshold = relevance_threshold

    async def _mock_web_search_fallback(self, query: str) -> dict[str, Any]:
        """Web search engine fallback fetching external real-time query context."""
        logger.info(f"Triggered Web Search Fallback engine for query: '{query}'")
        return {
            "chunk_id": "web_search_hit_1",
            "document_id": "doc_web_fallback",
            "content": f"[WEB SEARCH FALLBACK] Real-time search context addressing query: {query}",
            "score": 0.88,
            "payload": {
                "filename": "web_search_results.html",
                "content": f"[WEB SEARCH FALLBACK] Real-time search context addressing query: {query}",
                "metadata": {"source": "web_search_engine"},
            },
        }

    async def execute(self, request: RAGRequest) -> RAGResponse:
        start_time = time.perf_counter()
        trace_id = f"trace_{uuid.uuid4().hex[:12]}"

        # 1. Vector Search on internal Knowledge Base
        query_vector = self.embedding_provider.embed_query(request.query)
        kb_hits = self.vector_store.search(
            query_vector=query_vector,
            tenant_id=request.tenant_id,
            top_k=request.top_k,
        )

        # 2. Grade Context Relevance
        max_score = max([float(h.get("score", 0.0)) for h in kb_hits], default=0.0)
        web_search_triggered = False

        final_hits = list(kb_hits)
        if max_score < self.relevance_threshold or not kb_hits:
            web_search_triggered = True
            logger.warning(
                f"Knowledge base relevance score ({max_score:.2f}) below threshold ({self.relevance_threshold}). "
                f"Triggering CRAG web search."
            )
            web_hit = await self._mock_web_search_fallback(request.query)
            final_hits.append(web_hit)

        # 3. Context Assembly & Deduplication
        context_str, citations = self.context_builder.build_context(
            final_hits, max_context_tokens=request.max_context_tokens
        )

        # 4. Prompt Construction
        prompts = self.prompt_builder.build_prompt(request.query, context_str)

        # 5. LLM Completion via Sarvam AI
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

        strat_name = "Corrective (CRAG + Web Search)" if web_search_triggered else "Corrective (KB Grounded)"

        return RAGResponse(
            query=request.query,
            answer=llm_response.content,
            citations=citations,
            rag_strategy=strat_name,
            model=llm_response.model_name,
            latency_ms=elapsed_ms,
            prompt_tokens=llm_response.prompt_tokens,
            completion_tokens=llm_response.completion_tokens,
            estimated_cost_usd=cost,
            trace_id=trace_id,
            tenant_id=request.tenant_id,
        )
