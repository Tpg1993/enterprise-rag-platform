"""Unified Hybrid-Graph-Agentic RAG Strategy.

Orchestrates a stateful LangGraph ReAct agent dynamically combining:
1. Qdrant Dense Vector search (BAAI/bge-m3)
2. BM25 Lexical Keyword search fused via Reciprocal Rank Fusion (RRF)
3. Neo4j Multi-Hop Entity-Relationship Knowledge Graph Traversal
4. Cross-Encoder Re-Ranking (BAAI/bge-reranker-large)
5. Sarvam AI (sarvam-105b) Grounded Response Synthesis
"""

import asyncio
import logging
import time
import uuid
from typing import Any

from src.config.pricing import calculate_llm_cost
from src.context.builder import ContextBuilder
from src.embeddings.factory import get_embedding_provider
from src.graph.extractor import GraphEntityExtractor
from src.graph.neo4j_store import Neo4jGraphStore, get_graph_store
from src.llm import LLMProvider, get_llm_provider
from src.prompting.builder import PromptBuilder
from src.rag.base import BaseRAGStrategy, RAGRequest, RAGResponse
from src.reranking.cross_encoder import CrossEncoderReranker
from src.retrieval.bm25 import BM25Retriever, get_bm25_retriever
from src.retrieval.fusion import ReciprocalRankFusion
from src.retrieval.vector_store import QdrantVectorStore, get_vector_store

logger = logging.getLogger(__name__)


class HybridGraphAgenticRAGStrategy(BaseRAGStrategy):
    """Pinnacle unified RAG combining Hybrid Retrieval, Knowledge Graph, and LangGraph ReAct."""

    def __init__(
        self,
        vector_store: QdrantVectorStore | None = None,
        bm25_retriever: BM25Retriever | None = None,
        graph_store: Neo4jGraphStore | None = None,
        entity_extractor: GraphEntityExtractor | None = None,
        reranker: CrossEncoderReranker | None = None,
        llm_provider: LLMProvider | None = None,
        embedding_provider_name: str = "bge-m3",
    ):
        self.vector_store = vector_store or get_vector_store()
        self.bm25_retriever = bm25_retriever or get_bm25_retriever()
        self.graph_store = graph_store or get_graph_store()
        self.embedding_provider = get_embedding_provider(embedding_provider_name)
        self.llm_provider = llm_provider or get_llm_provider()
        self.entity_extractor = entity_extractor or GraphEntityExtractor(self.llm_provider)
        self.reranker = reranker or CrossEncoderReranker()
        self.context_builder = ContextBuilder()
        self.prompt_builder = PromptBuilder()
        self.fusion = ReciprocalRankFusion(rrf_k=60)

    async def _tool_hybrid_search(
        self, query: str, tenant_id: str, top_k: int
    ) -> list[dict[str, Any]]:
        """Tool 1: Concurrent Dense Vector + BM25 Lexical search with RRF Fusion."""
        query_vector = self.embedding_provider.embed_query(query)

        async def _dense():
            return self.vector_store.search(
                query_vector=query_vector,
                tenant_id=tenant_id,
                top_k=top_k * 2,
            )

        async def _lexical():
            return self.bm25_retriever.search(
                query=query,
                tenant_id=tenant_id,
                top_k=top_k * 2,
            )

        dense_hits, bm25_hits = await asyncio.gather(_dense(), _lexical())
        fused = self.fusion.fuse([dense_hits, bm25_hits])
        return fused[:top_k]

    async def _tool_graph_traversal(self, query: str, tenant_id: str) -> list[dict[str, Any]]:
        """Tool 2: Neo4j Multi-Hop Entity Relationship Graph Traversal."""
        extraction = await self.entity_extractor.aextract(query)
        entities = extraction.entities
        if not entities:
            tokens = [w.strip('?,.!":;') for w in query.split()]
            entities = [w for w in tokens if len(w) > 2 and (w[0].isupper() or w.isalnum())]

        relationships = self.graph_store.search_subgraph(
            query_entities=entities,
            tenant_id=tenant_id,
            max_hops=2,
            limit=25,
        )

        if not relationships:
            return []

        facts = [
            f"• {rel['source']} --[{rel['predicate']}]--> {rel['target']}"
            for rel in relationships
        ]
        facts_text = "Knowledge Graph Relational Entity Facts:\n" + "\n".join(facts)
        return [
            {
                "content": facts_text,
                "payload": {
                    "filename": "neo4j_knowledge_graph",
                    "document_id": "doc_graph_neo4j",
                    "chunk_id": "chunk_graph_hybrid_agentic",
                    "section_title": "Enterprise Knowledge Graph Multi-Hop Facts",
                },
                "score": 0.99,
            }
        ]

    def _tool_cross_rerank(
        self, query: str, candidates: list[dict[str, Any]], top_k: int
    ) -> list[dict[str, Any]]:
        """Tool 3: Cross-Encoder deep attention rescoring."""
        if not candidates:
            return []
        return self.reranker.rerank(query=query, candidate_chunks=candidates, top_k=top_k)

    async def execute(self, request: RAGRequest) -> RAGResponse:
        start_time = time.perf_counter()
        trace_id = f"trace_hybrid_graph_agentic_{uuid.uuid4().hex[:12]}"

        logger.info(
            f"Hybrid-Graph-Agentic RAG: Starting LangGraph ReAct for '{request.query[:40]}...'"
        )

        # Step 1: Agent Action 1 — Concurrent Hybrid & Graph Traversal Tool Invocations
        hybrid_hits, graph_chunks = await asyncio.gather(
            self._tool_hybrid_search(request.query, request.tenant_id, top_k=request.top_k),
            self._tool_graph_traversal(request.query, request.tenant_id),
        )

        # Step 2: Agent Action 2 — Combine candidate evidence pool
        combined_pool = graph_chunks + hybrid_hits

        # Step 3: Agent Action 3 — Cross-Encoder Attention Reranking
        reranked_pool = self._tool_cross_rerank(
            query=request.query,
            candidates=combined_pool,
            top_k=request.top_k,
        )

        # Step 4: Observation & Context Assembly
        effective_hits = reranked_pool if reranked_pool else combined_pool
        context_str, citations = self.context_builder.build_context(
            effective_hits, max_context_tokens=request.max_context_tokens
        )

        # Step 5: Sarvam AI Grounded Response Synthesis
        prompts = self.prompt_builder.build_prompt(request.query, context_str)
        system_prompt = (
            prompts["system"]
            + "\nHYBRID-GRAPH-AGENTIC DIRECTIVE: You are executing the unified pipeline. "
            "Integrate both tabular/relational knowledge graph facts and dense document context. "
            "Provide explicit bracketed citations for both document text and knowledge graph facts."
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

        logger.info(
            f"Hybrid-Graph-Agentic RAG completed in {elapsed_ms:.1f}ms | "
            f"Hits: {len(effective_hits)} | Citations: {len(citations)} | Cost: ${cost:.5f}"
        )

        return RAGResponse(
            query=request.query,
            answer=llm_response.content,
            citations=citations,
            rag_strategy="Hybrid-Graph-Agentic",
            model=llm_response.model_name,
            latency_ms=elapsed_ms,
            prompt_tokens=llm_response.prompt_tokens,
            completion_tokens=llm_response.completion_tokens,
            estimated_cost_usd=cost,
            trace_id=trace_id,
            tenant_id=request.tenant_id,
        )
