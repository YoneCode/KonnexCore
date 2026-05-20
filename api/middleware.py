"""Custom middleware + global exception handler for the API."""

from __future__ import annotations

import logging
import time
import uuid
from typing import TYPE_CHECKING

from fastapi import status
from fastapi.responses import JSONResponse

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from fastapi import FastAPI, Request
    from starlette.responses import Response

log = logging.getLogger(__name__)

_X_REQUEST_ID = "X-Request-ID"


async def log_requests(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Attach a request-ID and emit a single structured log line per request."""
    request_id = request.headers.get(_X_REQUEST_ID, uuid.uuid4().hex[:12])
    start_ns = time.perf_counter_ns()
    log.info(
        "request id=%s method=%s path=%s",
        request_id,
        request.method,
        request.url.path,
    )
    try:
        response = await call_next(request)
    except Exception:
        log.exception(
            "request id=%s method=%s path=%s — unhandled exception",
            request_id,
            request.method,
            request.url.path,
        )
        raise
    elapsed_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
    log.info(
        "response id=%s status=%d elapsed_ms=%.2f",
        request_id,
        response.status_code,
        elapsed_ms,
    )
    response.headers[_X_REQUEST_ID] = request_id
    return response


def install_exception_handlers(app: FastAPI) -> None:
    """Register the generic 500 handler that returns a uniform JSON body.

    We never echo Python stack traces to clients — those go to the
    server log. The response shape matches spec §7 ("contract rules"):
    ``{"error": str, "detail": dict, "stage": str}`` with appropriate
    HTTP code.
    """

    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled exception in request handler")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "internal-server-error",
                "detail": {"message": "an unexpected error occurred"},
                "stage": "server",
            },
        )

    app.add_exception_handler(Exception, _unhandled)
