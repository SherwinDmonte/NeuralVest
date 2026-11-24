"""Shared route dependencies (Phase 11): settings, database, the current user, access rules.

Access rule for stored analyses, reports and portfolios (task 11.1.4):
  * a document with a `user_id` belongs to that user only. Anyone else gets 404, the same
    answer as for an id that does not exist, so ids of other users' reports are not confirmed;
  * a document without a `user_id` (started without logging in, or before Phase 11) is
    readable by whoever has its unguessable id, but only while AUTH_REQUIRED=false.
"""

from typing import Annotated, Any

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pymongo.database import Database

from app.api.errors import AppError
from app.config import Settings, get_settings
from app.database.database import get_database
from app.services import auth_service

# auto_error=False: the dependencies below decide whether a missing token is an error.
bearer = HTTPBearer(auto_error=False, description="Access token from POST /api/auth/login")
_CHALLENGE = {"WWW-Authenticate": "Bearer"}


def get_app_settings(request: Request) -> Settings:
    return getattr(request.app.state, "settings", None) or get_settings()


def get_db(request: Request) -> Database:
    """The runner's database (the test database in tests), else the configured one (503 if none)."""
    runner = getattr(request.app.state, "runner", None)
    if runner is not None:
        return runner.db
    return get_database(get_app_settings(request))


def _user_from_token(request: Request, credentials: HTTPAuthorizationCredentials | None) -> dict | None:
    if credentials is None:
        return None
    settings = get_app_settings(request)
    if not settings.auth_configured:
        raise AppError(503, "auth_not_configured",
                       "Authentication is not configured. Set JWT_SECRET in backend/.env and restart the API.")
    try:
        user_id = auth_service.decode_access_token(credentials.credentials, settings)
    except auth_service.AuthError as exc:
        raise AppError(401, exc.code, exc.message, headers=_CHALLENGE) from exc
    user = auth_service.get_user(get_db(request), user_id)
    if user is None:  # account deleted after the token was issued
        raise AppError(401, "invalid_token", "The access token is invalid.", headers=_CHALLENGE)
    request.state.user_id = user["user_id"]  # used by the rate limiter
    return user


def optional_user(request: Request,
                  credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> dict | None:
    """The logged-in user, or None without a token. A token that IS sent must be valid."""
    return _user_from_token(request, credentials)


def current_user(request: Request,
                 credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> dict:
    user = _user_from_token(request, credentials)
    if user is None:
        raise AppError(401, "not_authenticated", "Log in first: send 'Authorization: Bearer <token>'.",
                       headers=_CHALLENGE)
    return user


def analysis_user(request: Request, user: Annotated[dict | None, Depends(optional_user)]) -> dict | None:
    """For analysis/portfolio endpoints: required when AUTH_REQUIRED=true, optional otherwise."""
    if user is None and get_app_settings(request).auth_required:
        raise AppError(401, "not_authenticated", "Log in first: send 'Authorization: Bearer <token>'.",
                       headers=_CHALLENGE)
    return user


OptionalUser = Annotated[dict | None, Depends(optional_user)]
CurrentUser = Annotated[dict, Depends(current_user)]
AnalysisUser = Annotated[dict | None, Depends(analysis_user)]


def user_id_of(user: dict | None) -> str | None:
    return user["user_id"] if user else None


def can_access(doc: dict[str, Any] | None, user: dict | None, settings: Settings) -> bool:
    if doc is None:
        return False
    owner = doc.get("user_id")
    if owner:
        return user is not None and user["user_id"] == owner
    return not settings.auth_required


def require_access(doc: dict[str, Any] | None, user: dict | None, settings: Settings, code: str,
                   message: str) -> dict[str, Any]:
    """The document, or 404 when it does not exist OR belongs to someone else."""
    if not can_access(doc, user, settings):
        raise AppError(404, code, message)
    return doc
