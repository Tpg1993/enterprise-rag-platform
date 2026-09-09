# MASTER SPECIFICATION
# Enterprise Multi-Architecture Production-Grade RAG & Agentic AI Platform
## Sarvam AI + LangChain + LangGraph + LangSmith

---

# 1. PROJECT OBJECTIVE

Build a production-grade, enterprise-oriented, modular RAG and Agentic AI platform that demonstrates, implements, evaluates, compares, and observes multiple RAG architectures using Sarvam AI as the primary LLM provider.

This is NOT a simple chatbot.

The platform must demonstrate:

- Enterprise document ingestion
- CDC/incremental ingestion
- Document parsing
- OCR
- Cleaning and normalization
- Deduplication
- Metadata extraction
- Multiple chunking strategies
- Local embeddings
- Vector retrieval
- BM25 retrieval
- Hybrid retrieval
- MMR
- Cross-encoder reranking
- Query processing
- Query rewriting
- Query decomposition
- Multi-query retrieval
- HyDE
- Context Builder
- Prompt Builder
- Adaptive RAG
- Corrective RAG
- Self-RAG
- ReAct/Agentic RAG
- GraphRAG
- SQL RAG
- Multimodal RAG
- Parent-child RAG
- Evaluation
- Latency optimization
- Cost optimization
- Caching
- Security
- RBAC/ABAC
- Prompt-injection protection
- Tool authorization
- PII protection
- Observability
- LangSmith tracing
- OpenTelemetry
- Prometheus/Grafana
- RAGAS/DeepEval
- Enterprise UI
- RAG strategy comparison
- Versioning
- Git branch traceability
- HLD/LLD
- Architecture documentation
- Docker-based local deployment
- CI/CD readiness

The platform must be designed so that additional RAG architectures can be added without rewriting the entire system.

---

# 2. CORE ARCHITECTURAL PRINCIPLE

Build ONE reusable RAG platform with multiple interchangeable strategies.

Do NOT create completely independent applications for each RAG type.

Use shared:

- ingestion
- document processing
- chunking
- embeddings
- vector DB
- BM25
- retrieval
- reranking
- context building
- prompting
- LLM provider
- caching
- security
- evaluation
- observability
- UI
- API

Only the strategy/orchestration layer should change between RAG implementations.

Use interfaces/abstract components wherever practical.

Conceptual architecture:

                    USER
                      |
                      v
                  FRONTEND
                      |
                      v
                   FASTAPI
                      |
                 AUTH / RBAC
                      |
                      v
              QUERY PROCESSOR
                      |
                      v
               RAG ROUTER
                      |
       +--------------+----------------+
       |              |                |
       v              v                v
    SIMPLE        ADAPTIVE          AGENTIC
       |              |                |
       v              v                v
   RETRIEVAL       ROUTER           LANGGRAPH
       |              |                |
       +--------------+----------------+
                      |
               RETRIEVAL LAYER
                      |
        +-------------+-------------+
        |             |             |
        v             v             v
      Dense          BM25         Graph
     Qdrant       OpenSearch      Neo4j
        |             |             |
        +-------------+-------------+
                      |
                   FUSION
                      |
                     MMR
                      |
                  RERANKER
                      |
              CONTEXT BUILDER
                      |
               PROMPT BUILDER
                      |
                      v
                SARVAM API
                      |
                      v
                   ANSWER

Supporting platform:

Redis
PostgreSQL
LangSmith
OpenTelemetry
Prometheus
Grafana
RAGAS
DeepEval
OPA
Presidio
NeMo Guardrails

---

# 3. LLM

Use Sarvam AI as the primary LLM provider.

Primary model:

sarvam-105b

Use the official Sarvam API/SDK.

Use the official `sarvamai` Python SDK where appropriate.

The implementation must support:

- chat completion
- streaming
- asynchronous calls
- timeout
- retries
- rate-limit handling
- token usage
- model metadata
- cost calculation
- correlation IDs

Do NOT attempt to run Sarvam-105B locally.

The local laptop should run the RAG infrastructure.

Sarvam inference should happen through the Sarvam API.

Create an abstraction:

LLMProvider

with:

SarvamLLMProvider

The architecture must allow another provider to be added later without rewriting the RAG system.

---

# 4. LOCAL-FIRST ARCHITECTURE

The target development environment is a local developer laptop with limited compute.

Do NOT require local GPU inference.

Run locally:

- FastAPI
- LangChain
- LangGraph
- local embeddings
- Qdrant
- BM25
- reranker where practical
- Redis
- PostgreSQL
- Neo4j optionally
- OpenSearch optionally
- RAGAS
- DeepEval
- Langfuse optionally
- Prometheus
- Grafana
- OPA
- Presidio

Use Sarvam API for LLM generation.

All local components should preferably be open-source/self-hosted.

---

# 5. GIT BRANCHING STRATEGY

Every RAG implementation must have its own Git branch.

Mandatory branch naming convention:

<LLM>-<RAG_TYPE>-<VERSION>-<AGENTIC_FRAMEWORK>

Examples:

sarvam-105b-basic-rag-v1.0.0-none

sarvam-105b-hybrid-rag-v1.0.0-none

sarvam-105b-mmr-rag-v1.0.0-none

sarvam-105b-reranked-rag-v1.0.0-none

sarvam-105b-parent-child-rag-v1.0.0-none

sarvam-105b-multi-query-rag-v1.0.0-langchain

sarvam-105b-hyde-rag-v1.0.0-langchain

sarvam-105b-adaptive-rag-v1.0.0-langgraph

sarvam-105b-corrective-rag-v1.0.0-langgraph

sarvam-105b-self-rag-v1.0.0-langgraph

sarvam-105b-react-rag-v1.0.0-langgraph

sarvam-105b-react-rag-v1.0.0-crewai

sarvam-105b-graph-rag-v1.0.0-langgraph

sarvam-105b-sql-rag-v1.0.0-langgraph

sarvam-105b-multimodal-rag-v1.0.0-langgraph

sarvam-105b-hybrid-graph-agentic-rag-v1.0.0-langgraph

Use:

main

as the stable integration branch.

Do not use vague branches such as:

feature/rag
rag-test
agentic
experiment

---

# 6. AGENTIC FRAMEWORKS

Use LangChain for:

- LLM abstractions
- prompts
- retrievers
- tools
- chains
- integrations
- document loaders where appropriate

Use LangGraph for:

- stateful agents
- ReAct
- Corrective RAG
- Self-RAG
- Adaptive RAG where graph orchestration is useful
- multi-step workflows
- agentic GraphRAG
- SQL agents

CrewAI may be implemented as an optional comparison branch.

Do not claim a framework is used if it is not actually used.

---

# 7. LANGSMITH

Use LangSmith as the primary LLM/RAG/agent observability and tracing platform.

Trace:

- FastAPI request
- query processing
- embedding
- retrieval
- BM25
- fusion
- MMR
- reranking
- context builder
- prompt
- LLM
- LangChain chain
- LangGraph node
- agent
- tools
- SQL
- graph operations
- errors
- retries

Every trace must include metadata:

llm_provider
llm_model
rag_type
rag_version
agentic_framework
embedding_model
reranker_model
prompt_version
application_version
environment
tenant_id
user_id
request_id

Do not expose LangSmith credentials to the frontend.

Frontend:

UI
→ Backend
→ LangSmith

Never:

UI
→ LangSmith using privileged credentials.

---

# 8. INTERNAL LANGSMITH TRACE UI

Do not force users to open LangSmith for every trace.

Create an internal Trace Explorer.

Show:

- trace ID
- request ID
- timestamp
- strategy
- version
- framework
- model
- total latency
- TTFT
- token usage
- cost
- retrieval count
- reranking count
- tool count
- cache hit
- errors

Create trace detail visualization:

Query
→ Router
→ Retrieval
→ MMR
→ Reranker
→ Context Builder
→ Prompt
→ Sarvam
→ Answer

For agentic:

Agent
→ Tool
→ Observation
→ Agent
→ Tool
→ Answer

Do NOT expose private chain-of-thought.

Show safe execution summaries only.

Provide an "Open in LangSmith" button for authorized technical users.

LangSmith remains the authoritative detailed trace backend.

---

# 9. OBSERVABILITY STACK

Use:

LangSmith:
LLM/RAG/Agent traces

OpenTelemetry:
distributed tracing

Prometheus:
application/infrastructure metrics

Grafana:
metrics dashboard

Optional Langfuse:
additional self-hosted LLM observability if required.

Do not make observability a hard dependency for core application functionality.

---

# 10. PROJECT STRUCTURE

Create:

project-root/

AGENTS.md
README.md
CHANGELOG.md
LICENSE
pyproject.toml
uv.lock
.gitignore
.env.example
Makefile
Dockerfile
docker-compose.yml

config/
    version.yaml
    settings.yaml
    models.yaml
    retrieval.yaml
    security.yaml
    observability.yaml
    pricing.yaml
    prompts/

docs/
    architecture/
    rag/
    security/
    deployment/
    runbooks/

src/
    api/
    auth/
    config/
    ingestion/
    documents/
    chunking/
    embeddings/
    retrieval/
    reranking/
    context/
    prompting/
    llm/
    evaluation/
    observability/
    security/
    cache/
    graph/
    sql/
    agents/
    rag/
        base/
        basic/
        hybrid/
        mmr/
        reranked/
        parent_child/
        multi_query/
        hyde/
        adaptive/
        corrective/
        self_rag/
        react/
        graph_rag/
        sql_rag/
        multimodal/

tests/
    unit/
    integration/
    security/
    evaluation/
    performance/

data/
    raw/
    processed/
    evaluation/
    sample/

frontend/
    components/
    pages/
    services/
    styles/

scripts/

Adapt the exact structure if necessary, but maintain strict separation of concerns.

---

# 11. AGENTS.md REQUIREMENTS

Create comprehensive AGENTS.md.

It must mandate:

- coding best practices
- type hints
- formatting
- linting
- testing
- secure coding
- modular architecture
- dependency injection
- no duplicated business logic
- no hardcoded secrets
- no static paths
- configuration-driven behavior
- environment-specific configuration
- version tracking
- Git traceability
- observability
- RAG quality measurement
- security
- documentation

Mandatory:

Use `uv`.

Use `.venv`.

Create and activate `.venv` before installing dependencies.

Install all project dependencies inside `.venv`.

Do not install project packages globally.

Do not commit `.env`.

Do not commit secrets.

Never use absolute/static filesystem paths.

Use project-root-relative or configuration-driven paths.

---

# 12. PYTHON ENVIRONMENT

Use:

Python 3.11+

uv

.venv

pyproject.toml

uv.lock

Required setup:

uv venv

activate .venv

uv sync

All commands must run against the project environment.

---

# 13. DOCUMENT INGESTION

Pipeline:

Source
→ CDC
→ Parse
→ OCR
→ Clean
→ Normalize
→ Metadata
→ Deduplicate
→ Chunk
→ Embed
→ Index

Support:

PDF
DOCX
TXT
HTML
Markdown
CSV
JSON

Use:

PyMuPDF
Docling
python-docx
BeautifulSoup
Tesseract/PaddleOCR

where appropriate.

---

# 14. CDC / INCREMENTAL INGESTION

Implement:

- checksum
- version tracking
- modified detection
- deleted detection
- idempotent ingestion
- chunk invalidation
- vector upsert/delete

Do not reprocess unchanged documents.

Document version must be traceable.

---

# 15. DOCUMENT CLEANING

Implement:

- HTML cleaning
- whitespace normalization
- encoding normalization
- boilerplate removal
- duplicate removal
- malformed content handling
- metadata extraction

Treat documents as untrusted input.

---

# 16. CHUNKING

Implement pluggable:

- fixed-size
- recursive
- semantic
- sentence
- structure-aware
- parent-child

Store:

document_id
tenant_id
chunk_id
parent_id
chunk_index
page
section
token_count
metadata

Make chunk size and overlap configurable.

---

# 17. EMBEDDINGS

Use local embeddings.

Default:

BGE-M3 or another configurable multilingual embedding model.

Do not use a paid embedding API by default.

Support:

- batching
- normalization
- caching
- versioning
- dimension validation

Track embedding model version.

---

# 18. VECTOR DATABASE

Primary:

Qdrant

Optional:

FAISS

Qdrant must support:

- HNSW
- filtering
- tenant isolation
- metadata
- persistence
- upsert
- delete
- search

Expose:

M
ef_construction
ef_search

Do not claim universal optimal HNSW settings.

Benchmark quality vs latency.

---

# 19. BM25

Implement:

rank-bm25

for lightweight mode.

Optionally:

OpenSearch

for production-like mode.

---

# 20. HYBRID RETRIEVAL

Dense:

Qdrant

Lexical:

BM25/OpenSearch

Combine using:

- Reciprocal Rank Fusion
- weighted fusion

Run dense and lexical retrieval concurrently when practical.

---

# 21. MMR

Implement:

retrieval
→ candidate set
→ MMR
→ reduced candidate set

Example default:

Top 50
→ MMR
→ Top 20

Make configurable:

lambda
candidate_k
final_k

Do not automatically use MMR if evaluation shows it reduces quality.

---

# 22. RERANKER

Implement local cross-encoder reranking.

Support:

BGE Reranker
Jina Reranker

Example:

Top 50
→ MMR
→ Top 20
→ Reranker
→ Top 5–10

Use batching.

Track:

reranker latency
candidate count
scores
final count

---

# 23. QUERY PROCESSING

Implement:

- normalization
- intent detection
- entity extraction
- query routing
- rewriting
- expansion
- decomposition
- multi-query
- HyDE

Routing principle:

Simple query
→ direct retrieval

Complex query
→ rewrite/decompose

Multi-intent
→ decomposition

Relationship-heavy
→ GraphRAG

Structured-data query
→ SQL RAG

Multi-step/tool-based
→ Agentic RAG

Avoid unnecessary LLM calls.

---

# 24. CONTEXT BUILDER

Dedicated component.

Responsibilities:

- deduplication
- adjacent chunk merging
- source preservation
- citation preservation
- relevance ordering
- context compression
- token budget
- document hierarchy

Context Builder answers:

"What evidence should reach the LLM?"

---

# 25. PROMPT BUILDER

Separate from Context Builder.

Prompt Builder answers:

"How should evidence and instructions be packaged for the LLM?"

Use versioned prompts.

Track:

prompt_id
prompt_version
strategy

Prompts must require:

- grounding
- citations
- refusal when evidence is insufficient
- safe behavior
- structured output where appropriate

---

# 26. BASIC RAG

Implement:

Query
→ embedding
→ vector search
→ context
→ Sarvam
→ answer

Use this as baseline.

---

# 27. HYBRID RAG

Implement:

Query
→ Dense + BM25
→ fusion
→ context
→ Sarvam

---

# 28. MMR RAG

Implement:

Query
→ retrieval
→ MMR
→ context
→ Sarvam

---

# 29. RERANKED RAG

Implement:

Query
→ Hybrid
→ MMR
→ Cross Encoder
→ Context
→ Sarvam

---

# 30. PARENT-CHILD RAG

Implement:

small child chunks
→ retrieve child
→ resolve parent
→ build context
→ rerank
→ Sarvam

---

# 31. MULTI-QUERY RAG

Implement:

Query
→ Sarvam generates search queries
→ parallel retrieval
→ fusion
→ reranking
→ context
→ final Sarvam answer

Limit number of generated queries.

Track cost and latency.

---

# 32. HYDE

Implement:

Query
→ hypothetical answer generation
→ embedding
→ retrieval
→ rerank
→ final generation

Evaluate whether HyDE improves retrieval quality.

---

# 33. ADAPTIVE RAG

Implement router:

Query
→ classifier/router

Routes:

simple
→ Hybrid

complex
→ Rewrite
→ Hybrid

multi-intent
→ Decompose
→ parallel retrieval

relationship-heavy
→ GraphRAG

structured
→ SQL RAG

multi-step
→ ReAct

Track:

route
confidence
reason
latency
cost

---

# 34. CORRECTIVE RAG

Implement:

Query
→ Retrieval
→ Evaluate retrieval

Good:
→ Generate

Bad:
→ Rewrite
→ Retrieve again

Limit correction iterations.

---

# 35. SELF-RAG

Implement:

Query
→ retrieval decision
→ retrieval
→ evidence evaluation
→ generation
→ grounding evaluation
→ revision if required

Limit:

iterations
LLM calls
execution time
cost

Do not expose private reasoning.

---

# 36. REACT / AGENTIC RAG

Use:

LangChain
+
LangGraph

Implement tools:

- vector search
- hybrid search
- document search
- SQL
- graph search
- calculator
- approved APIs

Workflow:

User
→ Agent
→ Tool
→ Observation
→ Agent
→ Tool
→ Final answer

Use explicit state.

State includes:

query
plan
actions
observations
documents
tool results
final answer

Do not expose chain-of-thought.

Expose safe action summaries.

---

# 37. AGENT SECURITY

Use:

RBAC/ABAC
OPA
tool allowlists
argument validation
timeouts
rate limits
sandboxing
maximum iterations
maximum tool calls
maximum execution time
maximum cost
audit logging

Agents must not receive unrestricted production credentials.

---

# 38. GRAPHRAG

Use:

Neo4j

Pipeline:

Documents
→ entities
→ relationships
→ graph
→ graph retrieval
→ vector retrieval
→ hybrid context
→ Sarvam

Use GraphRAG for multi-hop/relationship-heavy queries.

---

# 39. SQL RAG

Use PostgreSQL.

Flow:

Query
→ classification
→ SQL generation
→ SQL validation
→ authorization
→ read-only SQL
→ result
→ Sarvam

Security:

- read-only role
- allowlist
- SQL validation
- query timeout
- row limits
- no destructive commands
- audit

---

# 40. MULTIMODAL RAG

Support:

- text
- images
- tables
- diagrams
- scanned documents

Use appropriate local parsers/OCR.

Keep document processing provider-agnostic.

---

# 41. SECURITY

Implement:

Authentication
Authorization
RBAC
ABAC where required
tenant isolation
document ACL
audit logging

Roles:

ADMIN
ANALYST
USER
VIEWER

Enforce authorization server-side.

---

# 42. PROMPT INJECTION

Treat retrieved documents as untrusted.

Implement:

- instruction/data separation
- input validation
- output validation
- guardrails
- tool authorization
- policy checks
- least privilege

Optionally:

NeMo Guardrails
Presidio
OPA

Do not rely solely on LLM-based security.

---

# 43. PII

Use Presidio or equivalent.

Detect/redact sensitive information.

Do not log raw sensitive content unnecessarily.

---

# 44. CACHE

Use Redis.

Implement:

- embedding cache
- retrieval cache
- semantic cache
- response cache

Cache keys must include:

tenant
authorization context
strategy
model/version where relevant

Never leak cached data across users/tenants.

---

# 45. RBAC UI

Build different views.

ADMIN:

- users
- roles
- tenants
- costs
- configuration
- security
- traces

ANALYST:

- documents
- RAG comparison
- evaluation
- traces

USER:

- chat
- permitted sources

VIEWER:

- read-only dashboards

---

# 46. UI

Build a professional enterprise UI.

Main sections:

Dashboard
Chat
Documents
RAG Strategies
RAG Comparison
Traces
Evaluations
Cost
Latency
Security
Administration

---

# 47. CHAT UI

Show:

- answer
- citations
- source documents
- RAG strategy
- RAG version
- model
- latency
- TTFT
- token usage
- estimated cost
- cache status

Do not expose chain-of-thought.

---

# 48. RAG STRATEGY SELECTOR

Allow:

AUTO

Basic
Hybrid
MMR
Reranked
Parent-Child
Multi-Query
HyDE
Adaptive
Corrective
Self-RAG
ReAct
GraphRAG
SQL RAG
Multimodal

---

# 49. EXECUTION TRACE UI

Show safe execution timeline.

Example:

Query
→ Router
→ Retrieval
→ MMR
→ Reranker
→ Context Builder
→ Prompt
→ Sarvam
→ Answer

Agentic:

Agent
→ Tool
→ Observation
→ Agent
→ Tool
→ Answer

Show:

latency
status
counts
scores
source IDs
token usage

Do not show private reasoning.

---

# 50. LANGSMITH TRACE EXPLORER

Create:

/traces

Filters:

date
user
tenant
strategy
version
model
status
latency
trace ID

Show:

trace ID
request ID
strategy
version
framework
model
latency
TTFT
tokens
cost
retrieval count
reranker count
tool count
errors

Provide:

Open in LangSmith

for authorized technical users.

---

# 51. LATENCY DASHBOARD

Show:

P50
P95
P99

Break down:

query processing
embedding
dense retrieval
BM25
fusion
MMR
reranking
context builder
prompt builder
LLM TTFT
generation
total latency

---

# 52. COST DASHBOARD

Show:

input tokens
output tokens
cached tokens
LLM calls
retrieval calls
reranker calls
cost/request
cost/user
cost/tenant
cost/strategy
estimated monthly cost

Use config/pricing.yaml.

Never hardcode pricing in application logic.

---

# 53. QUALITY DASHBOARD

Show:

Recall@K
Precision@K
MRR
nDCG
Hit Rate
Context Precision
Context Recall
Faithfulness
Answer Relevancy
Correctness

Use:

RAGAS
DeepEval
LangSmith evaluations

---

# 54. RAG COMPARISON

Allow comparing strategies:

Basic
Hybrid
MMR
Reranked
Adaptive
Corrective
Self-RAG
ReAct
GraphRAG
SQL RAG
Multimodal

Compare:

quality
latency
TTFT
ITL
cost
LLM calls
retrieval calls
tool calls
complexity
security
maintainability

Never fabricate benchmark data.

---

# 55. ITL

Measure:

Inter-token latency

where the provider exposes sufficient streaming information.

Also measure:

TTFT
total generation latency
tokens/second where available

---

# 56. VERSIONING

Create:

config/version.yaml

Track:

application_version
rag_version
llm_model
embedding_model
reranker_model
prompt_version
evaluation_dataset_version
configuration_version
agentic_framework

Use semantic versioning.

---

# 57. UI VERSION TRACEABILITY

Display:

LLM:
Sarvam-105B

RAG:
Adaptive RAG

RAG Version:
v1.0.0

Framework:
LangGraph

Embedding:
BGE-M3

Reranker:
BGE Reranker

Prompt:
v2.1

Git Commit:
abc123

LangSmith Trace:
trace-id

This metadata must be dynamically loaded.

---

# 58. REPRODUCIBILITY

Every answer should be traceable to:

Git branch
Git commit
RAG version
LLM
embedding
reranker
prompt
configuration
evaluation dataset

This must be recorded in LangSmith metadata and application metadata.

---

# 59. DATABASES

PostgreSQL tables:

users
roles
permissions
tenants
documents
document_versions
chunks
ingestion_jobs
rag_requests
rag_traces
evaluations
audit_events
cost_events

Use migrations.

---

# 60. VECTOR SCHEMA

Each vector payload should include:

document_id
chunk_id
tenant_id
parent_id
source
page
section
document_version
embedding_model
metadata
ACL information

---

# 61. MULTI-TENANCY

Every request and stored object must include:

tenant_id

Apply tenant filtering to:

documents
chunks
vectors
cache
traces
audit
evaluation

Never rely on frontend filtering.

---

# 62. API

Implement:

POST /api/v1/chat

POST /api/v1/documents

DELETE /api/v1/documents/{id}

POST /api/v1/documents/{id}/reindex

GET /api/v1/rag/strategies

GET /api/v1/rag/versions

GET /api/v1/traces

GET /api/v1/traces/{id}

GET /api/v1/metrics

GET /api/v1/evaluations

POST /api/v1/evaluations/run

GET /api/v1/health

GET /api/v1/readiness

GET /api/v1/audit

Use:

Pydantic
API versioning
validation
structured errors

---

# 63. CHAT RESPONSE

Return safe metadata:

answer
citations
sources
rag_strategy
rag_version
framework
model
latency_ms
ttft_ms
token_usage
estimated_cost
retrieval_count
reranked_count
cache_hit
trace_id

Never return:

API keys
credentials
private chain-of-thought
unauthorized content
system secrets

---

# 64. PERFORMANCE OPTIMIZATION

Implement:

CDC
precomputed embeddings
embedding cache
semantic cache
metadata filtering
HNSW tuning
parallel retrieval
candidate reduction
MMR on limited candidates
batched reranking
context compression
token budgeting
streaming
async execution
connection pooling
timeouts
retries
circuit breakers

Optimization must be validated against RAG quality.

---

# 65. ERROR HANDLING

Implement:

- exponential backoff
- timeout
- retry
- circuit breaker
- rate-limit handling
- fallback
- graceful degradation

Do not expose raw provider errors.

---

# 66. FALLBACKS

Examples:

Sarvam unavailable
→ configured fallback

Reranker unavailable
→ retrieval without reranker

Graph unavailable
→ vector retrieval when appropriate

Redis unavailable
→ continue without cache

Observability unavailable
→ core application continues

---

# 67. TESTING

Unit tests:

- parsing
- cleaning
- chunking
- embeddings
- retrieval
- BM25
- fusion
- MMR
- reranking
- context builder
- prompt builder
- routing
- cost

Integration:

- Qdrant
- Redis
- PostgreSQL
- Neo4j
- OpenSearch
- Sarvam mocked

Security:

- RBAC
- tenant isolation
- ACL
- prompt injection
- SQL injection
- tool authorization
- secret leakage
- path traversal

Performance:

- concurrency
- latency
- retrieval throughput
- cache performance

---

# 68. MOCK MODE

Implement:

MOCK_LLM=true

When enabled:

- no Sarvam calls
- deterministic responses
- deterministic token usage
- predictable latency

CI must work without Sarvam API credentials.

---

# 69. CI/CD

Pipeline:

lint
→ type check
→ unit tests
→ integration tests
→ security tests
→ RAG evaluation
→ dependency scan
→ Docker build
→ container scan

Block promotion when quality/security gates fail.

---

# 70. DOCKER

Use:

Dockerfile
docker-compose.yml

Requirements:

- non-root
- minimal image
- healthcheck
- no secrets in image
- deterministic dependencies
- multi-stage build where useful

Docker Compose profiles:

core
search
graph
observability
security

Default core:

FastAPI
Qdrant
Redis
PostgreSQL

Optional:

OpenSearch
Neo4j
Prometheus
Grafana
Langfuse
OPA

---

# 71. NO STATIC PATHS

Never use:

/Users/...
C:\Users\...
/home/...

Use:

project-root-relative paths
configuration
environment variables

---

# 72. SECRETS

Never commit:

SARVAM_API_KEY
database passwords
JWT secrets
LangSmith API keys
certificates
tokens

`.env.example` must contain placeholders only.

Frontend must never contain backend secrets.

---

# 73. DOCUMENTATION

Generate:

README.md
AGENTS.md
HLD.md
LLD.md
architecture.md
deployment.md
security.md
scalability.md
observability.md
disaster-recovery.md
cost-optimization.md
performance.md
testing.md

Also create a document for every RAG architecture.

---

# 74. REQUIRED DIAGRAMS

Use Mermaid.

Generate:

1. Overall architecture
2. Ingestion
3. CDC
4. Query processing
5. Basic RAG
6. Hybrid RAG
7. MMR
8. Reranking
9. Adaptive RAG
10. Corrective RAG
11. Self-RAG
12. ReAct
13. GraphRAG
14. SQL RAG
15. Multimodal RAG
16. Security
17. RBAC
18. LangSmith observability
19. OpenTelemetry
20. CI/CD
21. Deployment
22. Failure/fallback
23. Cache
24. Multi-tenancy

---

# 75. HLD

Explain:

- frontend
- API
- authentication
- authorization
- RAG router
- query processing
- retrieval
- vector DB
- BM25
- MMR
- reranker
- context builder
- prompt builder
- LLM
- agents
- tools
- graph
- SQL
- caching
- security
- evaluation
- observability

---

# 76. LLD

Document:

- modules
- classes
- interfaces
- APIs
- schemas
- vector schema
- graph schema
- database schema
- cache keys
- LangGraph state
- tool contracts
- configuration

---

# 77. BUSINESS REQUIREMENTS

UI must serve both:

## Individual User

Need:

- simple chat
- sources
- citations
- strategy used
- response time
- confidence/relevance indicator

## Business User

Need:

- business answer
- evidence
- data freshness
- latency
- cost
- source provenance

## Engineer

Need:

- trace
- retrieval
- reranker
- prompt
- model
- tokens
- latency breakdown
- tool execution

## Admin

Need:

- users
- RBAC
- tenants
- cost
- security
- system health
- audit

---

# 78. SECURITY STANDARD

Follow:

Zero Trust
Least Privilege
Defense in Depth
Secure Defaults
Input Validation
Output Validation
RBAC
ABAC where necessary
Tenant Isolation
Secrets Management
Auditability
Prompt Injection Defense
Tool Authorization

Use OWASP guidance where applicable.

---

# 79. COST OPTIMIZATION

The platform should demonstrate:

- local embeddings
- local vector DB
- local reranker
- caching
- candidate reduction
- model routing
- minimal LLM calls
- query routing
- prompt optimization
- context compression
- streaming
- token budgets

The expensive component should primarily be Sarvam inference.

---

# 80. RAG STRATEGY MATRIX

Create documentation/UI showing:

| Strategy | Main Purpose |
|---|---|
| Basic RAG | baseline |
| Hybrid RAG | semantic + lexical |
| MMR | diversity |
| Reranked RAG | relevance precision |
| Parent-Child | context preservation |
| Multi-Query | query coverage |
| HyDE | retrieval improvement |
| Adaptive RAG | dynamic routing |
| Corrective RAG | retrieval recovery |
| Self-RAG | self-evaluation |
| ReAct RAG | tool-using agent |
| GraphRAG | relationships/multi-hop |
| SQL RAG | structured data |
| Multimodal RAG | images/tables/documents |

---

# 81. FRAMEWORK COMPARISON

Where useful, implement ReAct using:

LangGraph
LangChain
CrewAI

using separate branches.

Example:

sarvam-105b-react-rag-v1.0.0-langgraph

sarvam-105b-react-rag-v1.0.0-langchain

sarvam-105b-react-rag-v1.0.0-crewai

Compare:

quality
latency
TTFT
ITL
cost
LLM calls
tool calls
failure rate
observability
security
complexity
maintainability

Do not claim one is best without benchmark evidence.

---

# 82. VERSION REGISTRY

Create:

config/version.yaml

Track:

application
RAG strategy
LLM
embedding
reranker
prompt
framework
evaluation dataset
configuration

Example:

application:
  version: "1.0.0"

models:
  llm:
    provider: sarvam
    model: sarvam-105b

  embedding:
    model: bge-m3

  reranker:
    model: bge-reranker

rag:
  adaptive:
    version: "1.0.0"
    framework: langgraph

  react:
    version: "1.0.0"
    framework: langgraph

---

# 83. LANGSMITH METADATA

Every trace should include:

llm_provider
llm_model
rag_type
rag_version
agentic_framework
embedding_model
reranker_model
prompt_version
application_version
environment
git_branch
git_commit
tenant_id
user_id
request_id
evaluation_dataset_version

---

# 84. REPRODUCIBLE RAG

Every answer must be traceable to:

Git branch
Git commit
RAG version
LLM
embedding
reranker
prompt
configuration
evaluation dataset

This is mandatory for production-grade experiment tracking.

---

# 85. DEVELOPMENT PHASES

Do NOT generate the entire project blindly in one step.

Implement sequentially.

## Phase 0 — Repository

- Git
- branches
- AGENTS.md
- README
- uv
- .venv
- pyproject
- configuration
- versioning

## Phase 1 — Core Platform

- FastAPI
- frontend
- Sarvam integration
- Docker
- Qdrant
- Redis
- PostgreSQL

## Phase 2 — Ingestion

- parser
- cleaning
- CDC
- chunking
- embeddings
- indexing

## Phase 3 — Basic RAG

## Phase 4 — Hybrid RAG

## Phase 5 — MMR

## Phase 6 — Reranking

## Phase 7 — Context Builder

## Phase 8 — Prompt Builder

## Phase 9 — Multi-Query / HyDE

## Phase 10 — Adaptive RAG

## Phase 11 — Corrective RAG

## Phase 12 — Self-RAG

## Phase 13 — ReAct/Agentic RAG

## Phase 14 — GraphRAG

## Phase 15 — SQL RAG

## Phase 16 — Multimodal RAG

## Phase 17 — LangSmith

## Phase 18 — RAGAS/DeepEval

## Phase 19 — Security/RBAC

## Phase 20 — Observability

## Phase 21 — UI dashboards

## Phase 22 — Performance optimization

## Phase 23 — CI/CD

## Phase 24 — Production documentation

After every phase:

- run tests
- validate services
- validate APIs
- validate UI
- update version
- update CHANGELOG
- update documentation
- update diagrams
- create Git commit

---

# 86. PHASE ACCEPTANCE

Do not move to the next phase until the current phase:

- builds
- starts
- passes tests
- has documentation
- has working UI where applicable
- has no known security blocker

---

# 87. FINAL ACCEPTANCE CRITERIA

The platform is complete only when:

- all RAG architectures are implemented
- each architecture has a branch
- branch naming convention is followed
- RAG versions are tracked
- Git commit is traceable
- Sarvam API works
- local embeddings work
- Qdrant works
- BM25 works
- hybrid search works
- MMR works
- reranking works
- context builder works
- prompt builder works
- adaptive routing works
- corrective RAG works
- self-RAG works
- ReAct works
- LangChain is used appropriately
- LangGraph is used appropriately
- GraphRAG works
- SQL RAG works
- multimodal RAG is supported
- LangSmith tracing works
- internal Trace Explorer works
- RAGAS/DeepEval evaluation works
- latency metrics work
- TTFT/ITL metrics work where available
- cost metrics work
- RBAC works
- tenant isolation works
- prompt injection protections exist
- tool authorization exists
- PII protection exists
- caching works
- Docker works
- uv/.venv works
- no static paths exist
- no secrets are committed
- tests pass
- security tests pass
- documentation is complete
- HLD exists
- LLD exists
- Mermaid diagrams exist
- CI/CD is documented
- production deployment path is documented

---

# 88. FINAL TARGET ARCHITECTURE

                              USERS
                                |
                                v
                         ENTERPRISE UI
                  +-------------+-------------+
                  |             |             |
                 CHAT       DASHBOARD       ADMIN
                  |             |             |
                  +-------------+-------------+
                                |
                                v
                            FASTAPI
                                |
                         AUTH / RBAC / ABAC
                                |
                                v
                         QUERY PROCESSOR
                                |
                                v
                         ADAPTIVE ROUTER
                                |
             +------------------+------------------+
             |                  |                  |
             v                  v                  v
          BASIC             ADVANCED            AGENT
           RAG                RAG              LANGGRAPH
             |                  |                  |
             +------------------+------------------+
                                |
                         RETRIEVAL LAYER
                                |
             +------------------+------------------+
             |                  |                  |
           QDRANT              BM25              NEO4J
          Dense             Keyword             Graph
             |                  |                  |
             +------------------+------------------+
                                |
                              FUSION
                                |
                               MMR
                                |
                            RERANKER
                                |
                         CONTEXT BUILDER
                                |
                         PROMPT BUILDER
                                |
                                v
                         SARVAM-105B API
                                |
                                v
                         OUTPUT GUARDRAILS
                                |
                                v
                              ANSWER

       +--------------------------------------------------+
       |                  OBSERVABILITY                    |
       |                                                  |
       | LangSmith | OpenTelemetry | Prometheus | Grafana |
       +--------------------------------------------------+

       +--------------------------------------------------+
       |                     SECURITY                      |
       |                                                  |
       | RBAC | ABAC | OPA | Presidio | Guardrails       |
       +--------------------------------------------------+

       +--------------------------------------------------+
       |                    EVALUATION                    |
       |                                                  |
       | RAGAS | DeepEval | LangSmith Evaluations        |
       +--------------------------------------------------+

       +--------------------------------------------------+
       |                     STORAGE                      |
       |                                                  |
       | Qdrant | PostgreSQL | Redis | Neo4j | OpenSearch |
       +--------------------------------------------------+

---

# 89. MOST IMPORTANT DESIGN PRINCIPLE

The final system must not merely "support many RAG types".

It must make them **measurably comparable**.

For every strategy, measure:

Quality
+
Latency
+
Cost
+
Scalability
+
Security
+
Reliability
+
Complexity
+
Observability
+
Maintainability

The UI must allow the user to answer:

"Which RAG architecture should I use for this query/business requirement, and why?"

The system should provide evidence from actual execution and evaluation rather than hardcoded recommendations.

---

# 90. FINAL IMPLEMENTATION INSTRUCTION

Start with Phase 0.

Do NOT generate the entire system at once.

For each phase:

1. Explain what will be implemented.
2. Create/update files.
3. Configure dependencies using uv.
4. Create/update tests.
5. Run validation.
6. Fix errors.
7. Update documentation.
8. Update diagrams.
9. Update version.
10. Commit the phase.
11. Only then proceed to the next phase.

Always prefer:

correctness
security
quality
observability
maintainability
performance

over generating large amounts of code quickly.

The final product must look and behave like a production-oriented enterprise RAG/Agentic AI platform, while remaining runnable on a developer laptop by using local open-source RAG infrastructure and Sarvam AI API for LLM inference.