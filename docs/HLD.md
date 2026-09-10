# High-Level Design (HLD) — Enterprise Multi-Architecture RAG & Agentic AI Platform

> **Target LLM**: Sarvam AI (`sarvam-105b`) | **Frameworks**: LangChain & LangGraph | **Vector Store**: Qdrant | **Graph Store**: Neo4j | **Relational DB**: PostgreSQL / SQLite | **Observability**: LangSmith

---

## 1. Executive Summary

This platform is an enterprise-grade, multi-architecture Retrieval-Augmented Generation (RAG) and Agentic AI system. It implements and compares 14 interchangeable RAG strategies side-by-side, supporting unstructured documents (PDF, DOCX, TXT, HTML, Markdown), structured data (PostgreSQL Text-to-SQL), knowledge graph relations (Neo4j GraphRAG), and multimodal figures/tables (PyMuPDF vector extraction).

All strategies leverage **Sarvam-105B** for generation, local **BAAI/bge-m3** for dense 1024-dimensional embeddings, **BGE Reranker** for deep cross-attention, and **LangSmith** for granular execution tracing.

---

## 2. End-to-End System Architecture

```mermaid
flowchart TB
    subgraph Clients["Client Layer"]
        UI["Enterprise Web UI (SPA)"]
        API_Client["REST API Clients / SDK"]
    end

    subgraph Gateway["API Gateway & Middleware Layer (FastAPI)"]
        CORS["CORS Middleware"]
        AuthMid["JWT Auth & RBAC Middleware"]
        TenantMid["Tenant Context & ABAC Bounds"]
        TraceMid["Correlation ID & LangSmith Tracing"]
    end

    subgraph Routing["Query Routing & Execution Engine"]
        Router["Dynamic RAG Strategy Router (AUTO / Explicit)"]
        subgraph Strategies["14 Production RAG Strategies"]
            direction TB
            S1["Basic RAG"]
            S2["Hybrid RAG (Dense + BM25)"]
            S3["MMR RAG (Lambda=0.7)"]
            S4["Cross-Encoder Reranked"]
            S5["Parent-Child Hierarchical"]
            S6["Multi-Query Expansion"]
            S7["HyDE (Hypothetical Embeddings)"]
            S8["Adaptive RAG (LangGraph)"]
            S9["Corrective RAG (CRAG)"]
            S10["Self-RAG (Critique Loops)"]
            S11["ReAct Agentic (Tool Loop)"]
            S12["GraphRAG (Neo4j Multi-Hop)"]
            S13["SQL RAG (PostgreSQL Text-to-SQL)"]
            S14["Multimodal RAG (PDF Tables & Images)"]
        end
    end

    subgraph DataStores["Storage & Retrieval Subsystems"]
        Qdrant[("Qdrant Vector DB\n(BAAI/bge-m3 1024-dim)")]
        BM25["BM25 Lexical Inverted Index"]
        Neo4j[("Neo4j Knowledge Graph\n(Entity-Relation Triples)")]
        Postgres[("PostgreSQL / SQLite\n(Structured Enterprise Relational DB)")]
        HistoryDB[("Persistent History Store\n(chat_sessions, chat_messages, eval_history)")]
    end

    subgraph LLM_Layer["Inference & Synthesis"]
        SarvamProvider["SarvamLLMProvider\n(sarvam-105b via Live API / Mock Mode)"]
    end

    subgraph Evaluation["Evaluation & Observability"]
        LangSmith["LangSmith Distributed Traces"]
        RAGAS_DeepEval["RAGAS / DeepEval Quality Metrics\n(Precision, Recall, Faithfulness, Relevancy)"]
    end

    Clients --> Gateway
    Gateway --> Routing
    Router --> Strategies
    Strategies --> DataStores
    Strategies --> LLM_Layer
    Strategies --> Evaluation
    Strategies --> HistoryDB
```

---

## 3. Core Architectural Subsystems

### 3.1 Document Ingestion & CDC Pipeline
The ingestion pipeline processes untrusted enterprise documents through a multi-stage hygiene and enrichment pipeline before indexing.

```mermaid
sequenceDiagram
    autonumber
    actor User as Enterprise User / Analyst
    participant API as Document API (/api/v1/documents)
    participant CDC as CDC Engine (MD5 Hashing)
    participant Parser as Multimodal / Document Parser
    participant Cleaner as Text Cleaner & Presidio PII
    participant Embed as BAAI/bge-m3 Embedder
    participant Qdrant as Qdrant Vector Store
    participant BM25 as BM25 Lexical Index
    participant Neo4j as Neo4j Graph Store

    User->>API: Upload Document (PDF, DOCX, TXT, CSV, JSON)
    API->>CDC: Compute MD5 & Check Prior Versions
    CDC-->>API: Change Status (New / Unchanged / Version Incremented)
    API->>Parser: Parse file bytes
    Note over Parser: PyMuPDF extracts text, Markdown tables, and visual image figures
    Parser-->>API: ParsedDocument (Chunks with table/figure metadata)
    API->>Cleaner: Sanitize text & redact PII (SSN, credit card, email, phone)
    Cleaner-->>API: Cleaned, sanitized content
    API->>Embed: Embed chunks into 1024-dimensional vectors
    Embed-->>API: Dense vector embeddings
    par Indexing
        API->>Qdrant: Upsert vectors with tenant_id payload
        API->>BM25: Index lexical tokens
        API->>Neo4j: Extract and upsert entity-relation triples
    end
    API-->>User: Ingestion Response (document_id, version, chunks, latency)
```

### 3.2 GraphRAG Subsystem (Neo4j)
- **Entity Extraction**: `GraphEntityExtractor` parses text chunks to extract `(Subject, Predicate, Object)` entity-relation triples.
- **Graph Indexing**: Triples are persisted via Cypher `MERGE` queries tagged with `tenant_id` and `doc_id`.
- **Hybrid Traversal**: For a user query, Qdrant dense vector search retrieves top candidate chunks, while Neo4j executes variable-length path traversals (`MATCH (s)-[*1..2]-(t)`). Relational knowledge facts are synthesized alongside text passages in `ContextBuilder`.

### 3.3 SQL RAG Subsystem (PostgreSQL Text-to-SQL)
- **AST Security Sandboxing**: `SQLValidator` parses generated SQL with `sqlglot`. It strictly enforces read-only operations (`Select`, `Union`, `With`), rejects data manipulation or DDL statements (`DROP`, `DELETE`, `INSERT`, `UPDATE`, `ALTER`, `TRUNCATE`), enforces table allowlists, and injects `LIMIT 1000`.
- **Database Catalog Grounding**: `SQLGenerator` extracts live table schemas and column types to formulate syntactically valid queries for `sarvam-105b`.
- **Execution & Formatting**: `SQLExecutor` queries the database with execution timeouts (5.0s max) and formats records into GitHub-flavored Markdown tables.

### 3.4 Multimodal RAG Subsystem (PyMuPDF)
- **Vector Table Extraction**: PyMuPDF's `find_tables()` converts vector cell boundaries into Markdown tables preserving numerical alignment.
- **Visual Figure Capturing**: `get_images()` extracts visual image properties (dimensions, colorspace, page numbers).
- **Intent Reranking**: Detects `TABLE_KEYWORDS` and `VISUAL_KEYWORDS` in queries to boost table and figure candidate scores by $+0.25$, prioritizing tabular and graphical answers.

### 3.5 Persistent History & Session Store (PostgreSQL / SQLite)
- **`chat_sessions`**: Tracks conversation sessions partitioned by `tenant_id` and `user_id`.
- **`chat_messages`**: Captures user inputs, assistant responses, model names, latency, token consumption, dollar costs, and JSON citations.
- **`evaluation_history`**: Persists RAGAS and DeepEval quality metrics over time for trend analytics.

---

## 4. Multi-Tenant Data Isolation (Zero Trust)

Every document, vector payload, relational record, audit event, and trace enforces strict `tenant_id` partitioning:
- **Qdrant**: `models.Filter(must=[models.FieldCondition(key="tenant_id", match=models.MatchValue(value=tenant_id))])` applied at search time.
- **Neo4j**: Every node and relationship stores `tenant_id` and is constrained during Cypher traversal.
- **PostgreSQL / SQLite**: All queries require `WHERE tenant_id = :tenant_id`.

---

## 5. Technology Stack Summary

| Layer | Technologies |
| :--- | :--- |
| **LLM Provider** | Sarvam AI (`sarvam-105b`) with fallback `MockLLMProvider` |
| **Frameworks** | LangChain Core, LangGraph (stateful agents), Pydantic v2 |
| **API Backend** | FastAPI, Uvicorn, ASGI Middleware, Starlette |
| **Vector DB** | Qdrant (HNSW index, Cosine distance, 1024-dim BGE-M3) |
| **Lexical Index** | Local In-Memory BM25 (Okapi BM25 implementation) |
| **Graph DB** | Neo4j (Cypher query language, APOC procedures) |
| **Relational DB** | PostgreSQL / SQLite (via SQLAlchemy and persistent store) |
| **Document Parsers** | PyMuPDF (PDF, tables, images), python-docx, Beautiful Soup 4 |
| **Security & Guardrails**| Presidio Analyzer & Anonymizer, `sqlglot` AST validator, PBKDF2-HMAC-SHA256, HS256 JWT |
| **Observability** | LangSmith (OpenTelemetry-compatible tracing), Prometheus metrics |
| **Package Manager** | `uv` (exclusively, frozen lockfile `uv.lock`) |
