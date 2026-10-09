"""Structured Error Handling Middleware and Exception Handlers."""

import logging
from typing import Any, Dict
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from agent_security.core.decision_engine import TenantMismatchError
from agent_security.core.state_machine import InvalidStateTransitionError, PolicyViolationTransitionError
from agent_security.logging import request_id_ctx, trace_id_ctx

logger = logging.getLogger(__name__)


def build_error_envelope(
    code: str,
    message: str,
    details: Any = None,
    request_id: str = "",
    trace_id: str = "",
) -> Dict[str, Any]:
    """Construct a consistent, structured error envelope."""
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "request_id": request_id or request_id_ctx.get() or "unknown",
            "trace_id": trace_id or trace_id_ctx.get() or "unknown",
        }
    }


def register_error_handlers(app: FastAPI) -> None:
    """Attach structured error handlers to the FastAPI application."""

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        req_id = getattr(request.state, "request_id", request_id_ctx.get())
        trc_id = getattr(request.state, "trace_id", trace_id_ctx.get())
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT if hasattr(status, "HTTP_422_UNPROCESSABLE_CONTENT") else 422,
            content=build_error_envelope(
                code="VALIDATION_ERROR",
                message="Request payload failed schema validation.",
                details=exc.errors(),
                request_id=req_id,
                trace_id=trc_id,
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        req_id = getattr(request.state, "request_id", request_id_ctx.get())
        trc_id = getattr(request.state, "trace_id", trace_id_ctx.get())
        return JSONResponse(
            status_code=exc.status_code,
            content=build_error_envelope(
                code=f"HTTP_{exc.status_code}",
                message=str(exc.detail),
                request_id=req_id,
                trace_id=trc_id,
            ),
        )

    @app.exception_handler(TenantMismatchError)
    async def tenant_mismatch_handler(request: Request, exc: TenantMismatchError):
        req_id = getattr(request.state, "request_id", request_id_ctx.get())
        trc_id = getattr(request.state, "trace_id", trace_id_ctx.get())
        logger.warning(f"Tenant mismatch security event: {exc}", extra={"request_id": req_id})
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=build_error_envelope(
                code="CROSS_TENANT_ACCESS_DENIED",
                message=str(exc),
                request_id=req_id,
                trace_id=trc_id,
            ),
        )

    @app.exception_handler(PolicyViolationTransitionError)
    async def policy_violation_handler(request: Request, exc: PolicyViolationTransitionError):
        req_id = getattr(request.state, "request_id", request_id_ctx.get())
        trc_id = getattr(request.state, "trace_id", trace_id_ctx.get())
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=build_error_envelope(
                code="POLICY_VIOLATION",
                message=str(exc),
                request_id=req_id,
                trace_id=trc_id,
            ),
        )

    @app.exception_handler(InvalidStateTransitionError)
    async def invalid_state_handler(request: Request, exc: InvalidStateTransitionError):
        req_id = getattr(request.state, "request_id", request_id_ctx.get())
        trc_id = getattr(request.state, "trace_id", trace_id_ctx.get())
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=build_error_envelope(
                code="INVALID_STATE_TRANSITION",
                message=str(exc),
                request_id=req_id,
                trace_id=trc_id,
            ),
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        req_id = getattr(request.state, "request_id", request_id_ctx.get())
        trc_id = getattr(request.state, "trace_id", trace_id_ctx.get())
        logger.error(f"Unhandled server error: {exc}", exc_info=True, extra={"request_id": req_id})
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=build_error_envelope(
                code="INTERNAL_SERVER_ERROR",
                message="An unexpected server error occurred.",
                request_id=req_id,
                trace_id=trc_id,
            ),
        )
