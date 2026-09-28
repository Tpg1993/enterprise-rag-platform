# Phase-Wise Feature, Coverage & Testing Matrix

> **Enterprise Multi-Architecture Production-Grade RAG & Agentic AI Platform**  
> **Target Framework**: Sarvam AI (`sarvam-105b`) + LangChain + LangGraph + LangSmith + Qdrant + FastAPI

---

## Executive Overview

This matrix documents the features, architectural coverage, and exact step-by-step testing procedures (automated unit/integration tests, CLI commands, API requests, and manual UI verifications) for all **25 execution phases** (Phase 0 through Phase 24).

---

## Phase 0: Repository & Environment Initialization

- **Features & Deliverables**: `uv` package manager setup, `.venv` virtual environment, `pyproject.toml`, `.env.example`, `LICENSE`, `Makefile`, `README.md`, `CHANGELOG.md`, `AGENTS.md`, `agent.md`, and `config/*.yaml` schemas.
- **What It Covers**: Baseline workspace, strict Python 3.11+ type hints, `ruff` linter rules, `mypy` strict type checking, relative filesystem paths, zero committed secrets, version tracking registry (`config/version.yaml`), pricing model (`config/pricing.yaml`), security role definitions (`config/security.yaml`), and prompt templates (`config/prompts/`).
- **How To Test It**:
  - **Environment Verification**:
    ```bash
    uv venv .venv
    uv sync --all-extras
    ```
  - **Configuration Validation**:
    ```bash
    uv run python -c "from src.config.loader import load_settings; s = load_settings(); print(s.app, s.llm)"
    ```

---

## Phase 1: Core Platform Infrastructure

- **Features & Deliverables**: FastAPI application (`src/api/main.py`), middleware (`src/api/middleware.py`), schemas (`src/api/schemas.py`), routes (`/api/v1/health`, `/api/v1/chat`), `SarvamLLMProvider` & `MockLLMProvider` (`src/llm/`), multi-stage `Dockerfile`, `docker-compose.yml` (profiles: `core`, `search`, `graph`, `observability`), and Enterprise Web UI (`frontend/`).
- **What It Covers**: REST API routing, correlation ID injection (`X-Correlation-ID`), async-first request handling, fallback Mock Mode (`MOCK_LLM=true`), Sarvam-105B API integration with exponential backoff retries, container security (non-root `appuser`), and Web UI SPA workspace.
- **How To Test It**:
  - **Automated Unit Tests**:
    ```bash
    uv run pytest tests/unit/test_api.py tests/unit/test_config.py tests/unit/test_llm.py
    ```
  - **Code Quality & Linter**:
    ```bash
    uv run ruff check src tests
    uv run mypy src
    ```
  - **Live API Health Test**:
    ```bash
    curl http://localhost:8000/api/v1/health
    ```
  - **Manual UI Test**: Open `http://localhost:3000` in browser, type a query in the chat box, click **Send**, and verify response answer with latency and cost metrics.

---

## Phase 2: Ingestion & Document Processing Pipeline

- **Features & Deliverables**: Multi-format document parsers (`backend/src/documents/` for PDF, DOCX, TXT, MD, HTML, CSV, JSON), text cleaner (`backend/src/ingestion/cleaner.py`), Presidio PII redactor (`backend/src/ingestion/pii.py`), Enterprise Metadata Extractor (`backend/src/ingestion/metadata_extractor.py`), CDC checksum engine (`backend/src/ingestion/cdc.py`), pluggable chunkers (`backend/src/chunking/`), multi-provider embedding factory (`backend/src/embeddings/` for `bge-m3`, `tei-local`, `ollama-local`, `sarvam-api`, `mock-fast`), Qdrant Vector Store (`backend/src/retrieval/vector_store.py`), Document Management APIs (`POST /api/v1/documents`, `GET /api/v1/documents`, `DELETE /api/v1/documents/{id}`), and Web UI **Documents & Ingestion** tab.
- **What It Covers**: Multi-file parsing, whitespace normalization, PII anonymization (SSNs, emails, phone numbers, credit cards), rich metadata extraction (file size, word count, embedded author/title/creation date, language, PII flags, security classification), MD5 checksum tracking, version incrementing on re-upload (`v1` -> `v2` -> `v3`), parent-child/recursive chunking, 1024-dim vector generation, HNSW index upsert, query-level tenant filtering (`tenant_id`), and document lifecycle management.
- **How To Test It**:
  - **Automated Tests**:
    ```bash
    uv run pytest backend/tests/unit/test_documents.py backend/tests/unit/test_chunking.py backend/tests/unit/test_ingestion.py
    ```
  - **API File Upload Test**:
    ```bash
    curl -X POST http://localhost:8000/api/v1/documents \
      -F "file=@README.md" \
      -F "chunk_strategy=recursive" \
      -F "chunk_size=512" \
      -F "embedding_provider=bge-m3" \
      -F "tenant_id=default_tenant"
    ```
  - **List Documents API Test**:
    ```bash
    curl http://localhost:8000/api/v1/documents?tenant_id=default_tenant
    ```
  - **Manual UI Test**: Open `http://localhost:3000`, switch to **Documents & Ingestion** tab, drag and drop a PDF or TXT file, select chunking strategy and embedding provider, click **Upload & Index**, and verify document appears in the ingested table with rich metadata columns (Size & Words, Security & PII, Version `v1`). Re-upload to verify version increments to `v2`.

---

## Phase 3: Basic RAG Strategy

- **Features & Deliverables**: `BasicRAGStrategy` (`src/rag/basic/`): Query -> BGE-M3 Vector Search -> Context Assembly -> Sarvam-105B LLM -> Answer.
- **What It Covers**: Standard baseline dense vector retrieval pipeline, similarity scoring, single-pass generation, and initial quality/latency/cost benchmarking.
- **How To Test It**:
  - **Automated Strategy Test**:
    ```bash
    uv run pytest tests/unit/test_basic_rag.py
    ```
  - **API Execution Test**:
    ```bash
    curl -X POST http://localhost:8000/api/v1/chat \
      -H "Content-Type: application/json" \
      -d '{"query": "What is the project objective?", "rag_strategy": "Basic"}'
    ```

---

## Phase 4: Hybrid RAG Strategy

- **Features & Deliverables**: Lexical BM25 search engine (`src/retrieval/bm25.py` / `rank-bm25`), Reciprocal Rank Fusion (RRF) & weighted fusion (`src/retrieval/fusion.py`), and `HybridRAGStrategy` (`src/rag/hybrid/`).
- **What It Covers**: Concurrent execution of Dense (Qdrant) and Lexical (BM25) searches, rank combination math (RRF $k=60$), keyword + semantic coverage, and hit-rate optimization.
- **How To Test It**:
  - **Automated Fusion & BM25 Test**:
    ```bash
    uv run pytest tests/unit/test_hybrid.py
    ```
  - **API Query Test**:
    ```bash
    curl -X POST http://localhost:8000/api/v1/chat \
      -H "Content-Type: application/json" \
      -d '{"query": "exact technical term", "rag_strategy": "Hybrid"}'
    ```

---

## Phase 5: Maximal Marginal Relevance (MMR) Strategy

- **Features & Deliverables**: MMR diversity algorithm (`src/retrieval/mmr.py`), candidate set reduction (`candidate_k` -> `final_k`), and `MMRRAGStrategy` (`src/rag/mmr/`).
- **What It Covers**: Trade-off between relevance precision and novelty ($\lambda$ balancing), anti-redundancy filtering, and candidate set pruning.
- **How To Test It**:
  - **Automated MMR Test**:
    ```bash
    uv run pytest tests/unit/test_mmr.py
    ```

---

## Phase 6: Local Reranking Strategy

- **Features & Deliverables**: Local Cross-Encoder Reranker (`src/reranking/` using BGE Reranker / Jina Reranker) and `RerankedRAGStrategy` (`src/rag/reranked/`).
- **What It Covers**: Multi-stage retrieval pipeline: Dense + BM25 -> Fusion -> MMR -> Cross-Encoder Reranking -> Top 5. Precision @ K improvement and score thresholding.
- **How To Test It**:
  - **Automated Reranker Test**:
    ```bash
    uv run pytest tests/unit/test_reranking.py
    ```

---

## Phase 7: Context Builder Component

- **Features & Deliverables**: Dedicated `ContextBuilder` (`src/context/`): Adjacent chunk merging, deduplication, citation preservation, relevance ordering, context compression, and token budgeting.
- **What It Covers**: Windowing boundaries, max token capping, hierarchy preservation, and source provenance tracking.
- **How To Test It**:
  - **Automated Context Builder Test**:
    ```bash
    uv run pytest tests/unit/test_context_builder.py
    ```

---

## Phase 8: Prompt Builder & Guardrails Component

- **Features & Deliverables**: `PromptBuilder` (`src/prompting/`): Versioned prompt templates (`config/prompts/`), strict grounding instructions, system instruction separation, and structured outputs.
- **What It Covers**: Anti-hallucination rules, explicit citation enforcement, refusal when evidence is missing, and prompt injection isolation boundaries.
- **How To Test It**:
  - **Automated Prompting Test**:
    ```bash
    uv run pytest tests/unit/test_prompt_builder.py
    ```

---

## Phase 9: Multi-Query & HyDE Strategies

- **Features & Deliverables**:
  - `MultiQueryRAGStrategy` (`src/rag/multi_query/`): Sarvam AI multi-query expansion -> parallel retrieval -> fusion -> reranking -> answer.
  - `HyDERAGStrategy` (`src/rag/hyde/`): Hypothetical answer generation -> dense vector retrieval -> reranking -> final generation.
- **What It Covers**: Query perspective coverage, hypothetical document embedding matching, latency vs recall trade-offs.
- **How To Test It**:
  - **Automated Multi-Query & HyDE Test**:
    ```bash
    uv run pytest tests/unit/test_multi_query.py tests/unit/test_hyde.py
    ```

---

## Phase 10: Adaptive RAG Strategy (LangGraph Orchestration)

- **Features & Deliverables**: Query Classifier & Adaptive Router (`src/rag/adaptive/`): Classifies query intent (Simple, Complex, Multi-intent, Relationship, Structured, Multi-step) and executes a stateful graph workflow in LangGraph.
- **What It Covers**: Dynamic routing, LLM-based intent recognition, execution path selection, and branch latency logging.
- **How To Test It**:
  - **Automated Adaptive Router Test**:
    ```bash
    uv run pytest tests/unit/test_adaptive_rag.py
    ```
  - **UI Test**: Select **AUTO (Adaptive Router)** in Web UI, send varied query types, and inspect chosen route.

---

## Phase 11: Corrective RAG (CRAG) Strategy

- **Features & Deliverables**: `CorrectiveRAGStrategy` (`src/rag/corrective/`): Retrieval -> Document Evaluator node -> (If relevance is low: Query Rewriter -> Secondary Retrieval) -> Generation node.
- **What It Covers**: Active self-correction, retrieval recovery loops, max iteration caps, and re-querying logic.
- **How To Test It**:
  - **Automated CRAG Test**:
    ```bash
    uv run pytest tests/unit/test_corrective_rag.py
    ```

---

## Phase 12: Self-RAG Strategy

- **Features & Deliverables**: `SelfRAGStrategy` (`src/rag/self_rag/`): Retrieval decision node -> Evidence assessment -> Generation -> Grounding assessment -> Revision loop.
- **What It Covers**: Fine-grained self-reflection tokens (`IS_RETRIEVED`, `IS_RELEVANT`, `IS_GROUNDED`), hallucination prevention, and self-evaluation.
- **How To Test It**:
  - **Automated Self-RAG Test**:
    ```bash
    uv run pytest tests/unit/test_self_rag.py
    ```

---

## Phase 13: ReAct & Agentic RAG Framework

- **Features & Deliverables**: Stateful tool-using agent (`src/agents/`, `src/rag/react/`) in LangGraph with vector search, hybrid search, SQL tool, graph search, and calculator tools.
- **What It Covers**: ReAct loop (Thought -> Action -> Observation -> Final Answer), max graph iterations limit, tool allowlists, parameter validation, execution timeouts, and cost capping.
- **How To Test It**:
  - **Automated Agent Test**:
    ```bash
    uv run pytest tests/unit/test_react_agent.py
    ```

---

## Phase 14: GraphRAG Strategy (Neo4j Integration)

- **Features & Deliverables**: Entity & relationship extraction pipeline (`src/graph/`) indexing into Neo4j graph database. Graph + Vector hybrid retrieval strategy (`src/rag/graph_rag/`).
- **What It Covers**: Knowledge graph creation, Cypher graph traversal, multi-hop reasoning, entity linkage, and relationship-heavy query answering.
- **How To Test It**:
  - **Integration Test**:
    ```bash
    docker compose --profile graph up -d
    uv run pytest tests/integration/test_graph_rag.py
    ```

---

## Phase 15: SQL RAG Strategy (PostgreSQL Integration)

- **Features & Deliverables**: Text-to-SQL engine (`src/sql/`, `src/rag/sql_rag/`): Query -> Schema Inspection -> Safe SQL Generation -> AST/Validation -> Read-Only Execution -> Answer.
- **What It Covers**: Text-to-SQL generation, SQL AST validation, read-only role enforcement, query timeouts, row limits, and SQL injection prevention.
- **How To Test It**:
  - **Automated SQL RAG Test**:
    ```bash
    uv run pytest tests/integration/test_sql_rag.py
    ```

---

## Phase 16: Multimodal RAG Strategy

- **Features & Deliverables**: Table extraction, chart processing, OCR integration, and image metadata indexing (`src/rag/multimodal/`).
- **What It Covers**: Image/table parsing, OCR text extraction, multimodal document indexing, and hybrid context packaging.
- **How To Test It**:
  - **Automated Multimodal Test**:
    ```bash
    uv run pytest tests/unit/test_multimodal.py
    ```

---

## Phase 17: LangSmith Observability & Internal Trace Explorer

- **Features & Deliverables**: LangSmith SDK integration (`src/observability/langsmith.py`) tracing every chain, graph node, retrieval step, and LLM call with metadata. Internal Trace Explorer UI & API (`GET /api/v1/traces`).
- **What It Covers**: Metadata tracking (`llm_provider`, `model`, `strategy`, `version`, `git_branch`, `git_commit`, `tenant_id`, `user_id`), safe execution tree visualization, and direct "Open in LangSmith" link jump.
- **How To Test It**:
  - **API Trace Test**:
    ```bash
    curl http://localhost:8000/api/v1/traces
    ```
  - **UI Test**: Open Web UI **LangSmith Traces** tab and inspect execution timeline.

---

## Phase 18: RAG Evaluation Suite (RAGAS & DeepEval)

- **Features & Deliverables**: Automated benchmark runner (`src/evaluation/`) calculating Context Precision, Context Recall, Faithfulness, Answer Relevancy, Hit Rate, MRR, latency, and cost. Evaluation dataset versioning (`config/version.yaml`).
- **What It Covers**: Offline/CI golden dataset benchmarking (`data/evaluation/`), quality scoring, hallucination detection, and comparative evaluation matrix.
- **How To Test It**:
  - **Run Benchmarks**:
    ```bash
    uv run python -m src.evaluation.runner
    uv run pytest tests/evaluation
    ```

---

## Phase 19: Security, RBAC/ABAC & Governance

- **Features & Deliverables**: Server-side RBAC middleware (`src/auth/`, `src/security/` for ADMIN, ANALYST, USER, VIEWER), tenant isolation filters, Presidio PII redaction, and prompt injection guardrails (NeMo / OPA rules).
- **What It Covers**: Authorization enforcement, tenant boundary protection (`tenant_id` at DB query levels), PII anonymization, input/output validation, and security audit logs (`/api/v1/audit`).
- **How To Test It**:
  - **Security Test Suite**:
    ```bash
    uv run pytest tests/security
    ```

---

## Phase 20: Full Observability Stack (OpenTelemetry, Prometheus, Grafana)

- **Features & Deliverables**: OpenTelemetry trace exporters, Prometheus metrics middleware (`src/observability/metrics.py`), and Grafana dashboard definitions (`docker/grafana/`).
- **What It Covers**: Metrics tracking for P50/P95/P99 latency breakdowns, TTFT, ITL, token usage, throughput, and estimated dollar costs.
- **How To Test It**:
  - **Metrics Endpoint Test**:
    ```bash
    curl http://localhost:8000/metrics
    ```

---

## Phase 21: Enterprise UI Dashboards

- **Features & Deliverables**: Enterprise Web UI full dashboard suite (`frontend/`): Chat interface, RAG Strategy Matrix & Comparison table, Trace Explorer, Latency/Cost/Quality real-time charts, and Admin RBAC control.
- **What It Covers**: Multi-role UI views (User, Business, Engineer, Admin), side-by-side strategy comparison, real-time metrics visualization, and administrative controls.
- **How To Test It**: Open `http://localhost:3000` in browser and test all tabs (Chat, Documents, Strategies, Comparison, Traces, Evaluations, Admin).

---

## Phase 22: Performance & Caching Optimization

- **Features & Deliverables**: Multi-tier Redis cache (`src/cache/`): Embedding cache, retrieval cache, semantic cache, and response cache with tenant/strategy key scoping. Async execution pooling and HNSW parameter tuning.
- **What It Covers**: Cache hit optimization, semantic similarity caching, connection pooling, TTFT latency reduction, and tenant-isolated cache keys.
- **How To Test It**:
  - **Performance & Load Test**:
    ```bash
    uv run pytest tests/performance
    ```

---

## Phase 23: CI/CD Pipeline & Automated Testing

- **Features & Deliverables**: GitHub Actions workflows & Makefile dev tasks executing linting, type checks, unit tests, integration tests, security tests, RAGAS quality gates, and Docker build scans.
- **What It Covers**: Automated CI gates, offline `MOCK_LLM=true` test execution, dependency lock verification (`uv.lock`), and container vulnerability scanning.
- **How To Test It**:
  - **Full CI Pipeline Local Run**:
    ```bash
    make lint
    make test
    make docker-up
    ```

---

## Phase 24: Enterprise Architecture Documentation & Diagrams

- **Features & Deliverables**: Complete documentation suite (`docs/`): `HLD.md`, `LLD.md`, `architecture.md`, `deployment.md`, `security.md`, `scalability.md`, `observability.md`, `cost-optimization.md`, and individual strategy runbooks. 24 standard Mermaid system diagrams.
- **What It Covers**: End-to-end architecture documentation, data flow diagrams, ingestion CDC sequence diagrams, security/RBAC threat models, and production deployment runbooks.
- **How To Test It**: Validate markdown rendering and Mermaid diagram syntax in `docs/architecture/diagrams.md`.

---

## Phase 25: Full Observability Stack (OpenTelemetry, Prometheus, Grafana)

- **Features & Deliverables**: `PrometheusMetricsManager` (`src/observability/prometheus_service.py`), OpenTelemetry distributed tracing (`src/observability/otel_service.py`), Prometheus scrapable endpoint (`/metrics`, `/api/v1/metrics`), Grafana dashboard provisioning (`docker/grafana/dashboards/rag_observability.json`).
- **What It Covers**: RED metrics (requests, errors, duration), latency histograms (P50, P95, P99), TTFT gauges, token consumption, financial cost tracking, and cache hit/miss telemetry.
- **How To Test It**:
  - **Automated Tests**:
    ```bash
    uv run pytest backend/tests/unit/test_prometheus_metrics.py backend/tests/integration/test_metrics_integration.py
    ```
  - **Live Scrape Test**:
    ```bash
    curl http://localhost:8000/metrics
    ```

---

## Phase 26: PII Redaction (Presidio) & Open Policy Agent (OPA) Guardrails

- **Features & Deliverables**: Rego policy definition (`docker/opa/policies/prompt_policy.rego`), `OPAPolicyEngine` (`src/security/opa_engine.py`), `PresidioPIIRedactor` (`src/security/pii.py`), Security REST APIs (`POST /api/v1/security/inspect`, `GET /api/v1/security/status`), Live Security & PII Inspector in Web UI (`frontend/index.html`, `frontend/services/api.js`).
- **What It Covers**: Zero Trust Rego security rules, prompt injection & jailbreak detection, role boundary authorization, query character bounds, entity detection and masking (`EMAIL`, `PHONE`, `SSN`, `CREDIT_CARD`, `API_KEY`, `IP_ADDRESS`), and chat response security badges (`🛡️ X PII Redacted`, `OPA Passed`, `⚠️ OPA Intercepted`).
- **How To Test It**:
  - **Automated Tests**:
    ```bash
    uv run pytest backend/tests/unit/test_opa_guardrails.py backend/tests/unit/test_presidio_pii_security.py backend/tests/integration/test_security_opa_integration.py
    ```
  - **API Inspection Test**:
    ```bash
    curl -X POST http://localhost:8000/api/v1/security/inspect \
      -H "Content-Type: application/json" \
      -d '{"text": "Customer test@corp.com with SSN 123-45-6789", "role": "USER", "tenant_id": "default_tenant"}'
    ```
  - **Selenium E2E Test**:
    ```bash
    uv run pytest backend/tests/e2e/test_selenium.py
    ```

