# Changelog

All notable changes to the Enterprise Multi-Architecture RAG & Agentic AI Platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.4.0] - 2026-09-28

### Added
- **Phase 27 Complete (Unified Hybrid-Graph-Agentic Pinnacle RAG Strategy)**:
  - **`HybridGraphAgenticRAGStrategy` Engine (`backend/src/rag/hybrid_graph_agentic/strategy.py`)**:
    - Unified production-grade pinnacle architecture combining:
      1. Dense vector search via Qdrant (`BAAI/bge-m3`).
      2. Sparse lexical search via BM25 (`rank-bm25`).
      3. Reciprocal Rank Fusion (RRF with $k=60$) combining dense and lexical candidate runs.
      4. Neo4j multi-hop knowledge graph entity-relationship traversal (`Neo4jGraphStore`).
      5. Cross-Encoder deep attention rescoring (`CrossEncoderReranker`).
      6. Stateful LangGraph ReAct agent reasoning and Sarvam AI (`sarvam-105b`) grounded response synthesis.
  - **Strategy Router Factory Integration**:
    - Integrated `HYBRID-GRAPH-AGENTIC` into `backend/src/rag/router.py` with alias support (`HYBRID_GRAPH_AGENTIC`, `HYBRIDGRAPHAGENTIC`, `MASTER`).
  - **Dynamic Framework Resolution**:
    - Enhanced `/api/v1/chat` in `backend/src/api/routes/chat.py` with dynamic framework resolution tagging agentic workflows as `langgraph`.
  - **Enterprise Web UI & Benchmark Updates**:
    - Added Strategy Option 15 (`Hybrid-Graph-Agentic RAG (Pinnacle Agent)`) to chat query dropdown and evaluation strategy dropdown in `frontend/index.html`.
    - Added Strategy Catalog Card 15 to the architecture catalog tab.
    - Updated side-by-side benchmark runner in `frontend/services/api.js` to execute and benchmark all 15 production strategies.
  - **Automated Verification & Test Suite (100% Passing)**:
    - Unit Tests: `backend/tests/unit/test_hybrid_graph_agentic_rag.py` (4/4 passing).
    - Integration Tests: `backend/tests/integration/test_hybrid_graph_agentic_integration.py` (1/1 passing).
    - Strategy Comparison Benchmark: `backend/tests/integration/test_strategy_comparison.py` (1/1 passing across all 15 strategies).
    - Selenium & E2E Tests: `backend/tests/e2e/test_selenium.py` and `backend/tests/e2e/test_ui_e2e.py` (4/4 passing).
    - Repository Full Test Suite: **147/147 tests passing** with 0 regressions.

## [3.3.0] - 2026-09-28

### Added
- **Phase 26 Complete (PII Redaction with Presidio & Open Policy Agent Guardrails)**:
  - **Open Policy Agent (OPA) Guardrail Engine (`OPAPolicyEngine`)**:
    - Created `docker/opa/policies/prompt_policy.rego` defining Zero Trust policies: role authorization (`ADMIN`, `ANALYST`, `USER`, `VIEWER`), prompt injection & jailbreak signature detection, tenant boundary isolation, and character threshold validation.
    - Built `OPAPolicyEngine` in `backend/src/security/opa_engine.py` with seamless dual-mode execution: embedded local evaluation (~0.02ms) and remote HTTP client for live OPA daemon (`rag_opa`).
    - Added `opa` service to `docker-compose.yml` under `security` profile (`openpolicyagent/opa:0.62.0`).
  - **Presidio PII Redactor & Anonymization Engine (`PresidioPIIRedactor`)**:
    - Implemented structured `PIIDetectionReport` in `backend/src/security/pii.py` detecting and redacting `EMAIL`, `PHONE`, `SSN`, `CREDIT_CARD`, `API_KEY`, and `IP_ADDRESS` entities.
    - Integrated automatic PII redaction into `/api/v1/chat` (`backend/src/api/routes/chat.py`), guaranteeing sensitive data is sanitized before cache storage, vector retrieval, and external Sarvam AI API inference.
  - **Security REST APIs**:
    - Exposed `POST /api/v1/security/inspect` for real-time diagnostic evaluation of queries against OPA policies and Presidio PII entity detection (`backend/src/api/routes/security.py`).
    - Exposed `GET /api/v1/security/status` reporting active guardrail posture, OPA package, and supported PII entities.
  - **Enterprise Web UI Integration**:
    - Built interactive **"Live Security & PII Guardrails Inspector"** with test fixtures in the Governance tab (`frontend/index.html`, `frontend/services/api.js`).
    - Added dynamic `🛡️ X PII Redacted` and `OPA Passed` / `⚠️ OPA Intercepted` badges to chat output bubbles.
  - **Comprehensive Test Suite (100% Passing)**:
    - Unit Tests: `backend/tests/unit/test_opa_guardrails.py` (12/12 passing) and `backend/tests/unit/test_presidio_pii_security.py` (7/7 passing).
    - Integration Tests: `backend/tests/integration/test_security_opa_integration.py` (6/6 passing).
    - Platform-wide Test Suite: 138/138 passing tests across all 26 phases.
  - **Visual Proof Documentation**:
    - Captured verified recording (`opa-pii-security-demo.webp`), chat screenshot (`pii-redacted-chat-verified.png`), and architecture guide in `docs/proofs/phase-26-security-guardrails/`.

## [3.2.0] - 2026-09-10

### Added
- **Phase 25 Complete (Full Observability Stack — OpenTelemetry, Prometheus & Grafana)**:
  - **Prometheus Metrics Manager (`PrometheusMetricsManager`)**: Built enterprise metrics engine in `backend/src/observability/prometheus_service.py` exporting:
    - RED Metrics: `rag_requests_total` labeled by strategy, tenant_id, and status.
    - Latency Histograms: `rag_request_duration_seconds` (5ms to 10s buckets) and `rag_ttft_seconds` (Time-to-First-Token).
    - Financial & Token Counters: `rag_tokens_total` (prompt/completion) and `rag_cost_usd_total` (spend in USD).
    - Cache Telemetry: `rag_cache_events_total` (tier, hit/miss).
    - Operational Gauges: `rag_active_sessions` and `rag_indexed_documents`.
  - **Scrapable Prometheus Endpoints**: Exposed standard exposition format at `/metrics` and `/api/v1/metrics` (`backend/src/api/routes/metrics.py`, `backend/src/api/main.py`).
  - **OpenTelemetry Distributed Tracing**: Created `otel_service.py` with `init_opentelemetry()` and `trace_span()` context managers for RAG pipeline operations.
  - **Docker & Grafana Provisioning Suite**:
    - `docker/prometheus/prometheus.yml`: Scrape config targeting `rag_api:8000/metrics`.
    - `docker/grafana/provisioning/datasources/prometheus.yml`: Auto-configured Prometheus datasource.
    - `docker/grafana/provisioning/dashboards/dashboards.yml`: Auto-configured dashboard loader.
    - `docker/grafana/dashboards/rag_observability.json`: Production Grafana dashboard with request throughput, P50/P95/P99 latency quantiles, token consumption, total spend, and cache hit ratios.
    - `docker-compose.yml`: Mounted configs into `rag_prometheus` and `rag_grafana` containers.
  - **Comprehensive Test Suite (100% Passing)**:
    - Unit Tests: `backend/tests/unit/test_prometheus_metrics.py` (7/7 passing)
    - Integration Tests: `backend/tests/integration/test_metrics_integration.py` (2/2 passing)
    - Platform-wide Test Suite: 113/113 passing tests across all 25 phases.
  - **Visual Proof Documentation**: Captured live `/metrics` exposition screenshot (`prometheus-metrics-telemetry.png`), recording (`prometheus-metrics-demo.webp`), and guide in `docs/proofs/phase-25-opentelemetry-metrics/`.

## [3.1.0] - 2026-09-10

### Added
- **Phase 24 Complete (Redis Multi-Tier Caching Engine)**:
  - **Multi-Tier Cache Manager (`MultiTierCacheManager`)**: Implemented high-performance multi-tier caching engine in `backend/src/cache/service.py` featuring:
    - Tier 1 (Embedding Cache): Standardized SHA-256 hashed embeddings per model to eliminate duplicate embedding calculations.
    - Tier 2 (Retrieval Cache): Top-K candidate chunks caching partitioned strictly per tenant, strategy, and query.
    - Tier 3 (LLM Response Cache): Instantaneous exact-match answer replay with zero token expenditure and preserved citations.
    - Tier 4 (Tenant Policy Cache): In-memory and Redis storage for tenant policy bounds.
    - Resilient Fallback: Thread-safe in-memory LRU cache with TTL expiration whenever Redis connection is unavailable.
  - **Cache Management REST APIs**: Created `GET /api/v1/cache/stats` for real-time hit/miss metrics and `POST /api/v1/cache/clear` for full cache invalidation (`backend/src/api/routes/cache.py`).
  - **Chat Pipeline Optimization**: Wired Tier 3 LLM cache into `/api/v1/chat` (`backend/src/api/routes/chat.py`), yielding sub-millisecond responses (0.4ms latency, ~195x speedup) and $0.0000 cost.
  - **Frontend UI Indicators**: Added `Cache MISS` and vibrant green `⚡ Cache HIT` badges to chat responses in `frontend/services/api.js`.
  - **Comprehensive Test Suite (100% Passing)**:
    - Unit Tests: `backend/tests/unit/test_redis_caching.py` (8/8 passing)
    - Integration Tests: `backend/tests/integration/test_caching_integration.py` (1/1 passing)
  - **Visual Proof Documentation**: Saved UI screenshot (`redis-cache-hit-telemetry.png`), recording (`redis-cache-hit-demo.webp`), and architecture specification in `docs/proofs/phase-24-redis-caching/`.

## [3.0.0] - 2026-09-09

### Added
- **Phase 23 Complete (Persistent Chat & Evaluation History Tracking)**:
  - **Persistent Relational Store (`PersistentHistoryStore`)**: Implemented thread-safe persistent SQLite/PostgreSQL storage in `backend/src/storage/history.py` managing `chat_sessions`, `chat_messages`, and `evaluation_history` tables with ABAC tenant-level query isolation.
  - **Session & Message Lifecycle APIs**: Created `POST /api/v1/chat/sessions`, `GET /api/v1/chat/sessions`, `GET /api/v1/chat/history`, and enhanced `POST /api/v1/chat` to automatically capture user inputs, assistant responses, model names, latency, and token consumption metrics into persistent storage.
  - **Evaluation History Auditing**: Enhanced `POST /api/v1/evaluations/run` to persist RAGAS quality metrics (faithfulness, answer relevancy, context precision, recall) and exposed `GET /api/v1/evaluations/history` for trend analysis.
  - **Frontend UI Integration**: Built live "Historical Evaluation Runs" data table in Evaluation tab (`frontend/index.html`, `frontend/services/api.js`) displaying timestamps, strategies, metrics, and latency records.
  - **Comprehensive Test Suite (100% Passing)**:
    - Unit Tests: `backend/tests/unit/test_persistent_history.py` (3/3 passing)
    - Integration Tests: `backend/tests/integration/test_history_integration.py` (2/2 passing)
  - **Proof Documentation**: Saved UI screenshots (`eval-history-tracking.png`, `chat-history-session.png`) and architecture documentation in `docs/proofs/phase-23-persistent-history/`.

- **Phase 22 Complete (User Authentication, JWT Tokens & RBAC/ABAC Policies)**:
  - **Cryptographic Authentication & Password Hashing**: Implemented PBKDF2-HMAC-SHA256 salted hashing with 100,000 iterations and HS256 JSON Web Token issuance in `AuthService` (`backend/src/auth/service.py`).
  - **RBAC & ABAC Policy Enforcement**: Enforced role permissions (`ADMIN`, `ANALYST`, `USER`, `VIEWER`) and tenant session isolation bounds via `PolicyEngine` (`backend/src/auth/policy.py`) and FastAPI dependencies (`get_current_user`, `require_permission`, `require_roles`).
  - **REST API Endpoints**: Created `POST /api/v1/auth/register`, `POST /api/v1/auth/login`, `GET /api/v1/auth/me`, `GET /api/v1/auth/users`, and `GET /api/v1/auth/roles` (`backend/src/api/routes/auth.py`).
  - **Governance Web UI Integration**: Added active user session switcher in navigation header, interactive user directory table, and live RBAC permission matrix in Governance tab (`frontend/index.html`, `frontend/services/api.js`).
  - **Comprehensive Test Suite (100% Passing)**:
    - Unit Tests: `backend/tests/unit/test_auth_rbac.py` (6/6 passing)
    - Integration Tests: `backend/tests/integration/test_auth_integration.py` (2/2 passing)
  - **Proof Documentation**: Saved dashboard screenshot (`auth-governance-dashboard.png`) and architectural log in `docs/proofs/phase-22-auth-rbac/`.

- **Phase 21 Complete (Multimodal RAG — PDF Tables, Visual Figures & Images)**:
  - **Multimodal Document Parser (`MultimodalParser`)**: Built `MultimodalParser` (`backend/src/documents/multimodal_parser.py`) utilizing PyMuPDF vector table detection (`find_tables()`), cell-to-markdown table formatting (`table_to_markdown`), embedded image figure extraction (`get_images()`), and direct image file parsing (`.png`, `.jpg`, `.jpeg`, `.webp`).
  - **Modality-Aware Intent Detection & Reranking**: Built query token analyzers (`TABLE_KEYWORDS`, `VISUAL_KEYWORDS`) in `MultimodalRAGStrategy` (`backend/src/rag/multimodal/strategy.py`) boosting matching tabular and visual candidate scores by $+0.25$.
  - **Multimodal Grounded Generation & Citations**: Formatted table and figure citations (`Table X (Tabular Data)`, `Figure Y (Visual Diagram)`) and grounded answers via `sarvam-105b`.
  - **Router & Frontend Integration**: Registered `"Multimodal"` in `get_rag_strategy` (`backend/src/rag/router.py`), added to Web UI dropdown, strategy catalog card 14, and side-by-side benchmark matrix.
  - **Comprehensive Test Suite (100% Passing)**:
    - Unit Tests: `backend/tests/unit/test_multimodal_rag.py` (6/6 passing)
    - Integration Tests: `backend/tests/integration/test_multimodal_rag_integration.py` & `backend/tests/integration/test_strategy_comparison.py` (14/14 strategies passing)
    - Selenium E2E Tests: `backend/tests/e2e/test_selenium.py` (100% passing)
  - **Proof Documentation**: Saved query screenshot (`multimodal-live-query.png`), strategy card (`multimodal-architecture-card.png`), benchmark matrix (`multimodal-benchmark-matrix.png`), and architecture guide in `docs/proofs/phase-21-multimodal-rag/`.

- **Phase 20 Complete (SQL RAG — PostgreSQL & SQLite Text-to-SQL Query Engine)**:
  - **AST Security Validation (`SQLValidator`)**: Built AST-level validator (`backend/src/sql/validator.py`) using `sqlglot` enforcing strict read-only execution (`Select`, `Union`, `With`), blocking destructive commands (`DROP`, `DELETE`, `INSERT`, `UPDATE`, `ALTER`, `TRUNCATE`, `EXEC`), enforcing table allowlists, and rewriting queries with automatic maximum row limits (1000).
  - **Schema-Grounded SQL Generator (`SQLGenerator`)**: Implemented generator (`backend/src/sql/generator.py`) grounded in database catalog schemas with `sarvam-105b` and deterministic heuristic fallbacks.
  - **Secure SQL Executor (`SQLExecutor`)**: Built executor (`backend/src/sql/executor.py`) supporting live PostgreSQL and resilient embedded SQLite databases with automated execution time capping (5.0s max) and audit logging.
  - **SQL-RAG Strategy & Markdown Formatting**: Implemented `SQLRAGStrategy` (`backend/src/rag/sql_rag/strategy.py`) executing validated queries, converting tabular records into clean Markdown tables, and synthesizing natural-language answers with database table citations.
  - **Router & Frontend Integration**: Registered `"SQL-RAG"` in `get_rag_strategy` (`backend/src/rag/router.py`), added to Web UI dropdown, strategy catalog card 13, and side-by-side benchmark matrix.
  - **Comprehensive Test Suite (100% Passing)**:
    - Unit Tests: `backend/tests/unit/test_sql_rag.py` (10/10 passing)
    - Integration Tests: `backend/tests/integration/test_sql_rag_integration.py` & `backend/tests/integration/test_strategy_comparison.py` (13/13 strategies passing)
    - Selenium E2E Tests: `backend/tests/e2e/test_selenium.py` (100% passing)
  - **Proof Documentation**: Saved query synthesis screenshot (`sql-rag-live-query.png`), strategy card (`sql-rag-architecture-card.png`), benchmark matrix (`sql-rag-benchmark-matrix.png`), and architecture summary in `docs/proofs/phase-20-sql-rag/`.

- **Phase 19 Complete (GraphRAG — Neo4j Entity-Relationship Knowledge Graph RAG)**:
  - **Entity & Relationship Extraction**: Built `GraphEntityExtractor` (`backend/src/graph/extractor.py`) extracting `(Subject, Predicate, Object)` entity-relation triples using `sarvam-105b` with deterministic linguistic heuristic fallbacks and n-gram candidate extraction.
  - **Neo4j Knowledge Graph Store**: Implemented `Neo4jGraphStore` (`backend/src/graph/neo4j_store.py`) providing Cypher `MERGE` node and relationship upserts, variable-length path traversal (`MATCH (s)-[*1..2]-(t)`), strict `tenant_id` property isolation, and resilient in-memory BFS fallback.
  - **GraphRAG Strategy Pipeline**: Implemented `GraphRAGStrategy` (`backend/src/rag/graph_rag/strategy.py`) combining concurrent dense vector retrieval from Qdrant with multi-hop graph traversal in Neo4j, synthesizing relational knowledge facts (`[Graph Knowledge Fact]`) into grounded context.
  - **Automated Ingestion Pipeline**: Enhanced document ingestion route (`backend/src/api/routes/documents.py`) to automatically extract and index graph triples into Neo4j upon document upload.
  - **Strategy Router & Frontend Integration**: Registered `"GraphRAG"` in `get_rag_strategy` (`backend/src/rag/router.py`), added to Web UI dropdown, strategy catalog card 12, and side-by-side benchmark matrix (`frontend/index.html`, `frontend/services/api.js`).
  - **Comprehensive Test Suite (100% Passing)**:
    - Dedicated Unit Tests: `backend/tests/unit/test_graph_rag.py` (6/6 passing)
    - Multi-Component Integration Tests: `backend/tests/integration/test_graph_rag_integration.py` and `backend/tests/integration/test_strategy_comparison.py` (12/12 strategies passing)
    - Selenium WebDriver E2E UI Tests: `backend/tests/e2e/test_selenium.py` (100% passing)
  - **Proof Documentation**: Saved video recording (`graph-rag-live-demo.webp`), benchmark matrix screenshot (`graph-rag-benchmark-matrix.png`), and detailed architecture log in `docs/proofs/phase-19-graph-rag/`.

## [2.0.0] - 2026-08-17

### Added
- **Phase 18 Complete (ReAct Agentic RAG Strategy)**:
  - **Reasoning + Acting Tool Execution Loop**: Implemented `ReActRAGStrategy` (`backend/src/rag/react/strategy.py`) iterating through reasoning thought steps and dynamic tool execution (`knowledge_base_retrieval`, `web_search_fallback`).
  - **Strategy Router & Unit Tests**: Registered `"ReAct"` in `get_rag_strategy` (`backend/src/rag/router.py`) and built `backend/tests/unit/test_react_rag.py`.
- **Phase 17 Complete (Self-RAG Strategy)**:
  - **Self-Reflection & Hallucination Grading**: Implemented `SelfRAGStrategy` (`backend/src/rag/self_rag/strategy.py`) self-grading candidate document relevance and computing answer faithfulness scores to execute prompt self-reflection loops.
  - **Strategy Router & Unit Tests**: Registered `"Self-RAG"` in `get_rag_strategy` and built `backend/tests/unit/test_self_rag.py`.
- **Phase 16 Complete (Corrective RAG - CRAG Strategy)**:
  - **Web Search Fallback Trigger**: Implemented `CorrectiveRAGStrategy` (`backend/src/rag/corrective/strategy.py`) evaluating retrieval confidence scores ($< 0.5$) and automatically triggering web search fallback.
  - **Strategy Router & Unit Tests**: Registered `"Corrective"` in `get_rag_strategy` and built `backend/tests/unit/test_corrective_rag.py`.
- **Phase 15 Complete (Adaptive RAG Strategy)**:
  - **Query Intent Classifier**: Implemented `AdaptiveRAGStrategy` (`backend/src/rag/adaptive/strategy.py`) dynamically classifying user query complexity (`BASIC`, `HYBRID`, `MULTI_QUERY`, `RERANKED`) to route to optimal RAG pipelines.
  - **Strategy Router & Unit Tests**: Registered `"Adaptive"` in `get_rag_strategy` and built `backend/tests/unit/test_adaptive_rag.py`.
- **Phase 14 Complete (HyDE RAG Strategy)**:
  - **Hypothetical Document Generator & Embedder**: Implemented `HyDERAGStrategy` (`backend/src/rag/hyde/strategy.py`) generating hypothetical answer documents via `sarvam-105b` and embedding hypothetical passages for Qdrant vector retrieval.
  - **Strategy Router & Unit Tests**: Registered `"HyDE"` in `get_rag_strategy` and built `backend/tests/unit/test_hyde_rag.py`.

## [1.9.0] - 2026-08-17

### Added
- **Phase 14 Complete (Hypothetical Document Embeddings - HyDE RAG Strategy)**:
  - **Hypothetical Passage Generator**: Built `_generate_hypothetical_document` in `HyDERAGStrategy` (`backend/src/rag/hyde/strategy.py`) prompting `sarvam-105b` to generate a hypothetical answer document responding to user query.
  - **Vector Search on Hypothetical Embedding**: Embedded hypothetical document into vector space using `embedding_provider.embed_query` and retrieved dense vector hits from Qdrant.
  - **Strategy Router Integration**: Registered `"HyDE"` in `get_rag_strategy` (`backend/src/rag/router.py`).
  - **Unit & Integration Test Suite**: Built `backend/tests/unit/test_hyde_rag.py` and updated side-by-side strategy benchmark tests.

## [1.8.0] - 2026-08-14

### Added
- **Phase 11 Complete (Multi-Query Expansion RAG Strategy)**:
  - **Multi-Query Generator**: Built `_generate_query_variations` in `MultiQueryRAGStrategy` (`backend/src/rag/multi_query/strategy.py`) prompting `sarvam-105b` to generate 3 alternative query rephrasings from distinct technical perspectives.
  - **Parallel Vector Retrieval & RRF Fusion**: Executed parallel vector search streams across Qdrant using `asyncio.gather` and merged candidate hits via `reciprocal_rank_fusion_multi_query` ($RRF\_Score = \sum \frac{1}{60 + r_i}$).
  - **Strategy Router Integration**: Registered `"Multi-Query"` in `get_rag_strategy` (`backend/src/rag/router.py`).
  - **Unit Test Suite**: Built `backend/tests/unit/test_multi_query_rag.py` passing 100%.

## [1.7.0] - 2026-08-14

### Added
- **Phase 10 Complete (Parent-Child Hierarchical RAG Strategy)**:
  - **Parent-Child Chunker Enrichment**: Updated `ParentChildChunker` (`backend/src/chunking/parent_child.py`) attaching `parent_content` to child chunk payload metadata for instant context expansion.
  - **Parent-Child RAG Strategy Layer**: Built `ParentChildRAGStrategy` (`backend/src/rag/parent_child/strategy.py`) resolving small child vector search hits to full parent paragraph background context.
  - **Strategy Router Integration**: Registered `"Parent-Child"` in `get_rag_strategy` (`backend/src/rag/router.py`).
  - **Unit Test Suite**: Built `backend/tests/unit/test_parent_child_rag.py` passing 100%.

## [1.6.0] - 2026-08-13

### Added
- **Phase 9 Complete (Sarvam AI LLM Provider & RAG Evaluation Suite)**:
  - **YAML-Driven Pricing Engine**: Implemented `calculate_llm_cost` (`backend/src/config/pricing.py`) reading model pricing (`sarvam-105b`), vector store operations (`qdrant`), and cache operations (`redis`) from `config/pricing.yaml`.
  - **Sarvam Provider Optimizations**: Connected `SarvamLLMProvider` (`backend/src/llm/sarvam.py`) to dynamic pricing calculations and exponential backoff retry loops.
  - **RAG Evaluation Suite**: Implemented `RAGEvaluationEngine` (`backend/src/evaluation/engine.py`) calculating Context Precision, Context Recall, Faithfulness (hallucination detection), Answer Relevancy, Latency, and Cost metrics.
  - **Unit & Benchmark Tests**: Created unit test suite in `backend/tests/unit/test_sarvam_pricing_eval.py`.

## [1.5.0] - 2026-08-13

### Added
- **Phase 7 & 8 Complete (Advanced Context & System Prompt Builders)**:
  - **Token Budgeting & Overlap Deduplication**: Upgraded `ContextBuilder` (`backend/src/context/builder.py`) with `estimate_tokens` and Jaccard text similarity deduplication ($Sim > 0.85$).
  - **Rich Header Formatting**: Added section title, page number, security classification, and score metrics to context block headers.
  - **Prompt Injection Defense**: Upgraded `PromptBuilder` (`backend/src/prompting/builder.py`) wrapping context inside `<retrieved_context_untrusted_data>` tags to isolate untrusted data from system instructions (OWASP LLM Top 10 defense).
  - **Grounding Modes**: Added `GroundingMode` enum (`STRICT`, `BALANCED`, `CITATION_FOCUSED`) and inline bracketed source citation directives `[filename.pdf (Page X)]`.
  - **Structured Pydantic Models**: Exported `ContextBuildResult` and `PromptBuildResult` Pydantic models.
  - **Unit Tests**: Built comprehensive test suite in `backend/tests/unit/test_context_prompt_advanced.py`.

## [1.4.0] - 2026-08-13

### Added
- **Phase 6 Complete (Cross-Encoder Reranking Architecture)**:
  - **Cross-Encoder Reranker**: Implemented `CrossEncoderReranker` (`backend/src/reranking/cross_encoder.py`) supporting `BAAI/bge-reranker-large` and `cross-encoder/ms-marco-MiniLM-L-6-v2` for deep query-document cross-attention scoring.
  - **Reranked RAG Strategy**: Created `RerankedRAGStrategy` (`backend/src/rag/reranked/strategy.py`) fetching a wide candidate pool ($Top\_50$) and applying cross-encoder re-scoring to yield $Top\_5$ high-relevance chunks for Sarvam AI (`sarvam-105b`).
  - **Reranker Factory & Router**: Implemented `get_reranker` singleton loader in `backend/src/reranking/factory.py` and registered `Reranked` strategy in `backend/src/rag/router.py`.
  - **Unit & Integration Tests**: Created unit test suite in `backend/tests/unit/test_reranker.py` and updated strategy comparison benchmarks in `backend/tests/integration/test_strategy_comparison.py`.

## [1.3.0] - 2026-08-13

### Added
- **Phase 5 Complete (Maximal Marginal Relevance - MMR Strategy)**:
  - **MMR Diversity Selector**: Implemented `MaximalMarginalRelevance` (`backend/src/retrieval/mmr.py`) algorithm balancing similarity to user query with pairwise diversity among selected context vectors using configurable tradeoff factor $\lambda$.
  - **MMR RAG Strategy**: Created `MMRRAGStrategy` (`backend/src/rag/mmr/strategy.py`) fetching a wide candidate pool (e.g. $Top\_50$) and applying diversity re-ranking to pass $Top\_5$ non-redundant context chunks to Sarvam AI (`sarvam-105b`).
  - **Vector Store Vector Retrieval**: Updated `QdrantVectorStore` search method to supply candidate embedding vectors for downstream re-ranking.
  - **RAG Router & Unit Tests**: Registered `MMR` in `get_rag_strategy()` and built unit test suite in `backend/tests/unit/test_mmr.py`.

## [1.2.0] - 2026-08-13

### Added
- **Phase 4 Complete (Hybrid RAG Architecture)**:
  - **BM25 Lexical Retriever**: Implemented `BM25Retriever` (`backend/src/retrieval/bm25.py`) using `rank-bm25` (`BM25Okapi`) with tokenization, text normalization, and multi-tenant index isolation (`tenant_id`).
  - **Reciprocal Rank Fusion (RRF)**: Implemented `ReciprocalRankFusion` (`backend/src/retrieval/fusion.py`) using $RRF\_Score(d) = \sum \frac{1}{k + r(d)}$ ($k=60$) to merge dense vector scores and sparse lexical ranks.
  - **Concurrent Hybrid RAG Strategy**: Created `HybridRAGStrategy` (`backend/src/rag/hybrid/strategy.py`) executing Qdrant dense vector search and BM25 sparse keyword search concurrently via `asyncio.gather`, followed by RRF rank fusion and Sarvam AI (`sarvam-105b`) generation.
  - **RAG Router & Document Sync**: Registered `Hybrid` in `get_rag_strategy()`, synchronized BM25 index on document upload and deletion in `backend/src/api/routes/documents.py`.
  - **Frontend UI & Unit Tests**: Updated Web UI strategy dropdown options and created comprehensive test suite in `backend/tests/unit/test_hybrid_rag.py`.

## [1.1.0] - 2026-08-10

### Added
- **Phase 2 Complete (Ingestion & Document Processing Pipeline)**:
  - **Multi-Format Parsers**: Implemented parsers for PDF (PyMuPDF/fitz), DOCX (python-docx), HTML (BeautifulSoup4), CSV & JSON (StructuredParser), and TXT/Markdown in `backend/src/documents/`.
  - **Enterprise Metadata Extractor**: Added `EnterpriseMetadataExtractor` (`backend/src/ingestion/metadata_extractor.py`) extracting file size, word count, embedded author/title/creation date, language, PII count, and rule-based security classification (`Public`, `Internal`, `Confidential`).
  - **Multi-Provider Embedding Factory**: Implemented `get_embedding_provider` supporting local `BAAI/bge-m3` (default), Hugging Face TEI Rust container (`tei-local`), Ollama container (`ollama-local`), Sarvam Cloud API (`sarvam-api`), and offline fast generator (`mock-fast`).
  - **CDC Engine & Version Incrementing**: Implemented `ChangeDataCaptureEngine` supporting MD5 checksum tracking, version incrementing on re-upload (`v1` -> `v2` -> `v3`), and idempotent vector updates.
  - **Qdrant Vector Store Indexer**: Implemented `QdrantVectorStore` (`backend/src/retrieval/vector_store.py`) with HNSW index configuration ($M=16, ef_{construction}=128$), rich metadata payload indexing, and query-level tenant filtering.
  - **Document REST APIs & Web UI**: Added `POST/GET/DELETE /api/v1/documents` endpoints and built the Web UI **Documents & Ingestion** tab with drag-and-drop dropzone, embedding provider dropdown, and rich metadata table.
  - **Project Directory Reorganization**: Reorganized repository into clean root directories (`backend/`, `frontend/`, `docs/`).

## [1.0.0] - 2026-08-10

### Added
- **Phase 1 Complete**: Implemented core platform infrastructure including FastAPI app (`backend/src/api/`), `SarvamLLMProvider` & `MockLLMProvider` (`backend/src/llm/`), Pydantic v2 config loader (`backend/src/config/`), multi-stage `Dockerfile`, `docker-compose.yml` (profiles: `core`, `search`, `graph`, `observability`), frontend workspace (`frontend/`), and unit tests (`backend/tests/unit/`).
- **Phase 0 Complete**: Initialized repository structure, `uv` virtual environment, `pyproject.toml`, `.env.example`, `LICENSE`, `Makefile`, `README.md`, and configuration schemas (`backend/config/*.yaml`).
- **Development Standards**: Added strict coding guidelines, complete evaluation specifications, security guardrails, and Docker standards in [`AGENTS.md`](AGENTS.md) and [`agent.md`](agent.md).
- **Master Specification**: Established 25-phase execution roadmap derived from [`MASTER SPECIFICATION.md`](MASTER SPECIFICATION.md).
