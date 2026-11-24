"""Accounts and access tokens (Phase 11).

* Passwords are hashed with Argon2id (pwdlib, OWASP-recommended parameters). The plain
  password is never stored or logged; the `users` validator rejects anything that is not an
  Argon2 hash.
* Access tokens are JWTs signed with HS256 and the local JWT_SECRET. They carry only the
  user_id (`sub`), issue and expiry times. Every request re-checks that the user still exists.
* Login failures give one generic message, and an unknown e-mail still runs a hash
  verification, so the response does not reveal which e-mail addresses are registered.
"""

import uuid
from datetime import timedelta
from typing import Any

import jwt
from pwdlib import PasswordHash
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from app.config import Settings
from app.database.models import USERS, UserDocument
from app.database.repository import insert_document
from app.utils.timing import utc_now

ALGORITHM = "HS256"
ISSUER = "neuralvest"
_hasher = PasswordHash.recommended()  # Argon2id
# Verified against when the e-mail is unknown (equal work for unknown and known e-mails).
_DUMMY_HASH = _hasher.hash("neuralvest-timing-equaliser")


class AuthError(Exception):
    """Invalid credentials or token. `code` is the stable API error code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class EmailTakenError(Exception):
    pass


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        _hasher.verify(password, _DUMMY_HASH)
        return False
    try:
        return _hasher.verify(password, password_hash)
    except Exception:  # malformed hash: treat as a failed login, never as a crash
        return False


def public_user(doc: dict[str, Any]) -> dict[str, Any]:
    """The only user fields that ever leave the API (never the password hash)."""
    return {"user_id": doc["user_id"], "name": doc["name"], "email": doc["email"],
            "created_at": doc.get("created_at")}


def register_user(db: Database, name: str, email: str, password: str) -> dict[str, Any]:
    doc = UserDocument(user_id=uuid.uuid4().hex, name=name.strip(), email=email,
                       password_hash=hash_password(password))
    try:
        insert_document(db, doc)
    except DuplicateKeyError as exc:  # unique index on email
        raise EmailTakenError(doc.email) from exc
    return public_user(doc.to_document())


def authenticate(db: Database, email: str, password: str) -> dict[str, Any]:
    user = db[USERS].find_one({"email": email.strip().lower()})
    if user is None:
        verify_password(password, None)  # same work as for a known e-mail
        raise AuthError("invalid_credentials", "Invalid e-mail or password.")
    try:
        valid, new_hash = _hasher.verify_and_update(password, user["password_hash"])
    except Exception:  # malformed stored hash
        valid, new_hash = False, None
    if not valid:
        raise AuthError("invalid_credentials", "Invalid e-mail or password.")
    if new_hash:  # the hashing parameters were strengthened since this password was set
        db[USERS].update_one({"user_id": user["user_id"]}, {"$set": {"password_hash": new_hash, "updated_at": utc_now()}})
    return public_user(user)


def _secret(settings: Settings) -> str:
    if not settings.auth_configured:
        raise AuthError("auth_not_configured", "Authentication is not configured (JWT_SECRET missing).")
    return settings.jwt_secret.get_secret_value().strip()


def create_access_token(user_id: str, settings: Settings) -> dict[str, Any]:
    now = utc_now()
    expires = now + timedelta(minutes=settings.jwt_expire_minutes)
    claims = {"sub": user_id, "iat": now, "exp": expires, "iss": ISSUER, "typ": "access"}
    return {"access_token": jwt.encode(claims, _secret(settings), algorithm=ALGORITHM), "token_type": "bearer",
            "expires_in": settings.jwt_expire_minutes * 60, "expires_at": expires.isoformat()}


def decode_access_token(token: str, settings: Settings) -> str:
    """The user_id in a valid, unexpired token; AuthError otherwise."""
    try:
        claims = jwt.decode(token, _secret(settings), algorithms=[ALGORITHM], issuer=ISSUER,
                            options={"require": ["sub", "exp", "iat", "iss"]})
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("token_expired", "The access token has expired. Log in again.") from exc
    except jwt.PyJWTError as exc:
        raise AuthError("invalid_token", "The access token is invalid.") from exc
    if claims.get("typ") != "access" or not isinstance(claims.get("sub"), str):
        raise AuthError("invalid_token", "The access token is invalid.")
    return claims["sub"]


def get_user(db: Database, user_id: str) -> dict[str, Any] | None:
    doc = db[USERS].find_one({"user_id": user_id}, {"password_hash": 0})
    return public_user(doc) if doc else None
