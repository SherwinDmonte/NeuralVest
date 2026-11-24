"""Authentication endpoints (Phase 11): register, log in, who am I; watchlist and profile picture (Phase 12B).

Swagger: log in with POST /api/auth/login, copy `access_token`, click "Authorize" and paste it.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.api.deps import CurrentUser, get_app_settings, get_db
from app.api.errors import AppError
from app.api.rate_limit import rate_limit
from app.config import Settings
from app.data.errors import InvalidSymbolError
from app.data.symbols import normalize_symbol
from app.database.database import ensure_storage_available
from app.services import auth_service, avatar_service

router = APIRouter(prefix="/api/auth", tags=["auth"])

MIN_PASSWORD = 8
MAX_PASSWORD = 128  # Argon2 accepts more, but very long inputs only cost CPU
COMMON_PASSWORDS = {"password", "password1", "password123", "12345678", "123456789", "1234567890", "qwerty123",
                    "qwertyuiop", "iloveyou", "11111111", "abcdefgh", "abc12345", "letmein1", "welcome1",
                    "admin123", "neuralvest"}


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80, examples=["Asha"])
    email: EmailStr = Field(examples=["asha@example.com"])
    password: str = Field(min_length=MIN_PASSWORD, max_length=MAX_PASSWORD,
                          description=f"{MIN_PASSWORD}-{MAX_PASSWORD} characters")

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("name must not be blank")
        return v

    @field_validator("password")
    @classmethod
    def _password(cls, v: str) -> str:
        # Length over composition rules (NIST SP 800-63B), plus a block-list of the most
        # common passwords and of single repeated characters.
        if not v.strip() or len(set(v)) == 1:
            raise ValueError("password is too simple")
        if v.lower() in COMMON_PASSWORDS:
            raise ValueError("this password is too common; choose another")
        return v

    @model_validator(mode="after")
    def _not_email(self) -> "RegisterRequest":
        if self.password.lower() in (self.email.lower(), self.email.split("@")[0].lower()):
            raise ValueError("the password must not be your e-mail address")
        return self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=MAX_PASSWORD)


Db = Annotated[object, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_app_settings)]


def _require_auth_configured(settings: Settings) -> None:
    if not settings.auth_configured:
        raise AppError(503, "auth_not_configured",
                       "Authentication is not configured. Set JWT_SECRET (32+ characters) in backend/.env "
                       "and restart the API.")


@router.post("/register", status_code=201, summary="Create an account",
             dependencies=[Depends(rate_limit("auth", per_user=False))])
def register(body: RegisterRequest, db: Db, settings: AppSettings) -> dict:
    _require_auth_configured(settings)
    try:
        user = auth_service.register_user(db, body.name, body.email, body.password)
    except auth_service.EmailTakenError as exc:
        raise AppError(409, "email_already_registered", "An account with this e-mail already exists.") from exc
    return {"user": user}


@router.post("/login", summary="Log in and receive an access token (JWT)",
             dependencies=[Depends(rate_limit("auth", per_user=False))])
def login(body: LoginRequest, db: Db, settings: AppSettings) -> dict:
    _require_auth_configured(settings)
    try:
        user = auth_service.authenticate(db, body.email, body.password)
    except auth_service.AuthError as exc:
        raise AppError(401, exc.code, exc.message, headers={"WWW-Authenticate": "Bearer"}) from exc
    return {**auth_service.create_access_token(user["user_id"], settings), "user": user}


@router.get("/me", summary="The logged-in user")
def me(user: CurrentUser) -> dict:
    return {"user": user}


class WatchlistRequest(BaseModel):
    symbols: list[str] = Field(max_length=auth_service.MAX_WATCHLIST, examples=[["RELIANCE.NS", "TCS.NS"]])

    @field_validator("symbols")
    @classmethod
    def _normalize(cls, values: list[str]) -> list[str]:
        try:
            return list(dict.fromkeys(normalize_symbol(v) for v in values))
        except InvalidSymbolError as exc:
            raise ValueError(str(exc)) from exc


@router.get("/me/watchlist", summary="Your watchlist")
def get_watchlist(user: CurrentUser, db: Db) -> dict:
    return {"symbols": auth_service.get_watchlist(db, user["user_id"]), "max": auth_service.MAX_WATCHLIST}


@router.put("/me/watchlist", summary="Replace your watchlist (up to 20 symbols)")
def put_watchlist(body: WatchlistRequest, user: CurrentUser, db: Db) -> dict:
    return {"symbols": auth_service.set_watchlist(db, user["user_id"], body.symbols),
            "max": auth_service.MAX_WATCHLIST}


# ---------------------------------------------------------------- profile picture (Phase 12B)
AVATAR_BODY = {"requestBody": {"required": True, "description": "The image file itself as the request body (not a form).",
                               "content": {t: {"schema": {"type": "string", "format": "binary"}}
                                           for t in avatar_service.ACCEPTED_TYPES}}}


async def _read_upload(request: Request) -> bytes:
    """The raw body, refused early when it is over the size limit."""
    limit = avatar_service.MAX_UPLOAD_BYTES
    too_large = AppError(413, "file_too_large", f"The image is over {limit // (1024 * 1024)} MB.")
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit:
        raise too_large
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > limit:
            raise too_large
    return bytes(body)


@router.put("/me/avatar", summary="Set your profile picture (JPEG, PNG or WebP, up to 5 MB)",
            openapi_extra=AVATAR_BODY, dependencies=[Depends(rate_limit("avatar"))])
async def put_avatar(request: Request, user: CurrentUser, db: Db, settings: AppSettings) -> dict:
    content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if content_type not in avatar_service.ACCEPTED_TYPES:
        raise AppError(415, "unsupported_media_type", "Send a JPEG, PNG or WebP image with its Content-Type.")
    raw = await _read_upload(request)
    await run_in_threadpool(ensure_storage_available, settings)
    try:
        data = await run_in_threadpool(avatar_service.process_image, raw)
    except avatar_service.AvatarError as exc:
        status = {"file_too_large": 413, "unsupported_media_type": 415}.get(exc.code, 422)
        raise AppError(status, exc.code, exc.message) from exc
    await run_in_threadpool(avatar_service.save_avatar, db, user["user_id"], data)
    return {"user": await run_in_threadpool(auth_service.get_user, db, user["user_id"])}


@router.get("/me/avatar", summary="Your profile picture (256 x 256 WebP)",
            responses={200: {"content": {avatar_service.CONTENT_TYPE: {}}}, 404: {"description": "No picture set"}})
def get_avatar(user: CurrentUser, db: Db) -> Response:
    doc = avatar_service.get_avatar(db, user["user_id"])
    if not doc:
        raise AppError(404, "avatar_not_found", "No profile picture is set.")
    return Response(content=bytes(doc["data"]), media_type=doc["content_type"],
                    headers={"Cache-Control": "private, max-age=86400", "X-Content-Type-Options": "nosniff"})


@router.delete("/me/avatar", summary="Remove your profile picture")
def delete_avatar(user: CurrentUser, db: Db) -> dict:
    avatar_service.delete_avatar(db, user["user_id"])
    return {"user": auth_service.get_user(db, user["user_id"])}
