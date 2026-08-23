"""Request-id + access-log middleware. The request id is echoed in error
envelopes and bound to every log line via structlog contextvars, so one id
correlates client report ↔ access log ↔ engine/retrieval events."""

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.logging import EVT_REQUEST, get_logger

log = get_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        request.state.request_id = request_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        start = time.perf_counter()
        response = await call_next(request)
        if request.url.path != "/api/v1/health":  # don't spam liveness probes
            log.info(
                EVT_REQUEST,
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                latency_ms=int((time.perf_counter() - start) * 1000),
            )
        response.headers["x-request-id"] = request_id
        return response
