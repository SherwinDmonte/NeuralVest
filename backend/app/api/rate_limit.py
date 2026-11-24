"""Rate limiting for expensive endpoints (task 11.3.1).

Uses the `limits` library (the engine inside slowapi) directly as a FastAPI dependency: the
counters live in memory on `app.state`, so every app instance (and every test) starts fresh,
and no Redis is needed. Limits are per logged-in user, otherwise per client IP, and per
endpoint group ("auth", "analysis", "portfolio", "pdf"; values in Settings / .env).

The counters reset when the API restarts. That is acceptable for a single-user local app;
a shared deployment would use a shared store (limits supports Redis).
"""

import math
import time

from fastapi import Depends, Request
from limits import parse
from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter

from app.api.deps import get_app_settings, optional_user
from app.api.errors import AppError

GROUPS = ("auth", "analysis", "portfolio", "pdf")


class RateLimiter:
    def __init__(self) -> None:
        self.storage = MemoryStorage()
        self.strategy = MovingWindowRateLimiter(self.storage)

    def hit(self, limit_text: str, group: str, key: str) -> int | None:
        """None when allowed, else the seconds until the next request is allowed."""
        item = parse(limit_text)
        if self.strategy.hit(item, group, key):
            return None
        reset_at, _remaining = self.strategy.get_window_stats(item, group, key)
        return max(1, math.ceil(reset_at - time.time()))

    def reset(self) -> None:
        self.storage.reset()


def _client_key(request: Request) -> str:
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"user:{user_id}"
    return f"ip:{request.client.host if request.client else 'unknown'}"


def rate_limit(group: str, per_user: bool = True):
    """Dependency enforcing the limit of `group`. per_user=False always keys by IP (login)."""
    if group not in GROUPS:
        raise ValueError(f"unknown rate-limit group {group}")

    def check(request: Request) -> None:
        settings = get_app_settings(request)
        limiter: RateLimiter | None = getattr(request.app.state, "rate_limiter", None)
        if not settings.rate_limit_enabled or limiter is None:
            return
        key = _client_key(request) if per_user else f"ip:{request.client.host if request.client else 'unknown'}"
        limit_text = getattr(settings, f"rate_limit_{group}")
        retry_after = limiter.hit(limit_text, group, key)
        if retry_after is not None:
            raise AppError(429, "rate_limited",
                           f"Too many requests ({limit_text}). Try again in {retry_after} s.",
                           {"limit": limit_text, "retry_after_seconds": retry_after},
                           headers={"Retry-After": str(retry_after)})

    if per_user:
        # Resolve the (optional) user first so a logged-in user gets their own counter.
        def check_with_user(request: Request, _user=Depends(optional_user)) -> None:
            check(request)
        return check_with_user
    return check
