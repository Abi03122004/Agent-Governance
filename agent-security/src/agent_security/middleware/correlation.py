"""Request and Trace Correlation Middleware."""

import uuid
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from agent_security.logging import request_id_ctx, trace_id_ctx

HEADER_REQUEST_ID = "X-Request-ID"
HEADER_TRACE_ID = "X-Trace-ID"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Ensures every incoming request has a unique Request ID and Trace ID.
    
    Extracts headers if provided by upstream proxies/clients or generates UUIDs.
    Propagates them into contextvars and response headers.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Extract or generate request and trace IDs
        request_id = request.headers.get(HEADER_REQUEST_ID) or f"req_{uuid.uuid4().hex[:16]}"
        trace_id = request.headers.get(HEADER_TRACE_ID) or f"trc_{uuid.uuid4().hex[:16]}"

        # Bind to contextvars for current async task
        token_req = request_id_ctx.set(request_id)
        token_trc = trace_id_ctx.set(trace_id)

        try:
            # Store in request state for downstream handlers
            request.state.request_id = request_id
            request.state.trace_id = trace_id

            response = await call_next(request)

            # Inject into response headers
            response.headers[HEADER_REQUEST_ID] = request_id
            response.headers[HEADER_TRACE_ID] = trace_id
            return response
        finally:
            request_id_ctx.reset(token_req)
            trace_id_ctx.reset(token_trc)
