"""GraphRAG Strategy combining multi-hop Neo4j graph traversal with Qdrant dense vector search."""

import asyncio
import logging
import time
import uuid

from src.context.builder import ContextBuilder
from src.embeddings.factory import get_embedding_provider
from src.graph.extractor import GraphEntityExtractor
from src.graph.neo4j_store import Neo4jGraphStore, get_graph_store
from src.llm import LLMProvider, get_llm_provider
from src.prompting.builder import PromptBuilder
from src.rag.base import BaseRAGStrategy, Citation, RAGRequest, RAGResponse
from src.retrieval.vector_store import QdrantVectorStore, get_vector_store

logger = logging.getLogger(__name__)


class GraphRAGStrategy(BaseRAGStrategy):
    """Multi-hop Graph-Augmented RAG strategy querying Neo4j knowledge graphs in tandem with Qdrant dense vectors."""

    def __init__(
        self,
        vector_store: QdrantVectorStore | None = None,
        graph_store: Neo4jGraphStore | None = None,
        entity_extractor: GraphEntityExtractor | None = None,
        embedding_provider_name: str = "bge-m3",
        llm_provider: LLMProvider | None = None,
    ):
        self.vector_store = vector_store or get_vector_store()
        self.graph_store = graph_store or get_graph_store()
        self.embedding_provider = get_embedding_provider(embedding_provider_name)
        self.llm_provider = llm_provider or get_llm_provider()
        self.entity_extractor = entity_extractor or GraphEntityExtractor(self.llm_provider)
        self.context_builder = ContextBuilder()
        self.prompt_builder = PromptBuilder()

    async def execute(self, request: RAGRequest) -> RAGResponse:
        start_time = time.perf_counter()
        trace_id = f"trace_graph_rag_{uuid.uuid4().hex[:12]}"

        # 1. Extract Seed Entities from Query
        extraction = await self.entity_extractor.aextract(request.query)
        query_entities = extraction.entities

        # Fallback heuristic for entity seeds if none returned
        if not query_entities:
            tokens = [w.strip('?,.!":;') for w in request.query.split()]
            query_entities = [w for w in tokens if len(w) > 2 and (w[0].isupper() or w.isalnum())]

        # 2. Concurrently execute Dense Vector Search and Neo4j Graph Traversal
        async def _dense_retrieval() -> list[dict]:
            query_vector = self.embedding_provider.embed_query(request.query)
            return self.vector_store.search(
                query_vector=query_vector,
                tenant_id=request.tenant_id,
                top_k=request.top_k,
            )

        async def _graph_retrieval() -> list[dict]:
            return self.graph_store.search_subgraph(
                query_entities=query_entities,
                tenant_id=request.tenant_id,
                max_hops=2,
                limit=25,
            )

        dense_hits, graph_relationships = await asyncio.gather(
            _dense_retrieval(),
            _graph_retrieval(),
        )

        # 3. Transform Graph Relationships into Structured Knowledge Chunks
        graph_chunks: list[dict] = []
        if graph_relationships:
            # Group facts for context compactness
            facts = [
                f"• {rel['source']} --[{rel['predicate']}]--> {rel['target']}"
                for rel in graph_relationships
            ]
            facts_text = "Knowledge Graph Relational Facts:\n" + "\n".join(facts)
            graph_chunks.append(
                {
                    "content": facts_text,
                    "payload": {
                        "filename": "neo4j_knowledge_graph",
                        "document_id": "doc_graph_neo4j",
                        "chunk_id": "chunk_graph_subgraph",
                        "section_title": "Entity Relationships",
                    },
                    "score": 0.98,
                }
            )

        # 4. Synthesize Combined Context (Dense + Graph Knowledge)
        all_hits = graph_chunks + dense_hits
        context_str, citations = self.context_builder.build_context(
            all_hits, max_context_tokens=request.max_context_tokens
        )

        # 5. Build Instruction / Data Separation Prompt
        prompts = self.prompt_builder.build_prompt(request.query, context_str)

        # 6. Generate Grounded Answer via Sarvam-105B LLM
        llm_res = await self.llm_provider.agenerate(
            prompt=prompts["user"],
            system_prompt=prompts["system"],
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        # Enhance citations if graph facts contributed
        if graph_relationships and not any(c.filename == "neo4j_knowledge_graph" for c in citations):
            citations.insert(
                0,
                Citation(
                    document_id="doc_graph_neo4j",
                    filename="neo4j_knowledge_graph",
                    chunk_id="chunk_graph_subgraph",
                    content_snippet=f"{len(graph_relationships)} graph relationships traversed",
                    relevance_score=0.98,
                    section_title="Neo4j Knowledge Graph Subgraph",
                ),
            )

        return RAGResponse(
            answer=llm_res.content,
            query=request.query,
            rag_strategy="GraphRAG",
            citations=citations,
            latency_ms=elapsed_ms,
            prompt_tokens=llm_res.prompt_tokens,
            completion_tokens=llm_res.completion_tokens,
            estimated_cost_usd=llm_res.estimated_cost_usd,
            model=llm_res.model_name,
            trace_id=trace_id,
            tenant_id=request.tenant_id,
        )
