"""Unit tests for Multi-Tier Redis Caching Engine."""

import time
import pytest
from src.cache.service import MultiTierCacheManager, CacheTier, get_cache_manager


@pytest.fixture
def cache_mgr():
    """Creates an isolated cache manager instance for testing."""
    mgr = MultiTierCacheManager(redis_url="redis://non_existent_host:6379/0")
    mgr.clear()
    return mgr


def test_cache_initialization(cache_mgr):
    """Verifies cache manager initializes in fallback memory mode gracefully."""
    stats = cache_mgr.stats()
    assert "total_hits" in stats
    assert "total_misses" in stats
    assert "hit_rate" in stats
    assert stats["total_hits"] == 0
    assert stats["total_misses"] == 0


def test_embedding_tier_cache(cache_mgr):
    """Tests Tier 1 Query Embedding Cache storing and retrieval."""
    text = "What is enterprise retrieval?"
    embedding = [0.12, -0.45, 0.78, 0.99]

    # Initial miss
    miss = cache_mgr.get_embedding(text)
    assert miss is None

    # Set cache
    success = cache_mgr.set_embedding(text, embedding)
    assert success is True

    # Cache hit
    hit = cache_mgr.get_embedding(text)
    assert hit == embedding

    # Case insensitive key check
    hit_upper = cache_mgr.get_embedding("WHAT IS ENTERPRISE RETRIEVAL?")
    assert hit_upper == embedding


def test_retrieval_tier_cache(cache_mgr):
    """Tests Tier 2 Retrieval Cache with tenant isolation."""
    query = "enterprise governance architecture"
    chunks_tenant_a = [{"chunk_id": "c1", "content": "Tenant A governance"}]
    chunks_tenant_b = [{"chunk_id": "c2", "content": "Tenant B governance"}]

    cache_mgr.set_retrieval(query, tenant_id="tenant_a", strategy="Hybrid", hits=chunks_tenant_a)
    cache_mgr.set_retrieval(query, tenant_id="tenant_b", strategy="Hybrid", hits=chunks_tenant_b)

    res_a = cache_mgr.get_retrieval(query, tenant_id="tenant_a", strategy="Hybrid")
    res_b = cache_mgr.get_retrieval(query, tenant_id="tenant_b", strategy="Hybrid")

    assert res_a == chunks_tenant_a
    assert res_b == chunks_tenant_b
    assert res_a != res_b


def test_llm_response_tier_cache(cache_mgr):
    """Tests Tier 3 LLM Response Cache for fast prompt replay."""
    prompt = "Explain RRF fusion ranking"
    response_payload = {
        "answer": "RRF fuses ranks from dense and sparse retrieval.",
        "model": "sarvam-105b",
        "tokens": 42,
    }

    # Initial miss
    assert cache_mgr.get_llm_response(prompt, strategy="Basic", tenant_id="default") is None

    # Store response
    cache_mgr.set_llm_response(
        prompt,
        strategy="Basic",
        tenant_id="default",
        response_dict=response_payload,
        ttl=100,
    )

    # Retrieval hit
    hit = cache_mgr.get_llm_response(prompt, strategy="Basic", tenant_id="default")
    assert hit is not None
    assert hit["answer"] == response_payload["answer"]
    assert hit["model"] == "sarvam-105b"


def test_ttl_expiration(cache_mgr):
    """Tests that items expire after TTL seconds."""
    key = "short_lived_query"
    cache_mgr.set(CacheTier.LLM_RESPONSE, key, {"data": "temp"}, ttl_seconds=1)

    # Immediate hit
    assert cache_mgr.get(CacheTier.LLM_RESPONSE, key) == {"data": "temp"}

    # Sleep past expiration
    time.sleep(1.1)

    # Expired -> None
    assert cache_mgr.get(CacheTier.LLM_RESPONSE, key) is None


def test_telemetry_hit_rate(cache_mgr):
    """Verifies hit rate statistics calculation."""
    # 2 misses, 1 hit
    cache_mgr.get(CacheTier.EMBEDDING, "test1")
    cache_mgr.get(CacheTier.EMBEDDING, "test2")

    cache_mgr.set(CacheTier.EMBEDDING, "test3", [1.0, 2.0])
    cache_mgr.get(CacheTier.EMBEDDING, "test3")

    stats = cache_mgr.stats()
    assert stats["total_misses"] == 2
    assert stats["total_hits"] == 1
    assert stats["hit_rate"] == pytest.approx(0.3333, abs=0.01)


def test_cache_clear(cache_mgr):
    """Tests cache flush across all tiers."""
    cache_mgr.set(CacheTier.EMBEDDING, "k1", [0.1])
    cache_mgr.set(CacheTier.RETRIEVAL, "k2", [{"a": 1}])
    cache_mgr.set(CacheTier.LLM_RESPONSE, "k3", {"ans": "ok"})

    assert cache_mgr.stats()["memory_items"] == 3

    cache_mgr.clear()

    assert cache_mgr.stats()["memory_items"] == 0
    assert cache_mgr.stats()["total_hits"] == 0
    assert cache_mgr.stats()["total_misses"] == 0


def test_singleton_provider():
    """Tests process-wide singleton provider."""
    mgr1 = get_cache_manager()
    mgr2 = get_cache_manager()
    assert mgr1 is mgr2
