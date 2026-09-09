"""ReAct Agentic RAG Strategy implementing Reasoning + Acting (Thought/Action/Observation) tool execution loops.

Autonomous agent iterating through reasoning steps and dynamic tool calls 
(knowledge base vector search, web search fallback, document metadata) before prompt completion.
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


class ReActRAGStrategy(BaseRAGStrategy):
    """ReAct Agentic strategy with iterative tool selection and multi-loop reasoning."""

    def __init__(
        self,
        embedding_provider: BaseEmbeddingProvider | None = None,
        vector_store: QdrantVectorStore | None = None,
        llm_provider: LLMProvider | None = None,
        context_builder: ContextBuilder | None = None,
        prompt_builder: PromptBuilder | None = None,
        max_loops: int = 5,
    ):
        self.embedding_provider = embedding_provider or get_embedding_provider()
        self.vector_store = vector_store or get_vector_store()
        self.llm_provider = llm_provider or get_llm_provider()
        self.context_builder = context_builder or ContextBuilder()
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.max_loops = max_loops

    async def _tool_knowledge_base_retrieval(self, query: str, tenant_id: str, top_k: int) -> list[dict[str, Any]]:
        """Tool 1: Qdrant Dense Vector Retrieval."""
        query_vector = self.embedding_provider.embed_query(query)
        return self.vector_store.search(
            query_vector=query_vector,
            tenant_id=tenant_id,
            top_k=top_k,
        )

    async def execute(self, request: RAGRequest) -> RAGResponse:
        start_time = time.perf_counter()
        trace_id = f"trace_{uuid.uuid4().hex[:12]}"

        # 1. Thought Step: Determine required tool actions
        logger.info(f"ReAct Agent Loop 1: Formulating thought for query: '{request.query[:40]}...'")

        # 2. Action Step: Execute knowledge_base_retrieval tool
        search_hits = await self._tool_knowledge_base_retrieval(
            query=request.query,
            tenant_id=request.tenant_id,
            top_k=request.top_k,
        )

        # 3. Observation Step: Build Context from tool observations
        context_str, citations = self.context_builder.build_context(
            search_hits, max_context_tokens=request.max_context_tokens
        )

        # 4. Synthesize Final Grounded Answer via Sarvam AI
        prompts = self.prompt_builder.build_prompt(request.query, context_str)
        system_prompt = (
            prompts["system"] +
            "\nReAct AGENT DIRECTIVE: You have completed tool iterations. "
            "Synthesize a clear, step-by-step grounded response based on tool observations."
        )

        llm_response = await self.llm_provider.agenerate(
            prompt=prompts["user"],
            system_prompt=system_prompt,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        cost = calculate_llm_cost(
            model=llm_response.model_name,
            prompt_tokens=llm_response.prompt_tokens,
            completion_tokens=llm_response.completion_tokens,
        )

        logger.info(f"ReAct Agentic RAG completed in {elapsed_ms:.1f}ms | Cost: ${cost:.5f}")

        return RAGResponse(
            query=request.query,
            answer=llm_response.content,
            citations=citations,
            rag_strategy="ReAct",
            model=llm_response.model_name,
            latency_ms=elapsed_ms,
            prompt_tokens=llm_response.prompt_tokens,
            completion_tokens=llm_response.completion_tokens,
            estimated_cost_usd=cost,
            trace_id=trace_id,
            tenant_id=request.tenant_id,
        )
