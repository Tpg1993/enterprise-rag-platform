# REST API Reference — Enterprise RAG & Agentic AI Platform

> **Base URL**: `http://127.0.0.1:8000/api/v1`  
> **Interactive Documentation**: Swagger UI at `/docs` | ReDoc at `/redoc`

---

## 1. Authentication & Session Headers

### Required Request Headers
| Header | Description | Required | Example |
| :--- | :--- | :--- | :--- |
| `Content-Type` | MIME type of request body | Yes (POST) | `application/json` |
| `Authorization` | Bearer JSON Web Token (HS256) | Optional / Role Protected | `Bearer eyJhbGciOiJIUzI1Ni...` |
| `X-Correlation-ID` | Request tracking identifier for distributed tracing | Optional (Auto-generated) | `corr_8f7b209a` |

---

## 2. Authentication & Governance Endpoints

### `POST /auth/login`
Authenticates a user and returns an HS256 JWT access token.

**Request Body (`application/json`)**:
```json
{
  "email": "admin@enterprise.ai",
  "password": "Password123!"
}
```

**Response (`200 OK`)**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 86400,
  "user": {
    "user_id": "usr_admin_001",
    "email": "admin@enterprise.ai",
    "full_name": "Chief Security Officer",
    "role": "ADMIN",
    "tenant_id": "default_tenant",
    "department": "Executive Cyber & AI Governance",
    "security_clearance": "Top Secret // Sci"
  }
}
```

---

### `POST /auth/register`
Registers a new enterprise user.

**Request Body (`application/json`)**:
```json
{
  "email": "analyst.lead@enterprise.ai",
  "password": "SecurePassword123!",
  "full_name": "Senior RAG Analyst",
  "role": "ANALYST",
  "tenant_id": "default_tenant",
  "department": "Data Science",
  "security_clearance": "Secret"
}
```

**Response (`201 Created`)**:
```json
{
  "status": "SUCCESS",
  "user_id": "usr_94b1f69c",
  "message": "User registered successfully"
}
```

---

### `GET /auth/users`
Lists all registered directory users (requires `ADMIN` or `ANALYST` role).

**Response (`200 OK`)**:
```json
{
  "total": 4,
  "users": [
    {
      "user_id": "usr_admin_001",
      "email": "admin@enterprise.ai",
      "full_name": "Chief Security Officer",
      "role": "ADMIN",
      "tenant_id": "default_tenant",
      "department": "Executive Cyber & AI Governance",
      "security_clearance": "Top Secret // Sci",
      "is_active": true
    }
  ]
}
```

---

## 3. Chat & RAG Execution Endpoints

### `POST /chat`
Executes a query against any of the 14 RAG strategies. Automatically persists conversation turns to relational history when `session_id` is supplied.

**Supported Strategies (`rag_strategy`)**:
- `"AUTO"`, `"Basic"`, `"Hybrid"`, `"MMR"`, `"Reranked"`, `"Parent-Child"`, `"Multi-Query"`, `"HyDE"`, `"Adaptive"`, `"Corrective"`, `"Self-RAG"`, `"ReAct"`, `"GraphRAG"`, `"SQL-RAG"`, `"Multimodal"`

**Request Body (`application/json`)**:
```json
{
  "query": "What is the ARR Revenue and P99 Retrieval Latency reported in the enterprise metrics table?",
  "rag_strategy": "Multimodal",
  "max_context_tokens": 2048,
  "tenant_id": "default_tenant",
  "session_id": "sess_multimodal_fin",
  "enable_compression": true,
  "compression_target_ratio": 0.6,
  "temperature": 0.1,
  "top_k": 5
}
```

**Response (`200 OK`)**:
```json
{
  "answer": "Based on the enterprise metrics table in enterprise_benchmark_report.pdf:\n• ARR Revenue: $52.4 Million (Target: $50.0M — Exceeded)\n• P99 Retrieval Latency: 24.5 Milliseconds (Target: 30.0ms — Optimal)",
  "citations": [
    {
      "source": "enterprise_benchmark_report.pdf",
      "section_title": "Table 1 (Tabular Data)",
      "relevance_score": 0.9640,
      "page": 1,
      "bbox": [54.0, 110.0, 540.0, 210.0],
      "page_dimensions": {"width": 595.0, "height": 842.0},
      "content_snippet": "| Benchmark Metric | Reported Value | Target Threshold |\n| ARR Revenue | $52.4 Million | $50.0 Million |"
    }
  ],
  "rag_strategy": "Multimodal",
  "rag_version": "1.0.0",
  "model": "sarvam-105b",
  "latency_ms": 535.4,
  "ttft_ms": 133.8,
  "token_usage": {
    "prompt_tokens": 268,
    "completion_tokens": 198,
    "total_tokens": 466
  },
  "estimated_cost_usd": 0.0021,
  "retrieval_count": 4,
  "compression_ratio": 0.612,
  "tokens_saved": 144,
  "trace_id": "trace_b94e82f1"
}
```

---

### `POST /chat/sessions`
Creates a persistent conversation session container.

**Request Body (`application/json`)**:
```json
{
  "user_id": "admin@enterprise.ai",
  "tenant_id": "default_tenant",
  "title": "Quarterly Financial Analysis"
}
```

**Response (`201 Created`)**:
```json
{
  "status": "SUCCESS",
  "session": {
    "session_id": "sess_91aca9e4ab97",
    "user_id": "admin@enterprise.ai",
    "tenant_id": "default_tenant",
    "title": "Quarterly Financial Analysis",
    "created_at": 1789018756.13
  }
}
```

---

### `GET /chat/sessions`
Lists saved conversation sessions for the active tenant.

**Query Parameters**:
- `tenant_id` (string, default: `"default_tenant"`)
- `limit` (int, default: `50`)

**Response (`200 OK`)**:
```json
{
  "tenant_id": "default_tenant",
  "total_sessions": 3,
  "sessions": [
    {
      "session_id": "sess_43cb8f0722e0",
      "title": "Multimodal Financials & Latency Table Analysis",
      "message_count": 2,
      "created_at": 1789018756.10
    }
  ]
}
```

---

### `GET /chat/history`
Returns ordered message history for a specific conversation session.

**Query Parameters**:
- `session_id` (string, required)
- `tenant_id` (string, default: `"default_tenant"`)

**Response (`200 OK`)**:
```json
{
  "session_id": "sess_43cb8f0722e0",
  "tenant_id": "default_tenant",
  "total_messages": 2,
  "messages": [
    {
      "role": "user",
      "content": "What is the ARR Revenue and P99 Retrieval Latency reported in the enterprise metrics table?",
      "created_at": 1789018756.11
    },
    {
      "role": "assistant",
      "content": "Based on the enterprise metrics table...",
      "rag_strategy": "Multimodal",
      "latency_ms": 535.4,
      "cost_usd": 0.0027,
      "citations": [...]
    }
  ]
}
```

---

## 4. Document Ingestion & Management Endpoints

### `POST /documents`
Uploads, parses (extracting text, tables, figures), redacts PII, extracts metadata, embeds via BAAI/bge-m3, and indexes chunks into Qdrant, BM25, and Neo4j.

**Form Data (`multipart/form-data`)**:
- `file`: Document binary file (PDF, DOCX, TXT, MD, HTML, CSV, JSON)
- `chunk_strategy`: `"recursive"` | `"fixed"` | `"parent-child"` (default: `"recursive"`)
- `chunk_size`: integer (default: `512`)
- `chunk_overlap`: integer (default: `50`)
- `embedding_provider`: `"bge-m3"` | `"mock-fast"` (default: `"bge-m3"`)
- `tenant_id`: string (default: `"default_tenant"`)

**Response (`200 OK`)**:
```json
{
  "document_id": "doc_e6b8f35ef633",
  "filename": "enterprise_benchmark_report.pdf",
  "status": "ingested",
  "chunk_strategy": "fixed",
  "embedding_provider": "bge-m3",
  "total_chunks": 2,
  "total_tokens": 123,
  "checksum": "bae6a45a46294998e122550e7e2f6acb",
  "version": 1,
  "latency_ms": 3391.98,
  "tenant_id": "default_tenant",
  "file_size_human": "4.0 KB",
  "word_count": 110,
  "author": "Enterprise User",
  "security_classification": "Internal",
  "has_pii": false,
  "redacted_count": 0,
  "language": "en"
}
```

---

### `GET /documents`
Lists all documents currently indexed in the knowledge base for the tenant.

**Response (`200 OK`)**:
```json
[
  {
    "document_id": "doc_e6b8f35ef633",
    "filename": "enterprise_benchmark_report.pdf",
    "file_type": "pdf",
    "total_chunks": 2,
    "checksum": "bae6a45a46294998e122550e7e2f6acb",
    "version": 1,
    "tenant_id": "default_tenant",
    "chunk_strategy": "fixed",
    "embedding_provider": "bge-m3",
    "file_size_human": "4.0 KB",
    "word_count": 110,
    "security_classification": "Internal"
  }
]
```

---

## 5. Evaluation & Observability Endpoints

### `POST /evaluations/run`
Runs an automated RAGAS / DeepEval evaluation on a query/strategy pair. Persists the result into `evaluation_history`.

**Request Body (`application/json`)**:
```json
{
  "query": "Explain dense vector and BM25 RRF fusion formulas",
  "rag_strategy": "Hybrid",
  "tenant_id": "default_tenant"
}
```

**Response (`200 OK`)**:
```json
{
  "rag_strategy": "Hybrid",
  "query": "Explain dense vector and BM25 RRF fusion formulas",
  "context_precision": 0.94,
  "context_recall": 0.95,
  "faithfulness": 0.94,
  "answer_relevancy": 0.93,
  "overall_score": 0.94,
  "latency_ms": 415.8,
  "total_cost_usd": 0.0022,
  "answer": "Hybrid RAG executes dense vector retrieval and BM25 lexical search concurrently..."
}
```

---

### `GET /evaluations/history`
Returns chronological evaluation run history for trend and regression analysis.

**Response (`200 OK`)**:
```json
{
  "tenant_id": "default_tenant",
  "total_runs": 5,
  "history": [
    {
      "eval_id": "eval_71f8adb0b6f1",
      "strategy": "Reranked",
      "query": "Deep cross-attention candidate reranking evaluation",
      "context_precision": 0.98,
      "context_recall": 0.96,
      "faithfulness": 0.97,
      "answer_relevancy": 0.97,
      "overall_score": 0.97,
      "latency_ms": 520.3,
      "total_cost_usd": 0.0024
    }
  ]
}
```

---

### `GET /traces`
Returns real-time execution trace timeline from the internal LangSmith trace store.

**Response (`200 OK`)**:
```json
{
  "total_traces": 15,
  "traces": [
    {
      "trace_id": "trace_b94e82f1",
      "strategy": "Multimodal",
      "operation": "chat_synthesis",
      "latency_ms": 535.4,
      "tokens": 610,
      "tenant_id": "default_tenant",
      "timestamp": 1789019010.5,
      "status": "SUCCESS"
    }
  ]
}
```

---

## 6. System Health Endpoint

### `GET /health`
Returns live subsystem status across Qdrant, Redis, PostgreSQL, and Sarvam AI.

**Response (`200 OK`)**:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "environment": "development",
  "services": {
    "qdrant": "ready",
    "redis": "ready",
    "postgres": "ready",
    "sarvam_api": "ready"
  }
}
```

---

## 7. Strategy Catalog & Versions Manifest

### `GET /rag/strategies`
Returns full catalog metadata, category, features, version, and agentic framework for all 15 production RAG architectures.

### `GET /rag/versions`
Returns active platform version manifest from `backend/config/version.yaml`.

---

## 8. Document Re-indexing Pipeline

### `POST /documents/{document_id}/reindex`
Dynamically invalidates obsolete vector embeddings, re-chunks document with custom chunking strategy/size/overlap, re-embeds with BGE-M3, and logs an audit trail event.

---

## 9. Real-Time Chat SSE Streaming

### `POST /chat/stream`
Server-Sent Events endpoint streaming tokens with live Inter-Token Latency (ITL) and Time-to-First-Token (TTFT) metrics, Zero Trust OPA evaluation, and Presidio PII redaction.

---

## 10. Security & Audit Trail Explorer

### `GET /audit`
Returns tamper-evident security audit log entries with multi-tenant and event-type filtering (`SECURITY_BLOCK`, `PII_DETECTED`, `DOCUMENT_INGEST`, `DOCUMENT_REINDEX`, `DOCUMENT_DELETE`).

---

## 11. Tenant Quota, Rate Limiting & Financial Budget (Phase 32)

### `GET /tenants/{tenant_id}/quota`
Returns real-time token consumption, RPM rate limit, daily/monthly spend ($), and quota percentage.

**Response (`200 OK`)**:
```json
{
  "tenant_id": "default_tenant",
  "rate_limit_rpm": 60,
  "current_rpm": 4,
  "rpm_remaining": 56,
  "daily_tokens_used": 1250,
  "daily_token_limit": 500000,
  "daily_token_percent": 0.25,
  "monthly_tokens_used": 1250,
  "monthly_token_limit": 10000000,
  "daily_spend_usd": 0.00185,
  "daily_spend_limit_usd": 5.0,
  "daily_spend_percent": 0.04,
  "monthly_spend_usd": 0.00185,
  "monthly_spend_limit_usd": 50.0,
  "is_budget_exceeded": false,
  "rejection_reason": null
}
```

### `POST /tenants/{tenant_id}/quota/reset`
Resets daily and monthly token and dollar budget counters for the specified tenant.

**Rate Limit & Budget Response Headers (HTTP 429)**:
- `X-RateLimit-Limit`: Maximum requests permitted per minute.
- `X-RateLimit-Remaining`: Remaining request capacity in sliding window.
- `Retry-After`: Seconds to wait before submitting requests.
- `X-Budget-Exceeded`: `"true"` if daily/monthly token or dollar budget is exhausted.

---

## 12. Visual Document Page Layout & Citation Preview (Phase 34)

### `GET /documents/{document_id}/preview`
Retrieves document page visual layout, dimensions, text blocks, and geometric bounding boxes for interactive citation grounding.

**Query Parameters**:
- `page`: Page number (default: `1`).
- `tenant_id`: Tenant identifier (default: `default_tenant`).

**Response (`200 OK`)**:
```json
{
  "document_id": "doc_arch_spec",
  "filename": "enterprise_benchmark_report.pdf",
  "page_number": 1,
  "page_dimensions": {
    "width": 595.0,
    "height": 842.0
  },
  "blocks": [
    {
      "content": "Enterprise Benchmark & Architecture Specification Document",
      "bbox": [54.0, 72.0, 540.0, 108.0],
      "chunk_id": "doc_arch_spec_0"
    }
  ],
  "total_pages": 12
}
```

