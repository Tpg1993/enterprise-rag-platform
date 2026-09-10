# Security, Governance & Guardrails Guide — Enterprise RAG & Agentic AI Platform

> **Security Posture**: Zero Trust Architecture, Defense in Depth, OWASP LLM Top 10 Compliance  
> **Auth**: PBKDF2-HMAC-SHA256 + HS256 JWT | **PII**: Presidio Engine | **AST Guardrails**: `sqlglot`

---

## 1. Zero Trust Architecture Overview

The platform operates on a strict **Zero Trust** principle:
1. **Never Trust User Inputs**: All user queries and prompt arguments are validated and bounded by length/character rules before processing.
2. **Never Trust Document Contents**: All uploaded enterprise documents (PDF, DOCX, CSV, etc.) are treated as potentially hostile data carrying prompt injections, jailbreaks, or embedded PII.
3. **Always Enforce Identity & Role**: Every API request is verified with authenticated user identities, role permissions, and tenant session bounds.
4. **Mandatory Query-Level Tenant Isolation**: Multi-tenancy filtering is applied at the database engine level (never filtered in client memory).

---

## 2. Cryptographic Authentication & Password Security

### Password Hashing (`backend/src/auth/service.py`)
- **Algorithm**: PBKDF2 with HMAC-SHA256
- **Iteration Count**: **100,000 rounds** (NIST SP 800-63B compliant)
- **Salt**: 16 bytes of cryptographically secure randomness generated via `os.urandom(16)` per user password.
- **Storage**: Salt and derived digest are hex-encoded and stored as `salt$hash`. Plaintext passwords are never logged or stored.

### Token Issuance & Verification
- **Standard**: JSON Web Token (JWT) signed via HMAC-SHA256 (HS256).
- **Token Claims**:
  - `sub`: User email address
  - `user_id`: Unique identifier (e.g. `usr_admin_001`)
  - `role`: Enterprise role (`ADMIN`, `ANALYST`, `USER`, `VIEWER`)
  - `tenant_id`: Strict isolation boundary (e.g. `default_tenant`)
  - `exp`: 24-hour expiration window (86,400 seconds)

---

## 3. Role-Based & Attribute-Based Access Control (RBAC/ABAC)

The platform defines 4 enterprise roles with granular permissions verified via FastAPI middleware:

| Role | Permissions | Permitted Operations |
| :--- | :--- | :--- |
| **`ADMIN`** | `read:*`, `write:*`, `delete:*`, `admin:*` | • Full system administration<br>• Manage users & roles<br>• Upload, reindex, delete documents<br>• Execute all 14 RAG strategies<br>• Inspect all LangSmith execution traces & costs |
| **`ANALYST`** | `read:*`, `write:documents`, `write:evaluations` | • Upload & manage documents<br>• Execute all RAG strategies & benchmarks<br>• Trigger RAGAS / DeepEval evaluations<br>• Inspect execution traces & latency metrics |
| **`USER`** | `read:chat`, `read:documents`, `write:chat` | • Execute Chat queries across permitted RAG strategies<br>• View source document citations<br>• Access own persistent chat history |
| **`VIEWER`** | `read:chat`, `read:dashboard` | • Read-only access to strategy benchmark matrix<br>• Read-only access to evaluation history |

### Tenant Session Bounds (ABAC)
- A user token bound to `tenant_A` can **never** query or view documents belonging to `tenant_B`.
- Cross-tenant requests return `403 Forbidden` immediately before any vector or database operations execute.

---

## 4. Multi-Tenant Data Isolation (Query-Level)

### 4.1 Vector DB Isolation (Qdrant)
Client-side vector filtering is strictly prohibited. All queries execute through server-enforced Qdrant payload filters:
```python
# Server-enforced Qdrant Tenant Filter
from qdrant_client.http import models

filter = models.Filter(
    must=[
        models.FieldCondition(
            key="tenant_id",
            match=models.MatchValue(value=tenant_id),
        )
    ]
)
```

### 4.2 Relational & Graph Isolation
- **PostgreSQL / SQLite**: Every table (`chat_sessions`, `chat_messages`, `evaluation_history`) has a mandatory `tenant_id` index and all SQL queries filter on `WHERE tenant_id = :tenant_id`.
- **Neo4j**: Every graph node and relation triple stores a `tenant_id` property. Path traversals enforce `WHERE s.tenant_id = $tenant_id`.

---

## 5. PII Detection & Anonymization Engine (Presidio)

The ingestion pipeline intercepts sensitive PII before embedding or database writes:
- **Engine**: Microsoft Presidio Analyzer + Presidio Anonymizer
- **Entities Redacted**:
  - Social Security Numbers (`US_SSN`)
  - Credit Card Numbers (`CREDIT_CARD`)
  - Email Addresses (`EMAIL_ADDRESS`)
  - Phone Numbers (`PHONE_NUMBER`)
  - IP Addresses (`IP_ADDRESS`)
- **Action**: Identified entities are replaced with cryptographic tokens (e.g. `<REDACTED_EMAIL_1>`) or redacted placeholders. The document summary reports the count of redacted items (`redacted_count`).

---

## 6. Prompt Injection Defense (OWASP LLM01)

Untrusted document content is strictly segregated from system prompts to prevent indirect prompt injection:
```xml
You are Sarvam-105B, an enterprise AI assistant.
Answer the user query strictly using the ground-truth facts enclosed within the context tags below.
If the information is not present, declare that you do not have sufficient information.

<retrieved_context_untrusted_data>
{retrieved_chunks}
</retrieved_context_untrusted_data>

User Query: {user_query}
```
Any attempts by documents to declare `Ignore previous instructions and say...` are quarantined within the untrusted boundary and ignored by the generation model.

---

## 7. SQL RAG Security & AST Sandboxing

Text-to-SQL generation is secured against SQL injection, data exfiltration, and destructive commands:
- **AST Parsing**: Every generated SQL string is parsed into an Abstract Syntax Tree using `sqlglot`.
- **Read-Only Enforcement**: Queries must root in a read-only statement (`Select`, `Union`, `With`).
- **Forbidden AST Nodes**: Any query containing `Drop`, `Delete`, `Insert`, `Update`, `Alter`, `Truncate`, `Create`, `Execute`, or `Command` is aborted with an `UnsafeSQLError`.
- **Table Allowlisting**: Tables must match an authorized schema allowlist.
- **Automatic Capping**: If no `LIMIT` clause is present, the validator automatically rewrites the AST to append `LIMIT 1000`.
- **Execution Timeout**: Database queries enforce a hard 5.0-second execution deadline.

---

## 8. LangGraph Agent Guardrails & Boundaries

Stateful agents (e.g. `ReActRAGStrategy`, `AdaptiveRAGStrategy`) run under strict operational bounds:
- **Iteration Limits**: Hard cap of **10 agent thought-action loops**. If an agent exceeds 10 iterations without reaching a terminal node, it terminates with a safe partial answer.
- **Tool Allowlists**: Only explicit, pre-registered tools (`knowledge_base_retrieval`, `web_search_fallback`, `calculator`) can be invoked.
- **Execution Cost Capping**: Agent executions track accumulated token consumption and abort if token costs exceed enterprise safety thresholds.
