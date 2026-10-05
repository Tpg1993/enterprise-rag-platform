"""Hybrid RAG Strategy combining Qdrant dense vector search, BM25 lexical retrieval,
RRF fusion, and Sarvam-105B LLM.
"""

import asyncio
import logging
import time
import uuid

from src.context.builder import ContextBuilder
from src.embeddings.factory import get_embedding_provider
from src.llm import LLMProvider, get_llm_provider
from src.prompting.builder import PromptBuilder
from src.rag.base import BaseRAGStrategy, RAGRequest, RAGResponse
from src.retrieval import BM25Retriever, QdrantVectorStore, ReciprocalRankFusion, get_vector_store

logger = logging.getLogger(__name__)

# Shared global BM25 retriever instance across requests
global_bm25_retriever = BM25Retriever()


class HybridRAGStrategy(BaseRAGStrategy):
    """Hybrid RAG strategy executing concurrent dense vector and BM25 sparse search merged via RRF.
    """

    def __init__(
        self,
        vector_store: QdrantVectorStore | None = None,
        bm25_retriever: BM25Retriever | None = None,
        embedding_provider_name: str = "bge-m3",
        llm_provider: LLMProvider | None = None,
    ):
        self.vector_store = vector_store or get_vector_store()
        self.bm25_retriever = bm25_retriever or global_bm25_retriever
        self.embedding_provider = get_embedding_provider(embedding_provider_name)
        self.fusion = ReciprocalRankFusion(rrf_k=60)
        self.context_builder = ContextBuilder()
        self.prompt_builder = PromptBuilder()
        self.llm_provider = llm_provider or get_llm_provider()

    async def execute(self, request: RAGRequest) -> RAGResponse:
        start_time = time.perf_counter()
        trace_id = f"trace_hybrid_{uuid.uuid4().hex[:12]}"

        # 1. Concurrent Dense & Sparse retrieval
        async def _dense_search() -> list[dict]:
            query_vector = self.embedding_provider.embed_query(request.query)
            return self.vector_store.search(
                query_vector=query_vector,
                tenant_id=request.tenant_id,
                top_k=request.top_k * 2,
            )

        async def _bm25_search() -> list[dict]:
            return self.bm25_retriever.search(
                query=request.query,
                tenant_id=request.tenant_id,
                top_k=request.top_k * 2,
            )

        dense_hits, bm25_hits = await asyncio.gather(_dense_search(), _bm25_search())

        # 2. Reciprocal Rank Fusion (RRF)
        fused_hits = self.fusion.fuse(
            retrieval_runs=[dense_hits, bm25_hits],
            top_k=request.top_k,
            weights=[1.0, 1.0],
        )

        # Temporal filtering (Phase 45 Time-Travel RAG)
        if request.as_of_date or request.temporal_mode:
            from src.retrieval.temporal import TemporalFilter, TemporalPayloadValidator

            t_filter = TemporalFilter(
                as_of_date=request.as_of_date,
                temporal_mode=request.temporal_mode or "point_in_time",
            )
            filtered_fused = [
                h for h in fused_hits
                if TemporalPayloadValidator.evaluate_chunk(h.get("payload", {}), t_filter)[0]
            ]
            if filtered_fused:
                fused_hits = filtered_fused

        # 3. Context assembly & citation formatting
        ctx_res = self.context_builder.build_context(
            fused_hits,
            max_context_tokens=request.max_context_tokens,
            enable_compression=request.enable_compression,
            compression_target_ratio=request.compression_target_ratio,
            query=request.query,
            user_role=request.user_role,
            as_of_date=request.as_of_date,
            temporal_mode=request.temporal_mode,
        )
        context_str = ctx_res.formatted_context
        citations = ctx_res.citations

        # 4. Prompt building (grounding + Indic multilingual directives)
        prompts = self.prompt_builder.build_prompt(
            request.query,
            context_str,
            target_language=request.target_language,
            detected_language=request.detected_language,
        )

        # 5. LLM Generation (Sarvam-105B or Mock)
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
            rag_strategy="Hybrid",
            citations=citations,
            latency_ms=elapsed_ms,
            prompt_tokens=llm_res.prompt_tokens,
            completion_tokens=llm_res.completion_tokens,
            estimated_cost_usd=llm_res.estimated_cost_usd,
            model=llm_res.model_name,
            trace_id=trace_id,
            tenant_id=request.tenant_id,
            compression_ratio=ctx_res.compression_ratio,
            tokens_saved=ctx_res.tokens_saved,
            target_language=request.target_language,
            detected_language=request.detected_language,
        )

