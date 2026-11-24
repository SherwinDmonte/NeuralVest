"""Phase 11 unit tests (no database): password hashing, tokens, settings, URL safety, rate limits."""

from datetime import timedelta

import jwt
import pytest
from pydantic import SecretStr, ValidationError

from app.api.rate_limit import RateLimiter
from app.config import Settings
from app.services import auth_service as auth
from app.utils.timing import utc_now
from app.utils.urls import safe_http_url

SECRET = "s" * 48


def settings(**kw) -> Settings:
    return Settings(_env_file=None, jwt_secret=SecretStr(SECRET), **kw)


# ---------------------------------------------------------------- passwords
def test_password_hash_is_argon2_and_verifies():
    h = auth.hash_password("correct horse battery")
    assert h.startswith("$argon2id$") and "correct horse" not in h
    assert auth.verify_password("correct horse battery", h)
    assert not auth.verify_password("wrong", h)
    assert auth.hash_password("correct horse battery") != h  # random salt


def test_verify_handles_missing_and_malformed_hash():
    assert not auth.verify_password("anything", None)  # unknown e-mail: still does the work, returns False
    assert not auth.verify_password("anything", "$argon2id$garbage")


def test_public_user_never_contains_the_hash():
    doc = {"user_id": "a" * 32, "name": "A", "email": "a@example.com", "password_hash": "$argon2id$x"}
    assert "password_hash" not in auth.public_user(doc)


# ---------------------------------------------------------------- tokens
def test_token_round_trip():
    token = auth.create_access_token("b" * 32, settings(jwt_expire_minutes=30))
    assert token["token_type"] == "bearer" and token["expires_in"] == 1800
    assert auth.decode_access_token(token["access_token"], settings()) == "b" * 32


def test_expired_token():
    now = utc_now()
    token = jwt.encode({"sub": "u", "iat": now - timedelta(hours=2), "exp": now - timedelta(hours=1),
                        "iss": auth.ISSUER, "typ": "access"}, SECRET, algorithm="HS256")
    with pytest.raises(auth.AuthError) as exc:
        auth.decode_access_token(token, settings())
    assert exc.value.code == "token_expired"


@pytest.mark.parametrize("make", [
    lambda: jwt.encode({"sub": "u", "iat": utc_now(), "exp": utc_now() + timedelta(hours=1), "iss": auth.ISSUER,
                        "typ": "access"}, "x" * 48, algorithm="HS256"),          # another secret
    lambda: jwt.encode({"sub": "u", "iat": utc_now(), "exp": utc_now() + timedelta(hours=1), "iss": auth.ISSUER,
                        "typ": "access"}, None, algorithm="none"),              # unsigned ("alg": "none")
    lambda: jwt.encode({"sub": "u", "iat": utc_now(), "exp": utc_now() + timedelta(hours=1), "iss": "other",
                        "typ": "access"}, SECRET, algorithm="HS256"),            # wrong issuer
    lambda: jwt.encode({"sub": "u", "iat": utc_now(), "exp": utc_now() + timedelta(hours=1), "iss": auth.ISSUER,
                        "typ": "refresh"}, SECRET, algorithm="HS256"),           # not an access token
    lambda: jwt.encode({"iat": utc_now(), "exp": utc_now() + timedelta(hours=1), "iss": auth.ISSUER,
                        "typ": "access"}, SECRET, algorithm="HS256"),            # no subject
    lambda: "not.a.token",
])
def test_invalid_tokens_rejected(make):
    with pytest.raises(auth.AuthError) as exc:
        auth.decode_access_token(make(), settings())
    assert exc.value.code == "invalid_token"


def test_tokens_need_a_configured_secret():
    with pytest.raises(auth.AuthError) as exc:
        auth.create_access_token("u", Settings(_env_file=None))
    assert exc.value.code == "auth_not_configured"


# ---------------------------------------------------------------- settings
def test_jwt_secret_settings():
    assert Settings(_env_file=None, jwt_secret="<generate-locally>").jwt_secret is None  # .env.example placeholder
    assert not Settings(_env_file=None, jwt_secret="short").auth_configured  # under 32 characters
    assert settings().auth_configured
    assert SECRET not in repr(settings())  # SecretStr: never printed
    assert Settings(_env_file=None).auth_required is False


def test_invalid_rate_limit_fails_at_startup():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, rate_limit_auth="lots")


# ---------------------------------------------------------------- URLs (11.3.3)
@pytest.mark.parametrize("url", ["https://www.livemint.com/market/a.html", "http://example.com/x?a=1",
                                 "https://news.example.co.in:8443/p"])
def test_safe_urls_pass(url):
    assert safe_http_url(url) == url


@pytest.mark.parametrize("url", [None, "", "javascript:alert(1)", "data:text/html,<b>x</b>", "ftp://example.com/f",
                                 "https://user:pw@example.com/", "http://localhost:8000/api", "http://127.0.0.1/",
                                 "http://192.168.1.10/admin", "http://intranet/", "https://exa mple.com/",
                                 "https://example.com/\x00", "//example.com/x", "https://example.com:99999/",
                                 "https://" + "a" * 2100 + ".com/"])
def test_unsafe_urls_rejected(url):
    assert safe_http_url(url) is None


# ---------------------------------------------------------------- rate limiter (11.3.1)
def test_rate_limiter_allows_then_blocks():
    limiter = RateLimiter()
    assert [limiter.hit("3/minute", "auth", "ip:1") for _ in range(3)] == [None, None, None]
    retry_after = limiter.hit("3/minute", "auth", "ip:1")
    assert retry_after is not None and 1 <= retry_after <= 60
    assert limiter.hit("3/minute", "auth", "ip:2") is None  # separate counter per client
    assert limiter.hit("3/minute", "analysis", "ip:1") is None  # and per endpoint group
    limiter.reset()
    assert limiter.hit("3/minute", "auth", "ip:1") is None
