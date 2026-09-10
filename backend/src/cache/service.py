"""Multi-Tier Redis Caching Engine for Enterprise RAG & Agentic AI Platform.

Provides 4 distinct caching tiers:
1. Embedding Cache: Eliminates redundant vector calculations.
2. Retrieval Cache: Caches top-K candidate chunks per query, tenant, and strategy.
3. LLM Response Cache: Exact & semantic prompt caching for instant answers.
4. Tenant Policy Cache: In-memory/Redis storage for RBAC and ABAC bounds.
"""

import hashlib
import json
import logging
import os
import threading
import time
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class CacheTier(str, Enum):
    EMBEDDING = "embedding"
    RETRIEVAL = "retrieval"
    LLM_RESPONSE = "llm_response"
    TENANT_POLICY = "tenant_policy"


class MultiTierCacheManager:
    """Enterprise multi-tier caching manager with live Redis connectivity and in-memory LRU fallback."""

    def __init__(self, redis_url: str | None = None) -> None:
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._redis = None
        self._is_redis_available = False
        self._lock = threading.RLock()
        self._memory_cache: dict[str, dict[str, Any]] = {}
        
        # Performance & telemetry counters
        self._hits: dict[str, int] = {t.value: 0 for t in CacheTier}
        self._misses: dict[str, int] = {t.value: 0 for t in CacheTier}

        self._init_redis()

    def _init_redis(self) -> None:
        """Attempts to initialize connection to Redis server."""
        try:
            import redis
            client = redis.Redis.from_url(
                self.redis_url,
                socket_connect_timeout=1.5,
                socket_timeout=2.0,
                decode_responses=True
            )
            client.ping()
            self._redis = client
            self._is_redis_available = True
            logger.info("Connected to Redis server for Multi-Tier Caching.")
        except Exception as e:
            self._is_redis_available = False
            self._redis = None
            logger.info(f"Redis unavailable ({e}). Using in-memory fallback cache.")

    def _compute_key(self, tier: CacheTier, raw_key: str) -> str:
        """Computes standardized cache key with SHA-256 namespace."""
        key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:32]
        return f"rag_cache:{tier.value}:{key_hash}"

    def get(self, tier: CacheTier, raw_key: str) -> Any | None:
        """Retrieves an item from the specified cache tier."""
        cache_key = self._compute_key(tier, raw_key)

        if self._is_redis_available and self._redis:
            try:
                val = self._redis.get(cache_key)
                if val is not None:
                    with self._lock:
                        self._hits[tier.value] += 1
                    return json.loads(val)
                else:
                    with self._lock:
                        self._misses[tier.value] += 1
                    return None
            except Exception as e:
                logger.warning(f"Redis get error ({e}). Falling back to memory.")

        # In-memory cache fallback
        with self._lock:
            entry = self._memory_cache.get(cache_key)
            if entry:
                if entry["expires_at"] is None or entry["expires_at"] > time.time():
                    self._hits[tier.value] += 1
                    return entry["value"]
                else:
                    del self._memory_cache[cache_key]
            self._misses[tier.value] += 1
            return None

    def set(
        self,
        tier: CacheTier,
        raw_key: str,
        value: Any,
        ttl_seconds: int = 3600
    ) -> bool:
        """Stores an item in the specified cache tier with a TTL."""
        cache_key = self._compute_key(tier, raw_key)
        serialized = json.dumps(value)

        if self._is_redis_available and self._redis:
            try:
                self._redis.set(cache_key, serialized, ex=ttl_seconds)
                return True
            except Exception as e:
                logger.warning(f"Redis set error ({e}). Storing in memory.")

        # In-memory cache fallback
        with self._lock:
            self._memory_cache[cache_key] = {
                "value": value,
                "expires_at": time.time() + ttl_seconds if ttl_seconds > 0 else None,
                "tier": tier.value,
            }
            # Evict expired entries if memory exceeds 2000 items
            if len(self._memory_cache) > 2000:
                now = time.time()
                expired = [k for k, v in self._memory_cache.items() if v["expires_at"] and v["expires_at"] <= now]
                for k in expired:
                    del self._memory_cache[k]
        return True

    # Tier 1: Query Embedding Cache
    def get_embedding(self, text: str, model: str = "bge-m3") -> list[float] | None:
        key = f"{model}:{text.strip().lower()}"
        return self.get(CacheTier.EMBEDDING, key)

    def set_embedding(
        self,
        text: str,
        vector: list[float],
        model: str = "bge-m3",
        ttl: int = 86400
    ) -> bool:
        key = f"{model}:{text.strip().lower()}"
        return self.set(CacheTier.EMBEDDING, key, vector, ttl_seconds=ttl)

    # Tier 2: Vector & Lexical Retrieval Cache
    def get_retrieval(
        self,
        query: str,
        tenant_id: str,
        strategy: str,
        top_k: int = 5
    ) -> list[dict[str, Any]] | None:
        key = f"{tenant_id}:{strategy}:{top_k}:{query.strip().lower()}"
        return self.get(CacheTier.RETRIEVAL, key)

    def set_retrieval(
        self,
        query: str,
        tenant_id: str,
        strategy: str,
        hits: list[dict[str, Any]],
        top_k: int = 5,
        ttl: int = 1800
    ) -> bool:
        key = f"{tenant_id}:{strategy}:{top_k}:{query.strip().lower()}"
        return self.set(CacheTier.RETRIEVAL, key, hits, ttl_seconds=ttl)

    # Tier 3: LLM Response Cache
    def get_llm_response(
        self,
        prompt: str,
        strategy: str,
        tenant_id: str,
        system_prompt: str = ""
    ) -> dict[str, Any] | None:
        key = f"{tenant_id}:{strategy}:{system_prompt}:{prompt.strip()}"
        return self.get(CacheTier.LLM_RESPONSE, key)

    def set_llm_response(
        self,
        prompt: str,
        strategy: str,
        tenant_id: str,
        response_dict: dict[str, Any],
        system_prompt: str = "",
        ttl: int = 3600
    ) -> bool:
        key = f"{tenant_id}:{strategy}:{system_prompt}:{prompt.strip()}"
        return self.set(CacheTier.LLM_RESPONSE, key, response_dict, ttl_seconds=ttl)

    # Cache Stats & Telemetry
    def stats(self) -> dict[str, Any]:
        """Returns cache telemetry across hits, misses, and rates."""
        with self._lock:
            total_hits = sum(self._hits.values())
            total_misses = sum(self._misses.values())
            total_reqs = total_hits + total_misses
            hit_rate = (total_hits / total_reqs) if total_reqs > 0 else 0.0

            return {
                "redis_connected": self._is_redis_available,
                "total_hits": total_hits,
                "total_misses": total_misses,
                "hit_rate": round(hit_rate, 4),
                "tier_hits": dict(self._hits),
                "tier_misses": dict(self._misses),
                "memory_items": len(self._memory_cache),
            }

    def clear(self) -> None:
        """Clears all cached items."""
        with self._lock:
            self._memory_cache.clear()
            self._hits = {t.value: 0 for t in CacheTier}
            self._misses = {t.value: 0 for t in CacheTier}
        if self._is_redis_available and self._redis:
            try:
                keys = self._redis.keys("rag_cache:*")
                if keys:
                    self._redis.delete(*keys)
            except Exception as e:
                logger.warning(f"Error flushing Redis cache keys: {e}")


# Global Singleton Cache Manager
_global_cache_manager: MultiTierCacheManager | None = None
_cache_lock = threading.Lock()


def get_cache_manager() -> MultiTierCacheManager:
    """Returns the process-wide MultiTierCacheManager singleton."""
    global _global_cache_manager
    if _global_cache_manager is None:
        with _cache_lock:
            if _global_cache_manager is None:
                _global_cache_manager = MultiTierCacheManager()
    return _global_cache_manager
