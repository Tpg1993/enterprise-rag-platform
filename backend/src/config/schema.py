"""Pydantic v2 configuration schemas for application runtime parameters."""

from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True
    mock_llm: bool = True


class DatabaseConfig(BaseModel):
    postgres_url: str = (
        "postgresql+asyncpg://postgres:postgres_password_placeholder@localhost:5432/rag_platform"
    )
    pool_size: int = 10
    max_overflow: int = 20


class VectorStoreConfig(BaseModel):
    qdrant_url: str = "http://localhost:6333"
    collection_prefix: str = "enterprise_rag"
    distance_metric: str = "Cosine"


class CacheConfig(BaseModel):
    redis_url: str = "redis://localhost:6379/0"
    ttl_seconds: int = 3600


class GraphStoreConfig(BaseModel):
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"


class LLMSarvamConfig(BaseModel):
    default_model: str = "sarvam-105b"
    api_endpoint: str = "https://api.sarvam.ai/v1/chat/completions"
    timeout_seconds: int = 30
    max_retries: int = 3
    temperature: float = 0.1
    max_tokens: int = 2048


class EmbeddingConfig(BaseModel):
    model_name: str = "BAAI/bge-m3"
    dimension: int = 1024
    max_length: int = 8192
    batch_size: int = 32
    normalize: bool = True


class RerankerConfig(BaseModel):
    model_name: str = "BAAI/bge-reranker-large"
    max_length: int = 512
    top_n_default: int = 5


class HNSWConfig(BaseModel):
    m: int = 16
    ef_construction: int = 128
    ef_search: int = 64


class BM25Config(BaseModel):
    k1: float = 1.5
    b: float = 0.75


class HybridFusionConfig(BaseModel):
    algorithm: str = "rrf"
    rrf_k: int = 60
    dense_weight: float = 0.7
    lexical_weight: float = 0.3


class MMRConfig(BaseModel):
    default_lambda: float = 0.7
    candidate_k: int = 50
    final_k: int = 20


class SecurityConfig(BaseModel):
    pii_enabled: bool = True
    max_agent_iterations: int = 10
    max_execution_time_seconds: int = 45


class PlatformSettings(BaseModel):
    app: AppConfig = Field(default_factory=AppConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    vector_store: VectorStoreConfig = Field(default_factory=VectorStoreConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    graph_store: GraphStoreConfig = Field(default_factory=GraphStoreConfig)
    llm: LLMSarvamConfig = Field(default_factory=LLMSarvamConfig)
    embeddings: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    reranker: RerankerConfig = Field(default_factory=RerankerConfig)
    hnsw: HNSWConfig = Field(default_factory=HNSWConfig)
    bm25: BM25Config = Field(default_factory=BM25Config)
    hybrid_fusion: HybridFusionConfig = Field(default_factory=HybridFusionConfig)
    mmr: MMRConfig = Field(default_factory=MMRConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
