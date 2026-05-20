"""FastAPI application entry point.

Constructed via ``create_app`` so tests can spin up a fresh instance
without sharing state across runs. The module-level ``app`` exposes
the same instance for ``uvicorn api.main:app``.

Run locally::

    uvicorn api.main:app --host 0.0.0.0 --port 8000

OpenAPI schema is exposed at ``/docs`` (Swagger UI) and ``/redoc``.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from api.deps import AppState
from api.middleware import install_exception_handlers, log_requests
from api.routes import attack, demo, health, honeypot, identity, verify
from core.config import get_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

log = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Allocate the shared ``AppState`` once per process."""
    state = AppState()
    app.state.konnexcore_state = state
    log.info("KonnexCore lifespan: state initialised")
    try:
        yield
    finally:
        log.info("KonnexCore lifespan: shutdown")


def _cors_origins() -> list[str]:
    """Read the comma-separated CORS origin list from the environment.

    Default is the local Vite dev server. Production deployments
    point this at the dashboard's public origin.
    """
    raw = os.environ.get("KONNEXCORE_CORS_ORIGINS", "http://localhost:5173")
    return [o.strip() for o in raw.split(",") if o.strip()]


def create_app() -> FastAPI:
    """Build and return a fully wired FastAPI application."""
    settings = get_settings()
    app = FastAPI(
        title="KonnexCore API",
        version=settings.app_version,
        description=(
            "TEE-attested sensor capture (RootID) + deterministic Layer-3 verifier "
            "(DetVerify) + honeypot oracle (Honeynet) for the Konnex builder grant."
        ),
        lifespan=_lifespan,
        openapi_tags=[
            {"name": "health", "description": "Liveness / readiness probes."},
            {"name": "identity", "description": "Layer A — RootID identities and signing."},
            {"name": "verify", "description": "Layer B — six-stage DetVerify pipeline."},
            {"name": "honeypot", "description": "Layer C — Honeynet oracle."},
            {"name": "attack", "description": "Phase 4 attack-lab generators."},
            {"name": "demo", "description": "Composite end-to-end demo flows."},
        ],
    )

    app.add_middleware(BaseHTTPMiddleware, dispatch=log_requests)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    install_exception_handlers(app)

    for route_module in (health, identity, verify, honeypot, attack, demo):
        app.include_router(route_module.router)

    return app


#: Module-level app instance for ``uvicorn api.main:app``.
app = create_app()
