"""Basic RAG Strategy combining Qdrant dense vector search, ContextBuilder, and Sarvam-105B LLM."""

import logging
import time
import uuid

from src.context.builder import ContextBuilder
from src.embeddings.factory import get_embedding_provider
from src.llm import LLMProvider, get_llm_provider
from src.prompting.builder import PromptBuilder
from src.rag.base import BaseRAGStrategy, RAGRequest, RAGResponse
from src.retrieval.vector_store import QdrantVectorStore, get_vector_store

logger = logging.getLogger(__name__)


class BasicRAGStrategy(BaseRAGStrategy):
    """Standard baseline dense vector retrieval RAG strategy."""

    def __init__(
        self,
        vector_store: QdrantVectorStore | None = None,
        embedding_provider_name: str = "bge-m3",
        llm_provider: LLMProvider | None = None,
    ):
        self.vector_store = vector_store or get_vector_store()
        self.embedding_provider = get_embedding_provider(embedding_provider_name)
        self.context_builder = ContextBuilder()
        self.prompt_builder = PromptBuilder()
        self.llm_provider = llm_provider or get_llm_provider()

    async def execute(self, request: RAGRequest) -> RAGResponse:
        start_time = time.perf_counter()
        trace_id = f"trace_{uuid.uuid4().hex[:12]}"

        # 1. Embed query
        query_vector = self.embedding_provider.embed_query(request.query)

        # 2. Dense Vector Search in Qdrant with tenant isolation
        search_hits = self.vector_store.search(
            query_vector=query_vector,
            tenant_id=request.tenant_id,
            top_k=request.top_k,
        )

        # 3. Context assembly & citation extraction
        context_str, citations = self.context_builder.build_context(
            search_hits, max_context_tokens=request.max_context_tokens
        )

        # 4. Prompt building (grounding + instruction boundary)
        prompts = self.prompt_builder.build_prompt(request.query, context_str)

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
            rag_strategy="Basic",
            citations=citations,
            latency_ms=elapsed_ms,
            prompt_tokens=llm_res.prompt_tokens,
            completion_tokens=llm_res.completion_tokens,
            estimated_cost_usd=llm_res.estimated_cost_usd,
            model=llm_res.model_name,
            trace_id=trace_id,
            tenant_id=request.tenant_id,
        )
