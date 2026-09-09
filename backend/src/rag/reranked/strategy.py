"""Cross-Encoder Reranked RAG Strategy performing deep cross-attention candidate re-scoring."""

import logging
import time
import uuid

from src.context.builder import ContextBuilder
from src.embeddings.factory import get_embedding_provider
from src.llm import LLMProvider, get_llm_provider
from src.prompting.builder import PromptBuilder
from src.rag.base import BaseRAGStrategy, RAGRequest, RAGResponse
from src.reranking import BaseReranker, get_reranker
from src.retrieval.vector_store import QdrantVectorStore, get_vector_store

logger = logging.getLogger(__name__)


class RerankedRAGStrategy(BaseRAGStrategy):
    """RAG strategy fetching candidate pool and re-scoring via Cross-Encoder model."""

    def __init__(
        self,
        vector_store: QdrantVectorStore | None = None,
        embedding_provider_name: str = "bge-m3",
        reranker: BaseReranker | None = None,
        llm_provider: LLMProvider | None = None,
        candidate_multiplier: int = 5,
    ):
        self.vector_store = vector_store or get_vector_store()
        self.embedding_provider = get_embedding_provider(embedding_provider_name)
        self.reranker = reranker or get_reranker()
        self.candidate_multiplier = candidate_multiplier
        self.context_builder = ContextBuilder()
        self.prompt_builder = PromptBuilder()
        self.llm_provider = llm_provider or get_llm_provider()

    async def execute(self, request: RAGRequest) -> RAGResponse:
        start_time = time.perf_counter()
        trace_id = f"trace_rerank_{uuid.uuid4().hex[:12]}"

        # 1. Embed query
        query_vector = self.embedding_provider.embed_query(request.query)

        # 2. Fetch candidate pool (e.g. candidate_k = top_k * 5)
        candidate_k = max(request.top_k * self.candidate_multiplier, 20)
        candidate_hits = self.vector_store.search(
            query_vector=query_vector,
            tenant_id=request.tenant_id,
            top_k=candidate_k,
        )

        # 3. Cross-Encoder Reranking
        reranked_hits = self.reranker.rerank(
            query=request.query,
            hits=candidate_hits,
            top_n=request.top_k,
        )

        # 4. Context assembly & citations
        context_str, citations = self.context_builder.build_context(
            reranked_hits, max_context_tokens=request.max_context_tokens
        )

        # 5. Prompt building
        prompts = self.prompt_builder.build_prompt(request.query, context_str)

        # 6. LLM Generation (Sarvam-105B)
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
            rag_strategy="Reranked",
            citations=citations,
            latency_ms=elapsed_ms,
            prompt_tokens=llm_res.prompt_tokens,
            completion_tokens=llm_res.completion_tokens,
            estimated_cost_usd=llm_res.estimated_cost_usd,
            model=llm_res.model_name,
            trace_id=trace_id,
            tenant_id=request.tenant_id,
        )
