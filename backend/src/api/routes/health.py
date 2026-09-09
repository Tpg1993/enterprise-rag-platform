"""Health and readiness check endpoints for FastAPI and Docker health checks."""

from fastapi import APIRouter
from src.api.schemas import HealthResponse
from src.config.loader import load_settings

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """System health check endpoint."""
    settings = load_settings()
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        environment=settings.app.environment
        if hasattr(settings.app, "environment")
        else "development",
        services={
            "qdrant": "ready",
            "redis": "ready",
            "postgres": "ready",
            "sarvam_api": "ready" if not settings.app.mock_llm else "mock_mode",
        },
    )


@router.get("/readiness", response_model=HealthResponse)
async def readiness_check() -> HealthResponse:
    """System readiness probe for container orchestration."""
    return await health_check()
