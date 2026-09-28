"""RAG Strategy Catalog and Version Manifest API endpoints."""

import logging

from fastapi import APIRouter, HTTPException
from src.api.schemas import (
    RAGStrategiesResponse,
    RAGStrategyMetadata,
    RAGVersionResponse,
)
from src.config.loader import get_project_root, load_yaml_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/rag", tags=["RAG Platform & Strategies"])

# Comprehensive catalog of all 15 production RAG strategies
STRATEGIES_CATALOG: list[RAGStrategyMetadata] = [
    RAGStrategyMetadata(
        id="Basic",
        name="Basic RAG",
        description=(
            "Dense vector search using BAAI/bge-m3 embeddings in Qdrant Vector DB, "
            "followed by Sarvam-105B LLM generation."
        ),
        framework="none",
        category="Dense Retrieval",
        version="1.0.0",
        features=["BAAI/bge-m3", "Qdrant HNSW", "Sarvam-105B", "Zero-Trust Context"],
    ),
    RAGStrategyMetadata(
        id="Hybrid",
        name="Hybrid RAG",
        description=(
            "Concurrent Qdrant dense vector search + BM25 sparse lexical search "
            "fused via Reciprocal Rank Fusion (RRF)."
        ),
        framework="none",
        category="Hybrid Retrieval",
        version="1.0.0",
        features=["Dense + BM25", "Reciprocal Rank Fusion (RRF_k=60)", "Multi-Tenant Isolation"],
    ),
    RAGStrategyMetadata(
        id="MMR",
        name="MMR RAG",
        description=(
            "Maximal Marginal Relevance balances relevance with pairwise diversity "
            "(lambda=0.7) to eliminate redundant context chunks."
        ),
        framework="none",
        category="Diversity Retrieval",
        version="1.0.0",
        features=["Cosine Diversity", "Redundancy Elimination", "Configurable Lambda"],
    ),
    RAGStrategyMetadata(
        id="Reranked",
        name="Cross-Encoder Reranked RAG",
        description=(
            "Fetches Top-50 candidates and applies deep cross-attention rescoring "
            "via local BGE Cross-Encoder to output Top-5 context chunks."
        ),
        framework="none",
        category="Reranking",
        version="1.0.0",
        features=["Deep Cross-Attention", "BAAI/bge-reranker-large", "High Precision"],
    ),
    RAGStrategyMetadata(
        id="Parent-Child",
        name="Parent-Child RAG",
        description=(
            "Searches small child vector chunks and resolves to full parent paragraph "
            "background context for rich grounding."
        ),
        framework="none",
        category="Hierarchical Retrieval",
        version="1.0.0",
        features=["Hierarchical Chunking", "Context Expansion", "Child-Parent Map"],
    ),
    RAGStrategyMetadata(
        id="Multi-Query",
        name="Multi-Query RAG",
        description=(
            "Prompts Sarvam-105B to rephrase user prompt into 3 technical query variations, "
            "executing parallel vector searches and RRF fusion."
        ),
        framework="langchain",
        category="Query Expansion",
        version="1.0.0",
        features=["Query Expansion", "Parallel Retrieval", "Ambiguity Mitigation"],
    ),
    RAGStrategyMetadata(
        id="HyDE",
        name="HyDE RAG",
        description=(
            "Generates a hypothetical answer document using Sarvam-105B, embedding the "
            "hypothetical passage to retrieve dense vector matches."
        ),
        framework="langchain",
        category="Hypothetical Embeddings",
        version="1.0.0",
        features=["Hypothetical Document Embeddings", "Zero-Shot Bridging", "Dense Vector Search"],
    ),
    RAGStrategyMetadata(
        id="Adaptive",
        name="Adaptive RAG",
        description=(
            "Dynamic query intent classifier classifying complexity (BASIC, HYBRID, "
            "MULTI_QUERY, RERANKED) to route to optimal RAG pipelines."
        ),
        framework="langgraph",
        category="Dynamic Routing",
        version="1.0.0",
        features=["Intent Classification", "Cost-Optimized Routing", "Latency Mitigation"],
    ),
    RAGStrategyMetadata(
        id="Corrective",
        name="Corrective RAG (CRAG)",
        description=(
            "Evaluates retrieval confidence score (< 0.5 threshold) and automatically "
            "triggers web search fallback when internal knowledge is low."
        ),
        framework="langgraph",
        category="Active Corrective",
        version="1.0.0",
        features=["Confidence Scoring", "Automated Fallback", "Hallucination Protection"],
    ),
    RAGStrategyMetadata(
        id="Self-RAG",
        name="Self-RAG",
        description=(
            "Self-grading candidate document relevance and computing answer faithfulness "
            "scores to execute prompt self-reflection loops."
        ),
        framework="langgraph",
        category="Self-Reflection",
        version="1.0.0",
        features=["Self-Grading", "Hallucination Critique", "Reflection Revision Loops"],
    ),
    RAGStrategyMetadata(
        id="ReAct",
        name="ReAct Agentic RAG",
        description=(
            "Reasoning + Acting Tool Execution Loop in LangGraph iterating through "
            "Thought, Tool Action, and Observation cycles."
        ),
        framework="langgraph",
        category="Agentic Workflow",
        version="1.0.0",
        features=["LangGraph StateGraph", "Tool Invocation", "Observation Cycles"],
    ),
    RAGStrategyMetadata(
        id="GraphRAG",
        name="GraphRAG (Neo4j)",
        description=(
            "Multi-hop knowledge graph traversal in Neo4j coupled with Qdrant dense "
            "vector search for relationship-dense queries."
        ),
        framework="langgraph",
        category="Knowledge Graph",
        version="1.0.0",
        features=["Neo4j Cypher Traversal", "Entity Extraction", "Multi-Hop Reasoning"],
    ),
    RAGStrategyMetadata(
        id="SQL-RAG",
        name="SQL RAG (PostgreSQL)",
        description=(
            "Natural language to validated PostgreSQL queries with AST security "
            "guardrails, row limits, and read-only execution."
        ),
        framework="langgraph",
        category="Structured Text-to-SQL",
        version="1.0.0",
        features=["sqlglot AST Validation", "Read-Only Security", "Tabular Metrics"],
    ),
    RAGStrategyMetadata(
        id="Multimodal",
        name="Multimodal RAG",
        description=(
            "Joint retrieval over textual chunks, structured tables (Markdown), and "
            "visual image figures with modality-aware reranking."
        ),
        framework="langgraph",
        category="Multimodal Retrieval",
        version="1.0.0",
        features=["PDF Tables Extraction", "Visual Figure Extraction", "Modality-Aware Boosting"],
    ),
    RAGStrategyMetadata(
        id="Hybrid-Graph-Agentic",
        name="Hybrid-Graph-Agentic RAG",
        description=(
            "Unified architecture fusing Dense Qdrant vectors + BM25 Lexical + Neo4j Graph "
            "traversal via BGE Reranker into a LangGraph ReAct agent."
        ),
        framework="langgraph",
        category="Unified Pinnacle",
        version="1.0.0",
        features=["Dense + Lexical + Graph", "BGE Reranking", "LangGraph ReAct Agent"],
    ),
]


@router.get("/strategies", response_model=RAGStrategiesResponse)
async def get_rag_strategies() -> RAGStrategiesResponse:
    """Returns dynamic catalog of all 15 production RAG strategies."""
    return RAGStrategiesResponse(
        total_strategies=len(STRATEGIES_CATALOG),
        strategies=STRATEGIES_CATALOG,
    )


@router.get("/versions", response_model=RAGVersionResponse)
async def get_rag_versions() -> RAGVersionResponse:
    """Returns platform version manifest, strategy versions, and model versions."""
    root = get_project_root()
    version_file = root / "backend" / "config" / "version.yaml"

    if not version_file.exists():
        raise HTTPException(status_code=404, detail="version.yaml configuration not found")

    data = load_yaml_config(version_file)
    if not data:
        raise HTTPException(status_code=500, detail="Failed to load version.yaml manifest")

    return RAGVersionResponse(
        application=data.get("application", {}),
        models=data.get("models", {}),
        rag=data.get("rag", {}),
        security=data.get("security", {}),
        prompts=data.get("prompts", {}),
        evaluation_dataset=data.get("evaluation_dataset", {}),
    )
