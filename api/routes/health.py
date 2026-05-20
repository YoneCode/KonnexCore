"""Health-check route."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from core.config import get_settings

router = APIRouter(prefix="/api", tags=["health"])


class HealthResponse(BaseModel):
    """Response schema for ``GET /api/health``."""

    model_config = ConfigDict(extra="forbid")

    status: str
    version: str


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
def health() -> HealthResponse:
    """Return ``{status, version}``. No state access — safe for load balancer probes."""
    settings = get_settings()
    return HealthResponse(status="ok", version=settings.app_version)
