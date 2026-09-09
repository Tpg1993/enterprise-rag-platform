"""Hypothetical Document Embeddings (HyDE) RAG Strategy.

Generates a hypothetical answer document responding to user query, embeds the hypothetical 
document into vector space, performs Qdrant dense vector search, and synthesizes grounded answer.
"""

import logging
import time
import uuid

from src.config.pricing import calculate_llm_cost
from src.context.builder import ContextBuilder
from src.embeddings import BaseEmbeddingProvider, get_embedding_provider
from src.llm import LLMProvider, get_llm_provider
from src.prompting.builder import PromptBuilder
from src.rag.base import BaseRAGStrategy, RAGRequest, RAGResponse
from src.retrieval.vector_store import QdrantVectorStore, get_vector_store

logger = logging.getLogger(__name__)


class HyDERAGStrategy(BaseRAGStrategy):
    """HyDE strategy embedding hypothetical response documents for dense vector retrieval."""

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

    async def _generate_hypothetical_document(self, query: str) -> str:
        """Prompts LLM to generate a hypothetical passage answering user query."""
        system_prompt = (
            "You are an expert technical passage generator. Write a short, highly detailed hypothetical "
            "passage or document section that directly answers the user query. Do not include introductory text."
        )
        user_prompt = f"Query: {query}"

        try:
            res = await self.llm_provider.agenerate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.7,
                max_tokens=256,
            )
            return res.content.strip()
        except Exception as e:
            logger.warning(f"Hypothetical document generation failed ({e}). Using query as fallback.")
            return query

    async def execute(self, request: RAGRequest) -> RAGResponse:
        start_time = time.perf_counter()
        trace_id = f"trace_{uuid.uuid4().hex[:12]}"

        # 1. Generate hypothetical document via Sarvam AI
        hypo_doc = await self._generate_hypothetical_document(request.query)

        # 2. Embed hypothetical document into vector space
        hypo_vector = self.embedding_provider.embed_query(hypo_doc)

        # 3. Vector search using hypothetical document vector
        search_hits = self.vector_store.search(
            query_vector=hypo_vector,
            tenant_id=request.tenant_id,
            top_k=request.top_k,
        )

        # 4. Context Assembly & Deduplication
        context_str, citations = self.context_builder.build_context(
            search_hits, max_context_tokens=request.max_context_tokens
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
            f"HyDE RAG executed in {elapsed_ms:.1f}ms | Hits: {len(search_hits)} | Cost: ${cost:.5f}"
        )

        return RAGResponse(
            query=request.query,
            answer=llm_response.content,
            citations=citations,
            rag_strategy="HyDE",
            model=llm_response.model_name,
            latency_ms=elapsed_ms,
            prompt_tokens=llm_response.prompt_tokens,
            completion_tokens=llm_response.completion_tokens,
            estimated_cost_usd=cost,
            trace_id=trace_id,
            tenant_id=request.tenant_id,
        )
