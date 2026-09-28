# Enterprise Multi-Architecture Production-Grade RAG & Agentic AI Platform

> **Target LLM**: Sarvam AI (`sarvam-105b`) | **Frameworks**: LangChain & LangGraph | **Vector Store**: Qdrant | **Graph Store**: Neo4j | **Relational DB**: PostgreSQL / SQLite | **Observability**: LangSmith

---

## 1. Executive Overview

An enterprise-oriented, multi-architecture RAG and Agentic AI platform designed to implement, evaluate, compare, and observe multiple RAG architectures side-by-side using **Sarvam AI (`sarvam-105b`)** as the primary LLM provider.

The platform provides a complete web workspace (chat, document ingestion, strategy catalog, side-by-side benchmark matrix, trace explorer, evaluation trends, and RBAC governance) backed by production-grade Python services.

---

## 2. 15 Supported Production RAG Strategies

| # | Strategy Name | Core Architecture | Primary Use Case |
| :---: | :--- | :--- | :--- |
| **1** | **Basic RAG** | Dense vector search (BAAI/bge-m3) in Qdrant Vector DB | Baseline semantic retrieval |
| **2** | **Hybrid RAG** | Concurrent Qdrant dense vector + BM25 lexical search fused via RRF | Precision + keyword accuracy |
| **3** | **MMR RAG** | Maximal Marginal Relevance balancing relevance and pairwise diversity ($\lambda=0.7$) | Redundancy elimination |
| **4** | **Cross-Encoder Reranked** | Fetches Top-50 candidates and rescores with deep cross-attention via local BGE Reranker | High-precision reranking |
| **5** | **Parent-Child RAG** | Searches granular child vectors and resolves to full parent paragraph context | Context preservation |
| **6** | **Multi-Query RAG** | Expands prompt into multiple parallel query formulations fused via RRF | Ambiguous or multi-intent queries |
| **7** | **HyDE RAG** | Generates hypothetical document embeddings to bridge lexical-semantic gap | Sparse queries / zero-shot |
| **8** | **Adaptive RAG** | Query intent router directing to Direct LLM, Dense Retrieval, or Multi-Step Agent | Dynamic cost/latency routing |
| **9** | **Corrective RAG (CRAG)** | Confidence evaluator triggering automated web search fallback on low confidence | Grounding protection & hallucination drop |
| **10** | **Self-RAG** | Self-reflection critique loops grading hallucination risk and rewriting answers | Zero-hallucination compliance |
| **11** | **ReAct Agentic RAG** | Stateful Thought-Action-Observation loop in LangGraph with tool invocation | Complex multi-step reasoning |
| **12** | **GraphRAG** | Multi-hop knowledge graph traversal in Neo4j fused with dense vectors in Qdrant | Relational enterprise entity reasoning |
| **13** | **SQL RAG** | Schema-grounded Text-to-SQL with AST read-only validation (`sqlglot`) | Tabular relational business metrics |
| **14** | **Multimodal RAG** | Extracts vector tables and image figures (PyMuPDF) with token intent reranking | Complex PDFs, financials & charts |
| **15** | **Hybrid-Graph-Agentic RAG** | Unified pinnacle fusing Dense Qdrant + BM25 Lexical + Neo4j Graph traversal via BGE Reranker into a LangGraph ReAct agent | Holistic enterprise reasoning across unstructured text and relational knowledge |

---

## 3. Platform Architecture & Documentation

For in-depth architectural specifications and operational runbooks, refer to the documentation suite in [`docs/`](docs/):

- 📘 **[High-Level Design (HLD)](docs/HLD.md)**: System architecture, subsystem interaction flows, and Mermaid diagrams.
- 📐 **[Low-Level Design (LLD)](docs/LLD.md)**: UML class hierarchy, sequence flows, LangGraph state machines, math formulas, and ER diagrams.
- 🔌 **[REST API Reference](docs/api_reference.md)**: Full endpoint specifications, JSON schemas, headers, and `curl` examples.
- 🛡️ **[Security & Governance Guide](docs/security.md)**: Zero Trust model, PBKDF2 password hashing, JWT tokens, RBAC/ABAC matrix, Presidio PII redaction, and SQL AST sandboxing.
- 🧪 **[Phase-Wise Testing Matrix](docs/rag_phase_test_matrix.md)**: Step-by-step test procedures across all 25 implementation phases.
- 📸 **[Phase-by-Phase Proof Directory](docs/proofs/README.md)**: Master proof index with verified UI screenshots and recordings.

---

## 4. Phase Completion & Verification Status

| Phase | Description | Status | Dedicated Git Branch | Verified Proof |
| :---: | :--- | :---: | :--- | :--- |
| **0** | Project Setup (uv, pyproject, configs) | ✅ Done | `main` | [README](docs/proofs/phase-00-project-setup/README.md) |
| **1** | Platform Infrastructure (FastAPI, Docker, LLM) | ✅ Done | `sarvam-105b-basic-rag-v1.0.0-none` | [README](docs/proofs/phase-01-platform-infrastructure/README.md) |
| **2** | Ingestion Pipeline (CDC, Multi-format, BGE-M3) | ✅ Done | `sarvam-105b-basic-rag-v1.0.0-none` | [README](docs/proofs/phase-02-ingestion-pipeline/README.md) |
| **3** | Basic RAG | ✅ Done | `sarvam-105b-basic-rag-v1.0.0-none` | [README](docs/proofs/phase-03-basic-rag/README.md) |
| **4** | Hybrid RAG (Dense + BM25 + RRF) | ✅ Done | `sarvam-105b-hybrid-rag-v1.0.0-none` | [README](docs/proofs/phase-04-hybrid-rag/README.md) |
| **5** | MMR RAG | ✅ Done | `sarvam-105b-mmr-rag-v1.0.0-none` | [README](docs/proofs/phase-05-mmr-rag/README.md) |
| **6** | Cross-Encoder Reranked RAG | ✅ Done | `sarvam-105b-reranked-rag-v1.0.0-none` | [README](docs/proofs/phase-06-reranked-rag/README.md) |
| **7-8** | Context Builder + Prompt Builder | ✅ Done | `main` | [README](docs/proofs/phase-07-08-context-prompt-builders/README.md) |
| **9** | Evaluation Suite + Dynamic Pricing Engine | ✅ Done | `main` | [README](docs/proofs/phase-09-evaluation-pricing/README.md) |
| **10** | Parent-Child RAG | ✅ Done | `sarvam-105b-parent-child-rag-v1.0.0-none` | [README](docs/proofs/phase-10-parent-child-rag/README.md) |
| **11** | Multi-Query RAG | ✅ Done | `sarvam-105b-multi-query-rag-v1.0.0-langchain` | [README](docs/proofs/phase-11-multi-query-rag/README.md) |
| **12** | HyDE RAG | ✅ Done | `sarvam-105b-hyde-rag-v1.0.0-langchain` | [README](docs/proofs/phase-12-hyde-rag/README.md) |
| **13** | Adaptive RAG (LangGraph) | ✅ Done | `sarvam-105b-adaptive-rag-v1.0.0-langgraph` | [README](docs/proofs/phase-13-adaptive-rag/README.md) |
| **14** | Corrective RAG (CRAG) | ✅ Done | `sarvam-105b-corrective-rag-v1.0.0-langgraph` | [README](docs/proofs/phase-14-corrective-rag/README.md) |
| **15** | Self-RAG | ✅ Done | `sarvam-105b-self-rag-v1.0.0-langgraph` | [README](docs/proofs/phase-15-self-rag/README.md) |
| **16** | ReAct Agentic RAG | ✅ Done | `sarvam-105b-react-rag-v1.0.0-langgraph` | [README](docs/proofs/phase-16-react-rag/README.md) |
| **17** | LangSmith Observability & Trace Explorer | ✅ Done | `main` | [README](docs/proofs/phase-17-langsmith-observability/README.md) |
| **18** | Side-by-Side Strategy Comparison Matrix | ✅ Done | `main` | [README](docs/proofs/phase-18-strategy-comparison/README.md) |
| **19** | **GraphRAG (Neo4j Multi-Hop Triples)** | ✅ Done | `sarvam-105b-graph-rag-v1.0.0-langgraph` | [README](docs/proofs/phase-19-graph-rag/README.md) |
| **20** | **SQL RAG (PostgreSQL Text-to-SQL)** | ✅ Done | `sarvam-105b-sql-rag-v1.0.0-langgraph` | [README](docs/proofs/phase-20-sql-rag/README.md) |
| **21** | **Multimodal RAG (PDF Tables & Images)** | ✅ Done | `sarvam-105b-multimodal-rag-v1.0.0-langgraph` | [README](docs/proofs/phase-21-multimodal-rag/README.md) |
| **22** | **Auth, JWT & RBAC/ABAC Policies** | ✅ Done | `sarvam-105b-auth-rbac-v1.0.0-none` | [README](docs/proofs/phase-22-auth-rbac/README.md) |
| **23** | **Persistent Chat & Eval History** | ✅ Done | `sarvam-105b-persistent-history-v1.0.0-none` | [README](docs/proofs/phase-23-persistent-history/README.md) |
| **25** | **Full Observability Stack (OTel, Prometheus, Grafana)** | ✅ Done | `sarvam-105b-opentelemetry-metrics-v1.0.0-none` | [README](docs/proofs/phase-25-opentelemetry-metrics/README.md) |
| **26** | **PII Redaction (Presidio) + OPA Guardrails** | ✅ Done | `sarvam-105b-security-guardrails-v1.0.0-none` | [README](docs/proofs/phase-26-security-guardrails/README.md) |
| **27** | **Hybrid-Graph-Agentic Pinnacle RAG** | ✅ Done | `sarvam-105b-hybrid-graph-agentic-rag-v1.0.0-langgraph` | [README](docs/proofs/phase-27-hybrid-graph-agentic-rag/README.md) |

---

## 5. Quick Start (Local Setup)

### 5.1 Prerequisites
- Python 3.11+
- [`uv`](https://github.com/astral-sh/uv) package manager (exclusive package manager)
- Docker & Docker Compose (optional for local Qdrant/Neo4j containers)

### 5.2 Environment Setup
```bash
# 1. Create and activate virtual environment
uv venv .venv

# On Windows PowerShell:
.venv\Scripts\Activate.ps1

# On Linux/macOS:
source .venv/bin/activate

# 2. Sync locked dependencies
uv sync

# 3. Configure environment keys
cp .env.example .env
# Edit .env and supply SARVAM_API_KEY
```

### 5.3 Launching the Application
```bash
# Start FastAPI backend server (serves REST API and Web UI on http://127.0.0.1:8000)
uv run uvicorn backend.src.api.main:app --host 127.0.0.1 --port 8000
```
Open your browser to: **`http://127.0.0.1:8000/ui/`**

---

## 6. Running Automated Test Suites

In accordance with Section 4 of `AGENTS.md`, all phases are backed by dedicated test suites:

```bash
# Run all unit tests
uv run pytest backend/tests/unit/

# Run all multi-component integration tests
uv run pytest backend/tests/integration/

# Run specific phase test suite (e.g. Multimodal + Persistent History)
uv run pytest backend/tests/unit/test_persistent_history.py backend/tests/unit/test_multimodal_rag.py
```

---

## 7. License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
