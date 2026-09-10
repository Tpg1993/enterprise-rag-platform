"""Prometheus metrics endpoint for platform-wide telemetry and monitoring."""

from fastapi import APIRouter, Response
from src.observability.prometheus_service import get_prometheus_manager

router = APIRouter(tags=["Metrics"])


@router.get("/metrics")
async def get_prometheus_metrics():
    """Returns standard Prometheus exposition format telemetry for scraping."""
    prom_mgr = get_prometheus_manager()
    data, content_type = prom_mgr.export_metrics()
    return Response(content=data, media_type=content_type)
