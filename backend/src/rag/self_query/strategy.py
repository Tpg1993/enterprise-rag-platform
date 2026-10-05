"""Strategy 20: Autonomous Self-Querying & Metadata Filter Synthesizer (Self-Query-RAG)."""

import logging
import time
import uuid

from src.context.builder import ContextBuilder
from src.embeddings.factory import get_embedding_provider
from src.llm import LLMProvider, get_llm_provider
from src.prompting.builder import PromptBuilder
from src.rag.base import BaseRAGStrategy, RAGRequest, RAGResponse
from src.retrieval.self_query import SelfQueryCompiler, get_self_query_compiler
from src.retrieval.vector_store import QdrantVectorStore, get_vector_store

logger = logging.getLogger(__name__)


class SelfQueryRAGStrategy(BaseRAGStrategy):
    """Deconstructs natural language into clean semantic query and structured metadata filters."""

    def __init__(
        self,
        vector_store: QdrantVectorStore | None = None,
        embedding_provider_name: str = "bge-m3",
        llm_provider: LLMProvider | None = None,
        compiler: SelfQueryCompiler | None = None,
    ):
        self.vector_store = vector_store or get_vector_store()
        self.embedding_provider = get_embedding_provider(embedding_provider_name)
        self.context_builder = ContextBuilder()
        self.prompt_builder = PromptBuilder()
        self.llm_provider = llm_provider or get_llm_provider()
        self.compiler = compiler or get_self_query_compiler()

    async def execute(self, request: RAGRequest) -> RAGResponse:
        start_time = time.perf_counter()
        trace_id = f"trace_{uuid.uuid4().hex[:12]}"

        # 1. Compile query into clean semantic string & structured metadata filters
        parsed = self.compiler.compile(request.query)
        logger.info(
            f"Self-Query compiled query: semantic='{parsed.semantic_query}', "
            f"filters_count={len(parsed.filters)}"
        )

        # 2. Embed sanitized semantic query
        query_vector = self.embedding_provider.embed_query(parsed.semantic_query)

        # 3. Translate filters into native Qdrant filter
        qdrant_filter = self.compiler.to_qdrant_filter(parsed, tenant_id=request.tenant_id)

        # 4. Filtered Dense Vector Search in Qdrant (or memory fallback)
        search_hits = self.vector_store.search(
            query_vector=query_vector,
            tenant_id=request.tenant_id,
            top_k=request.top_k,
            metadata_filter=qdrant_filter,
            filter_conditions=parsed.filters,
        )

        # 5. Temporal Filtering fallback if as_of_date specified (Phase 45)
        if request.as_of_date or request.temporal_mode:
            from src.retrieval.temporal import TemporalFilter, TemporalPayloadValidator

            t_filter = TemporalFilter(
                as_of_date=request.as_of_date,
                temporal_mode=request.temporal_mode or "point_in_time",
            )
            filtered_hits = [
                h
                for h in search_hits
                if TemporalPayloadValidator.evaluate_chunk(h.get("payload", {}), t_filter)[0]
            ]
            if filtered_hits:
                search_hits = filtered_hits

        # 6. Context Assembly & Citation Sanitization
        ctx_res = self.context_builder.build_context(
            search_hits,
            max_context_tokens=request.max_context_tokens,
            enable_compression=request.enable_compression,
            compression_target_ratio=request.compression_target_ratio,
            query=parsed.semantic_query,
            user_role=request.user_role,
            as_of_date=request.as_of_date,
            temporal_mode=request.temporal_mode,
        )

        # 7. Prompt Construction with Indic multilingual directives
        prompts = self.prompt_builder.build_prompt(
            request.query,
            ctx_res.formatted_context,
            target_language=request.target_language,
            detected_language=request.detected_language,
        )

        # 8. Generation via Sarvam-105B or Mock LLM
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
            rag_strategy="Self-Query-RAG",
            citations=ctx_res.citations,
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
