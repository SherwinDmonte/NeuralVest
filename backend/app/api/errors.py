"""Centralized exception handling.

Every error leaves the API as the same JSON envelope (`schemas/common.ErrorResponse`), with
the request ID so a user-visible error can be matched to a log line. Internal details
(stack traces, database messages) are logged, never returned.
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pymongo.errors import ConnectionFailure, PyMongoError, ServerSelectionTimeoutError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("neuralvest.errors")


class AppError(Exception):
    """An expected, user-facing error with a stable machine-readable code."""

    def __init__(self, status_code: int, code: str, message: str, details: Any | None = None,
                 headers: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        self.headers = headers  # e.g. Retry-After (429), WWW-Authenticate (401)


def _error(request: Request, status_code: int, code: str, message: str, details: Any = None,
           headers: dict[str, str] | None = None) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    body = {"error": {"code": code, "message": message, "details": details, "request_id": request_id}}
    return JSONResponse(status_code=status_code, content=jsonable_encoder(body), headers=headers)


INTERNAL_ERROR_MESSAGE = "An unexpected error occurred."


class UnhandledErrorMiddleware:
    """Turns an unexpected exception into the standard 500 envelope INSIDE the request-ID and CORS
    middleware. FastAPI runs an `Exception` handler outside every middleware, so before Phase 13
    such a response had no X-Request-ID header and no CORS headers (a browser then reported a CORS
    failure instead of the error). The app-level handler below remains as a last resort."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def tracking_send(message: Message) -> None:
            nonlocal started
            started = started or message["type"] == "http.response.start"
            await send(message)

        try:
            await self.app(scope, receive, tracking_send)
        except Exception:
            if started:  # part of the response is already sent: nothing sensible to replace it with
                raise
            logger.exception("Unhandled error")
            request_id = (scope.get("state") or {}).get("request_id")
            body = {"error": {"code": "internal_error", "message": INTERNAL_ERROR_MESSAGE, "details": None,
                              "request_id": request_id}}
            await JSONResponse(status_code=500, content=body)(scope, receive, send)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        return _error(request, exc.status_code, exc.code, exc.message, exc.details, exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Keep only the useful parts of each Pydantic error.
        details = [
            {"location": list(err.get("loc", [])), "message": err.get("msg"), "type": err.get("type")}
            for err in exc.errors()
        ]
        return _error(request, 422, "validation_error", "The request is invalid.", details)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {401: "not_authenticated", 404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        return _error(request, exc.status_code, code, str(exc.detail), headers=getattr(exc, "headers", None))

    @app.exception_handler(PyMongoError)
    async def _database_error(request: Request, exc: PyMongoError) -> JSONResponse:
        if isinstance(exc, (ServerSelectionTimeoutError, ConnectionFailure)):
            logger.warning("Database unavailable: %s", exc.__class__.__name__)
            return _error(request, 503, "database_unavailable", "The database is currently unavailable.")
        logger.exception("Database error")
        return _error(request, 500, "database_error", "A database error occurred.")

    @app.exception_handler(Exception)
    async def _unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error")
        return _error(request, 500, "internal_error", INTERNAL_ERROR_MESSAGE)
