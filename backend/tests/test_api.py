"""API behaviour without a database (MongoDB deliberately unconfigured)."""

import re

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client(no_db_settings):
    with TestClient(create_app(no_db_settings)) as c:
        yield c


def assert_error_envelope(resp, status: int, code: str):
    assert resp.status_code == status
    body = resp.json()
    assert set(body) == {"error"}
    assert body["error"]["code"] == code
    assert body["error"]["request_id"] == resp.headers["X-Request-ID"]


def test_health_ok_with_request_id(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"
    assert re.fullmatch(r"[0-9a-f]{32}", r.headers["X-Request-ID"])


def test_valid_incoming_request_id_is_echoed(client):
    r = client.get("/api/health", headers={"X-Request-ID": "client-trace-12345"})
    assert r.headers["X-Request-ID"] == "client-trace-12345"


def test_unsafe_incoming_request_id_is_replaced(client):
    r = client.get("/api/health", headers={"X-Request-ID": "bad id; drop"})
    assert r.headers["X-Request-ID"] != "bad id; drop"


def test_health_db_reports_not_configured(client):
    r = client.get("/api/health/db")
    assert r.status_code == 503
    assert r.json()["configured"] is False and r.json()["connected"] is False


def test_stock_endpoint_without_db_returns_503(client):
    assert_error_envelope(client.get("/api/stocks/RELIANCE.NS"), 503, "database_not_configured")


def test_invalid_symbol_returns_validation_error(client):
    assert_error_envelope(client.get("/api/stocks/not a symbol"), 422, "validation_error")


def test_unknown_route_returns_not_found(client):
    assert_error_envelope(client.get("/api/does-not-exist"), 404, "not_found")


def test_cors_allows_frontend_origin_only(client):
    ok = client.options("/api/health", headers={"Origin": "http://localhost:5173",
                                                "Access-Control-Request-Method": "GET"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    bad = client.options("/api/health", headers={"Origin": "http://evil.example",
                                                 "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in bad.headers


def test_stock_search_works_without_database(client):
    """Phase 11: without MongoDB the curated list still answers."""
    body = client.get("/api/stocks/search?q=INFY").json()
    assert body["items"][0] == {"symbol": "INFY.NS", "company_name": None, "exchange": "NSE", "sector": None,
                                "industry": None, "source": "curated_list"}


def test_auth_without_database_returns_503(client):
    r = client.post("/api/auth/login", json={"email": "a@example.com", "password": "whatever1"})
    assert r.status_code == 503
