"""Authentication endpoints (Phase 11): register, log in, who am I.

Swagger: log in with POST /api/auth/login, copy `access_token`, click "Authorize" and paste it.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.api.deps import CurrentUser, get_app_settings, get_db
from app.api.errors import AppError
from app.api.rate_limit import rate_limit
from app.config import Settings
from app.data.errors import InvalidSymbolError
from app.data.symbols import normalize_symbol
from app.services import auth_service

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
