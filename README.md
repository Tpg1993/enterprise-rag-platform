# Enterprise Multi-Architecture Production-Grade RAG & Agentic AI Platform

> Powered by **Sarvam AI (`sarvam-105b`)**, **LangChain**, **LangGraph**, **LangSmith**, **FastAPI**, **Qdrant**, and **Enterprise Web UI**.

---

## Overview

An enterprise-oriented, modular RAG & Agentic AI platform designed to implement, evaluate, compare, and observe multiple RAG architectures side-by-side using Sarvam AI as the primary LLM provider.

### Supported RAG Strategies
1. **Basic RAG** (baseline vector retrieval)
2. **Hybrid RAG** (Dense Qdrant + Lexical BM25 + Reciprocal Rank Fusion)
3. **MMR RAG** (Maximal Marginal Relevance diversity optimization)
4. **Reranked RAG** (Cross-Encoder reranking using BGE/Jina)
5. **Parent-Child RAG** (Small chunk retrieval -> Parent chunk context)
6. **Multi-Query RAG** (Query expansion & multi-retrieval fusion)
7. **HyDE RAG** (Hypothetical Document Embeddings)
8. **Adaptive RAG** (Intent classification & dynamic route selection via LangGraph)
9. **Corrective RAG (CRAG)** (Retrieval quality evaluation & active re-querying)
10. **Self-RAG** (Grounding & self-reflection decision loops)
11. **ReAct / Agentic RAG** (Stateful tool-using agents in LangGraph)
12. **GraphRAG** (Neo4j entity/relationship graph + vector hybrid retrieval)
13. **SQL RAG** (Safe Text-to-SQL query generation against PostgreSQL)
14. **Multimodal RAG** (Text, tables, images, and document structures)

---

## Quick Start (Local Setup)

### Prerequisites
- Python 3.11+
- [`uv`](https://github.com/astral-sh/uv) package manager
- Docker & Docker Compose

### Environment Setup
```bash
# 1. Create virtual environment & sync dependencies
uv venv .venv
# On Windows PowerShell:
.venv\Scripts\Activate.ps1

# 2. Sync dependencies
uv sync

# 3. Copy environment configuration
cp .env.example .env
```

### Running Services
```bash
# Start core infrastructure (Qdrant, Redis, PostgreSQL, FastAPI)
docker compose --profile core up -d

# Run local development server
uv run uvicorn src.api.main:app --reload
```

---

## Git Branching Strategy

Each RAG strategy is developed on a dedicated branch adhering to:  
`<LLM>-<RAG_TYPE>-<VERSION>-<AGENTIC_FRAMEWORK>`

Examples:
- `sarvam-105b-basic-rag-v1.0.0-none`
- `sarvam-105b-hybrid-rag-v1.0.0-none`
- `sarvam-105b-adaptive-rag-v1.0.0-langgraph`
- `sarvam-105b-sql-rag-v1.0.0-langgraph`

`main` acts as the stable integration branch.

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
