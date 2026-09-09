# AGENTS.md — Development Guidelines & Coding Standards

> **Enterprise Multi-Architecture Production-Grade RAG & Agentic AI Platform**  
> **LLM**: Sarvam AI (`sarvam-105b`) | **Frameworks**: LangChain & LangGraph | **Observability**: LangSmith | **Vector DB**: Qdrant

---

## 1. Environment & Package Management Rules

- **Package Manager**: Use `uv` exclusively. Do **NOT** use `pip` directly or `conda`.
- **Virtual Environment**: `.venv` is **MANDATORY**. Create and activate `.venv` before installing or running dependencies.
  ```bash
  uv venv .venv
  # Windows PowerShell:
  .venv\Scripts\Activate.ps1
  # Install dependencies:
  uv sync
  ```
- **Execution**: All Python commands must be executed within `.venv` (e.g. `uv run pytest`, `uv run fastapi dev`).
- **No Global Installs**: Never install project packages globally.
- **No Hardcoded Paths**: **NEVER** use static or absolute paths (e.g., `C:\Users\...` or `/home/...`). Always use project-root-relative or configuration-driven paths.
- **Secrets & Credentials**: **NEVER** commit `.env`, API keys, DB passwords, or JWT secrets. `.env.example` must contain placeholders only.

---

## 2. Clean & Strict Coding Standards

### Python Standards & Style
- **Python Version**: Python 3.11+
- **Type Hints**: Mandatory for **ALL** function parameters, return values, and class attributes. Enable strict mode in `mypy`.
- **Async First**: Use `async`/`await` for I/O operations (FastAPI endpoints, Qdrant queries, HTTP calls, Database sessions).
- **Validation**: Use **Pydantic v2** for all data models, API payloads, vector payloads, and configuration schemas.
- **Linting & Formatting**: Use `ruff check` and `ruff format`. Enforce clean code rules strictly.
- **Docstrings & Comments**: Preserved and updated. Document public classes, interfaces, and complex RAG math algorithms.

### Software Architecture Principles
- **Single Responsibility Principle (SRP)**: Separate RAG phases into isolated modules (`ingestion`, `chunking`, `embeddings`, `retrieval`, `fusion`, `mmr`, `reranking`, `context`, `prompting`, `llm`, `security`).
- **Dependency Injection**: Pass components (e.g. `LLMProvider`, `VectorStore`, `Reranker`) as injected interfaces rather than instantiating global singletons inside strategies.
- **Modular RAG Strategies**: All RAG strategies inherit from `BaseRAGStrategy` in `src/rag/base.py`. Never duplicate retrieval or fusion business logic across strategies.
- **Configuration-Driven**: All parameters (chunk size, overlap, top_k, lambda, thresholds, timeouts, retries, pricing) must be defined in `config/*.yaml` files and loaded via Pydantic settings.

---

## 3. Project Structure

```
RAG Types/
├── MASTER SPECIFICATION.md
├── AGENTS.md                          # Mandatory agent guidelines and coding standards
├── agent.md                           # Mirror guidelines
├── README.md                          # Comprehensive project documentation
├── CHANGELOG.md                       # Version history and phase completion logs
├── LICENSE                            # Software license
├── pyproject.toml                     # uv project & dependency specifications
├── uv.lock                            # Deterministic dependency lockfile
├── .gitignore                         # Strict exclusion rules (.env, .venv, caches)
├── .dockerignore                      # Docker context exclusion rules
├── .env.example                       # Template environment file (placeholders only)
├── Makefile                           # Development automation commands
├── Dockerfile                         # Multi-stage production container build
├── docker-compose.yml                 # Local container orchestrator
├── backend/                           # Backend Application Root
│   ├── config/                        # YAML-based environment configurations
│   ├── data/                          # Versioned data & benchmarks
│   ├── src/                           # Core Application Source Code
│   │   ├── api/                       # FastAPI application, routers, middleware
│   │   ├── auth/                      # Authentication, JWT, RBAC, ABAC policies
│   │   ├── config/                    # Settings loader and Pydantic validation
│   │   ├── ingestion/                 # CDC, document cleaning, normalization
│   │   ├── documents/                 # Parsers (PDF, DOCX, TXT, HTML, Markdown, CSV, JSON)
│   │   ├── chunking/                  # Pluggable chunkers (Fixed, Semantic, Parent-Child)
│   │   ├── embeddings/                # Local BGE-M3 embedding service & cache
│   │   ├── retrieval/                 # Qdrant Dense search, BM25 Lexical, RRF Fusion, MMR
│   │   ├── reranking/                 # Local Cross-Encoder reranker (BGE Reranker)
│   │   ├── context/                   # ContextBuilder (Merging, deduplication, citations)
│   │   ├── prompting/                 # PromptBuilder (System/Data separation, grounding)
│   │   ├── llm/                       # SarvamLLMProvider & MockLLM implementation
│   │   ├── evaluation/                # RAGAS, DeepEval, and LangSmith evaluation engines
│   │   ├── observability/             # LangSmith tracing, OpenTelemetry, Prometheus metrics
│   │   ├── security/                  # Presidio PII redaction, OPA rules, injection guardrails
│   │   ├── cache/                     # Multi-tier Redis caching
│   │   ├── graph/                     # Neo4j entity/relationship extractor for GraphRAG
│   │   ├── sql/                       # PostgreSQL Text-to-SQL query engine
│   │   ├── agents/                    # LangGraph stateful agents, tools, ReAct workflows
│   │   └── rag/                       # Interchangeable RAG strategies
│   └── tests/                         # Test Suites (unit, integration, security, eval)
├── frontend/                          # Enterprise Web UI (index.html, styles, services)
└── docs/                              # Architecture, HLD, LLD, diagrams, and test matrix
```

---

## 4. Complete RAG & Agent Evaluation Suite

Evaluation is a core pillar of this platform. Every RAG strategy must be systematically and measurably evaluated across **Quality**, **Latency**, **Cost**, and **Security**.

### Standard Evaluation Metrics
1. **Retrieval Metrics**:
   - **Context Precision**: Ratio of relevant chunks in retrieved context to total chunks retrieved.
   - **Context Recall**: Ratio of relevant chunks retrieved to total ground-truth chunks needed.
   - **Hit Rate**: Percentage of queries for which at least one relevant document was retrieved.
   - **MRR (Mean Reciprocal Rank)**: Reciprocal rank of the first relevant document.
   - **nDCG (Normalized Discounted Cumulative Gain)**: Multi-level relevance scoring position accuracy.
2. **Generation Quality Metrics (RAGAS & DeepEval)**:
   - **Faithfulness**: Extent to which the LLM answer is derived strictly from the provided context (detecting hallucinations).
   - **Answer Relevancy**: Extent to which the answer directly addresses the user prompt.
   - **Correctness / Similarity**: Semantic correctness against ground-truth golden dataset.
3. **Operational Metrics**:
   - **Latency (P50, P95, P99)**: Breakdown across query routing, retrieval, fusion, reranking, context building, TTFT (Time-to-First-Token), and generation.
   - **Inter-Token Latency (ITL)**: Streaming token arrival intervals.
   - **Token Consumption**: Prompt tokens, completion tokens, cached tokens.
   - **Cost per Request / Tenant / Strategy**: Dynamic pricing calculation via `config/pricing.yaml`.

### Evaluation Execution Guidelines
- Use **RAGAS** and **DeepEval** programmatically inside `src/evaluation/`.
- Maintain versioned evaluation datasets in `data/evaluation/` tracked by `config/version.yaml`.
- **Never fabricate evaluation numbers**. Results must be calculated directly from live or test execution runs.
- Benchmark suites must be runnable offline in CI using `MOCK_LLM=true`.

---

## 5. Security, Governance & Guardrails

Follow **Zero Trust**, **Least Privilege**, **Defense in Depth**, and **OWASP LLM Top 10** standards.

### Server-Side RBAC & ABAC
- Enforce strict server-side authorization middleware in FastAPI.
- Roles:
  - `ADMIN`: User management, tenant config, system costs, trace inspection, security settings.
  - `ANALYST`: Document upload, RAG strategy comparison, evaluation dashboards, traces.
  - `USER`: Chat execution, viewing permitted documents and source citations.
  - `VIEWER`: Read-only summary dashboards.

### Multi-Tenancy & Data Isolation
- Every document, chunk, vector payload, cache entry, audit event, and trace must contain a `tenant_id`.
- Vector DB queries (Qdrant) and relational queries (PostgreSQL) must apply `tenant_id` filters **at the query level**. Never filter results on the client side.

### Prompt Injection & Input/Output Protection
- Treat all uploaded documents and user inputs as untrusted data.
- Enforce strict instruction/data boundary separation in `PromptBuilder`.
- Use NeMo Guardrails / OPA rules to intercept malicious prompt injection attacks.

### PII Protection
- Use **Presidio** to detect and redact sensitive personal information (SSN, credit cards, emails, phone numbers) before passing context to LLM or writing logs.

### Agent Security & Tool Boundaries
- Agents running in LangGraph must **NEVER** receive unrestricted production system access.
- Mandatory Agent Limits:
  - Max Graph Iterations (e.g. 10 loops max).
  - Tool Allowlists (only explicit, authorized functions allowed).
  - Parameter Type & Bounds Validation.
  - Execution Timeouts & Cost Capping.
- Read-only database roles for SQL RAG (no `DROP`, `UPDATE`, `INSERT`, `DELETE`).

---

## 6. Observability & LangSmith Tracing

- Use **LangSmith** as the primary backend for LLM/RAG/Agent execution tracing.
- Mandatory Metadata attached to **EVERY** trace:
  - `llm_provider`, `llm_model`
  - `rag_type`, `rag_version`
  - `agentic_framework`
  - `embedding_model`, `reranker_model`
  - `prompt_version`, `application_version`
  - `git_branch`, `git_commit`
  - `tenant_id`, `user_id`, `request_id`
- **Internal Trace Explorer**: Expose safe trace summary timelines in the backend/frontend UI (`/api/v1/traces`). Provide an "Open in LangSmith" deep link for technical admins while protecting internal chain-of-thought secrets.

---

## 7. Git Branching Strategy

Each RAG implementation must exist on a dedicated Git branch adhering strictly to:
`<LLM>-<RAG_TYPE>-<VERSION>-<AGENTIC_FRAMEWORK>`

*Examples*:
- `sarvam-105b-basic-rag-v1.0.0-none`
- `sarvam-105b-hybrid-rag-v1.0.0-none`
- `sarvam-105b-adaptive-rag-v1.0.0-langgraph`
- `sarvam-105b-corrective-rag-v1.0.0-langgraph`
- `sarvam-105b-self-rag-v1.0.0-langgraph`
- `sarvam-105b-react-rag-v1.0.0-langgraph`
- `sarvam-105b-graph-rag-v1.0.0-langgraph`
- `sarvam-105b-sql-rag-v1.0.0-langgraph`

Use `main` as the stable integration branch. Avoid generic branch names (`feature/rag`, `test`).

---

## 8. Containerization & Execution Rules

### Dockerfile & Image Standards
- **Multi-Stage Build**: Minimal production image using `python:3.11-slim` base.
- **Non-Root User**: Always run container as unprivileged `appuser` (UID 10001).
- **Zero Embedded Secrets**: Never bake `.env`, API keys, or JWT secrets into image layers.
- **Health Checks**: Mandatory `HEALTHCHECK` instructions targeting `/api/v1/health`.
- **Dependency Locking**: Copy `pyproject.toml` and `uv.lock` and install via `uv sync --frozen --no-dev`.

### Docker Compose Profiles
- `core`: FastAPI, Qdrant, Redis, PostgreSQL
- `search`: OpenSearch (Lexical index alternative)
- `graph`: Neo4j (GraphRAG backend)
- `observability`: Prometheus, Grafana, OpenTelemetry Collector
- `security`: OPA (Open Policy Agent) service

### Command Execution Standards
- **Bash Execution**: Always use shell/bash commands (`uv run`, `docker compose`, `make`) for dev, build, testing, and deployment workflows.

