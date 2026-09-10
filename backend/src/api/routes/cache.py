"""FastAPI routes for inspecting cache telemetry and managing cache invalidation."""

from fastapi import APIRouter
from src.cache.service import get_cache_manager

router = APIRouter(prefix="/cache", tags=["Cache"])


@router.get("/stats")
async def get_cache_stats():
    """Returns real-time multi-tier cache telemetry, hit rates, and items."""
    cache = get_cache_manager()
    return cache.stats()


@router.post("/clear")
async def clear_cache():
    """Flushes all cached items across memory and Redis."""
    cache = get_cache_manager()
    cache.clear()
    return {"status": "SUCCESS", "message": "Multi-tier cache flushed successfully"}
