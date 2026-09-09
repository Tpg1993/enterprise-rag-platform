"""Maximal Marginal Relevance (MMR) RAG Strategy eliminating context redundancy via diversity re-ranking."""

import logging
import time
import uuid

from src.context.builder import ContextBuilder
from src.embeddings.factory import get_embedding_provider
from src.llm import LLMProvider, get_llm_provider
from src.prompting.builder import PromptBuilder
from src.rag.base import BaseRAGStrategy, RAGRequest, RAGResponse
from src.retrieval import MaximalMarginalRelevance, QdrantVectorStore, get_vector_store

logger = logging.getLogger(__name__)


class MMRRAGStrategy(BaseRAGStrategy):
    """MMR strategy retrieving candidate pool and selecting diverse non-redundant context chunks."""

    def __init__(
        self,
        vector_store: QdrantVectorStore | None = None,
        embedding_provider_name: str = "bge-m3",
        llm_provider: LLMProvider | None = None,
        lambda_mult: float = 0.7,
        candidate_multiplier: int = 5,
    ):
        self.vector_store = vector_store or get_vector_store()
        self.embedding_provider = get_embedding_provider(embedding_provider_name)
        self.mmr_selector = MaximalMarginalRelevance(lambda_mult=lambda_mult)
        self.candidate_multiplier = candidate_multiplier
        self.context_builder = ContextBuilder()
        self.prompt_builder = PromptBuilder()
        self.llm_provider = llm_provider or get_llm_provider()

    async def execute(self, request: RAGRequest) -> RAGResponse:
        start_time = time.perf_counter()
        trace_id = f"trace_mmr_{uuid.uuid4().hex[:12]}"

        # 1. Embed query
        query_vector = self.embedding_provider.embed_query(request.query)

        # 2. Fetch candidate pool (e.g. candidate_k = top_k * 5)
        candidate_k = max(request.top_k * self.candidate_multiplier, 20)
        candidate_hits = self.vector_store.search(
            query_vector=query_vector,
            tenant_id=request.tenant_id,
            top_k=candidate_k,
        )

        # 3. Extract or generate vectors for candidate pool
        candidate_vectors: list[list[float]] = []
        for hit in candidate_hits:
            v = hit.get("vector")
            if v and len(v) == len(query_vector):
                candidate_vectors.append(v)
            else:
                # Fallback embed document content
                emb = self.embedding_provider.embed_documents([hit["content"]])
                candidate_vectors.append(emb[0] if emb else query_vector)

        # 4. Apply MMR Diversity Selection
        selected_hits = self.mmr_selector.select(
            query_vector=query_vector,
            candidate_hits=candidate_hits,
            candidate_vectors=candidate_vectors,
            final_k=request.top_k,
        )

        # 5. Context assembly & citations
        context_str, citations = self.context_builder.build_context(
            selected_hits, max_context_tokens=request.max_context_tokens
        )

        # 6. Prompt building
        prompts = self.prompt_builder.build_prompt(request.query, context_str)

        # 7. LLM Generation (Sarvam-105B)
        llm_res = await self.llm_provider.agenerate(
            prompt=prompts["user"],
            system_prompt=prompts["system"],
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        return RAGResponse(
            answer=llm_res.content,
            query=request.query,
            rag_strategy="MMR",
            citations=citations,
            latency_ms=elapsed_ms,
            prompt_tokens=llm_res.prompt_tokens,
            completion_tokens=llm_res.completion_tokens,
            estimated_cost_usd=llm_res.estimated_cost_usd,
            model=llm_res.model_name,
            trace_id=trace_id,
            tenant_id=request.tenant_id,
        )
