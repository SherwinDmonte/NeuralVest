"""Request ID middleware: every request gets an ID that appears in logs and the response."""

import logging
import re
import time
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.utils.logging_config import request_id_var

logger = logging.getLogger("neuralvest.http")

REQUEST_ID_HEADER = "X-Request-ID"
# Accept a client-supplied ID only if it is short and harmless (prevents log injection).
_VALID_ID = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


class RequestIdMiddleware:
    """Pure ASGI middleware (lighter than BaseHTTPMiddleware and safe for streaming)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = dict(scope.get("headers") or []).get(REQUEST_ID_HEADER.lower().encode(), b"").decode(
            "latin-1"
        )
        request_id = incoming if _VALID_ID.match(incoming) else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        scope.setdefault("state", {})["request_id"] = request_id
        started = time.perf_counter()
        status_holder = {"code": 500}

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["code"] = message["status"]
                headers = list(message.get("headers", []))
                headers.append((REQUEST_ID_HEADER.lower().encode(), request_id.encode()))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000
            logger.info(
                "%s %s -> %s (%.1f ms)", scope["method"], scope["path"], status_holder["code"], elapsed_ms
            )
            request_id_var.reset(token)
