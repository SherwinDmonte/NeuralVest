"""Phase 11 API tests (task 11.5.1): auth flow, protected and user-scoped routes, pagination,
error codes, rate limits, search, sentiment and PDF - against the TEST database."""

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.agents import market_research as mr
from app.agents import stock_analysis as sa
from app.config import get_settings
from app.data import news_data as nd
from app.database import models as m
from app.database.repository import insert_document
from app.main import create_app
from app.orchestration import graph as graph_module
from app.orchestration.graph import build_graph
from app.services import analysis_runner as ar
from tests.agent_fakes import FakeLLM, news_transport, patch_benchmark, patch_fundamentals, patch_market_data

pytestmark = pytest.mark.integration
SECRET = SecretStr("t" * 48)
PASSWORD = "a-long-test-password"


def app_settings(**kw):
    return get_settings().model_copy(update={"jwt_secret": SECRET, "auth_required": False,
                                             "rate_limit_auth": "100/minute", "rate_limit_analysis": "100/minute",
                                             "rate_limit_pdf": "100/minute", **kw})


@pytest.fixture
def runner(clean_db, tmp_path, monkeypatch):
    patch_market_data(monkeypatch, mr)
    patch_fundamentals(monkeypatch, sa)
    patch_benchmark(monkeypatch, graph_module)
    monkeypatch.setattr(nd, "utc_now", lambda: datetime(2026, 11, 22, tzinfo=UTC))
    settings = get_settings().model_copy(update={"data_cache_dir": tmp_path, "risk_free_rate_pct": 6.0,
                                                 "risk_free_rate_date": date(2026, 11, 20),
                                                 "risk_free_rate_source": "test rate", "report_llm_summary": False})
    llm = FakeLLM()
    r = ar.AnalysisRunner(clean_db, settings, llm=llm, workflow_factory=lambda include_gdelt: build_graph(
        llm=llm, db=clean_db, settings=settings, include_gdelt=False, news_transport=news_transport()))
    yield r
    r.shutdown()


def make_client(runner, **settings_kw):
    return TestClient(create_app(app_settings(**settings_kw), runner=runner))


@pytest.fixture
def client(runner):
    with make_client(runner) as c:
        yield c


def register(client, email="asha@example.com", name="Asha", password=PASSWORD):
    return client.post("/api/auth/register", json={"name": name, "email": email, "password": password})


def login(client, email="asha@example.com", password=PASSWORD) -> dict:
    register(client, email=email, password=password)
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def error_code(resp) -> str:
    return resp.json()["error"]["code"]


def job(db, user_id=None, status="completed", symbols=("RELIANCE.NS",), requested_at=None, summary=None):
    rid = uuid.uuid4().hex
    doc = m.AnalysisReportDocument(
        report_id=uuid.uuid4().hex, request_id=rid, user_id=user_id, symbols=list(symbols),
        request_params={"symbols": list(symbols)}, status=status, status_history=[m.StatusEvent(status=status)],
        interrupted_reason="server_restart_during_run" if status == "interrupted" else None,
        final_summary=summary, requested_at=requested_at or datetime.now(UTC))
    insert_document(db, doc)
    return doc


# ---------------------------------------------------------------- 11.1 authentication
def test_register_login_me(client, clean_db):
    r = register(client, email="Asha@Example.com")
    assert r.status_code == 201
    user = r.json()["user"]
    assert user["email"] == "asha@example.com" and "password_hash" not in user and "password" not in r.text
    stored = clean_db[m.USERS].find_one({"user_id": user["user_id"]})
    assert stored["password_hash"].startswith("$argon2id$") and PASSWORD not in str(stored)

    r = client.post("/api/auth/login", json={"email": "ASHA@example.com", "password": PASSWORD})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer" and body["expires_in"] == 3600 and body["user"]["user_id"] == user["user_id"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200 and me.json()["user"]["email"] == "asha@example.com"


def test_register_validation_and_duplicates(client):
    assert register(client).status_code == 201
    dup = register(client, email="ASHA@example.com")
    assert dup.status_code == 409 and error_code(dup) == "email_already_registered"
    for bad in ({"password": "short"}, {"password": "password123"}, {"password": "aaaaaaaaaa"},
                {"email": "not-an-email"}, {"name": "   "}, {"email": "bob@example.com", "password": "bob@example.com"}):
        body = {"name": "Bob", "email": "bob@example.com", "password": PASSWORD} | bad
        r = client.post("/api/auth/register", json=body)
        assert r.status_code == 422 and error_code(r) == "validation_error", bad


def test_login_failures_are_generic(client):
    register(client)
    wrong = client.post("/api/auth/login", json={"email": "asha@example.com", "password": "wrong-password"})
    unknown = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": PASSWORD})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["error"]["message"] == unknown.json()["error"]["message"]
    assert error_code(wrong) == "invalid_credentials" and wrong.headers["WWW-Authenticate"] == "Bearer"


def test_me_needs_a_valid_token(client, clean_db):
    r = client.get("/api/auth/me")
    assert r.status_code == 401 and error_code(r) == "not_authenticated" and r.headers["WWW-Authenticate"] == "Bearer"
    assert error_code(client.get("/api/auth/me", headers={"Authorization": "Bearer nonsense"})) == "invalid_token"
    headers = login(client)
    clean_db[m.USERS].delete_many({})  # account deleted after the token was issued
    assert error_code(client.get("/api/auth/me", headers=headers)) == "invalid_token"


def test_auth_not_configured_returns_503(runner):
    with make_client(runner, jwt_secret=None) as c:
        r = register(c)
        assert r.status_code == 503 and error_code(r) == "auth_not_configured"
        r = c.get("/api/auth/me", headers={"Authorization": "Bearer x.y.z"})
        assert r.status_code == 503


# ---------------------------------------------------------------- 11.1.4 scoping
def test_analysis_is_private_to_its_owner(client, runner):
    asha, ravi = login(client), login(client, email="ravi@example.com")
    rid = client.post("/api/analysis/start", json={"symbols": ["RELIANCE"]}, headers=asha).json()["request_id"]
    runner.wait_idle()
    job_doc = runner.db[m.ANALYSIS_REPORTS].find_one({"request_id": rid})
    me = client.get("/api/auth/me", headers=asha).json()["user"]
    assert job_doc["user_id"] == me["user_id"]
    report_id = job_doc["report_id"]

    for path in (f"/api/analysis/{rid}/status", f"/api/analysis/{rid}", f"/api/analysis/{rid}/report",
                 f"/api/reports/{report_id}", f"/api/reports/{report_id}/pdf"):
        assert client.get(path, headers=asha).status_code == 200, path
        other, anonymous = client.get(path, headers=ravi), client.get(path)
        assert other.status_code == anonymous.status_code == 404, path  # same answer as "does not exist"
    assert client.post(f"/api/analysis/{rid}/rerun", headers=ravi).status_code == 404


def test_anonymous_analyses_follow_auth_required(runner):
    with make_client(runner) as c:  # AUTH_REQUIRED=false (Phase 11 default): the MVP dashboard keeps working
        rid = c.post("/api/analysis/start", json={"symbols": ["TCS"]}).json()["request_id"]
        runner.wait_idle()
        assert c.get(f"/api/analysis/{rid}").status_code == 200
        c.app.state.settings = c.app.state.settings.model_copy(update={"auth_required": True})
        r = c.post("/api/analysis/start", json={"symbols": ["TCS"]})
        assert r.status_code == 401 and error_code(r) == "not_authenticated"
        assert c.get(f"/api/analysis/{rid}").status_code == 401
        headers = login(c)
        assert c.get(f"/api/analysis/{rid}", headers=headers).status_code == 404  # unowned: hidden
        assert c.post("/api/analysis/start", json={"symbols": ["TCS"]}, headers=headers).status_code == 202
        runner.wait_idle()


def test_portfolio_is_scoped(client, clean_db):
    asha, ravi = login(client), login(client, email="ravi@example.com")
    owner = client.get("/api/auth/me", headers=asha).json()["user"]["user_id"]
    doc = m.PortfolioDocument(portfolio_id=uuid.uuid4().hex, request_id=uuid.uuid4().hex, user_id=owner,
                              stock_allocations=[m.StockAllocation(symbol="TCS.NS", weight_pct=100, amount_inr=1000,
                                                                   shares=1, last_price=1000)],
                              investment_amount=1000, optimization_method="equal_weight")
    insert_document(clean_db, doc)
    assert client.get(f"/api/portfolio/{doc.portfolio_id}", headers=asha).status_code == 200
    assert client.get(f"/api/portfolio/{doc.portfolio_id}", headers=ravi).status_code == 404


# ---------------------------------------------------------------- 11.2.4 reports list + pagination
def test_reports_list_is_paginated_and_per_user(client, clean_db):
    asha, ravi = login(client), login(client, email="ravi@example.com")
    owner = client.get("/api/auth/me", headers=asha).json()["user"]["user_id"]
    now = datetime.now(UTC)
    docs = [job(clean_db, owner, requested_at=now - timedelta(minutes=i), symbols=("TCS.NS",) if i == 2 else
                ("RELIANCE.NS",), summary={"key_observations": {"items": ["a", "b", "c"]}, "traceability": {"ok": True}})
            for i in range(3)]
    job(clean_db, None)  # anonymous: never listed

    assert client.get("/api/reports").status_code == 401
    page1 = client.get("/api/reports?page_size=2", headers=asha).json()
    assert page1["total"] == 3 and page1["has_next"] and len(page1["items"]) == 2
    assert [i["report_id"] for i in page1["items"]] == [docs[0].report_id, docs[1].report_id]  # newest first
    item = page1["items"][0]
    assert item["report_ready"] and item["key_observations"] == ["a", "b"] and item["pdf_url"].endswith("/pdf")
    page2 = client.get("/api/reports?page=2&page_size=2", headers=asha).json()
    assert len(page2["items"]) == 1 and not page2["has_next"]
    assert client.get("/api/reports?symbol=TCS.NS", headers=asha).json()["total"] == 1
    assert client.get("/api/reports?status=failed", headers=asha).json()["total"] == 0
    assert client.get("/api/reports", headers=ravi).json()["total"] == 0
    assert client.get("/api/reports?page=0", headers=asha).status_code == 422
    assert client.get("/api/reports?page_size=101", headers=asha).status_code == 422


def test_report_and_pdf_endpoints(client, runner, clean_db):
    headers = login(client)
    rid = client.post("/api/analysis/start", json={"symbols": ["RELIANCE", "TCS"], "investment_amount": 100000},
                      headers=headers).json()["request_id"]
    runner.wait_idle()
    report_id = client.get(f"/api/analysis/{rid}/report", headers=headers).json()["report_id"]
    full = client.get(f"/api/reports/{report_id}", headers=headers).json()
    assert full["request_id"] == rid and full["report"]["sections"] and full["market_research"]["RELIANCE.NS"]
    pdf = client.get(f"/api/reports/{report_id}/pdf", headers=headers)
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF") and "attachment" in pdf.headers["content-disposition"]
    assert pdf.headers["cache-control"] == "no-store"

    owner = client.get("/api/auth/me", headers=headers).json()["user"]["user_id"]
    queued = job(clean_db, owner, status="queued")
    r = client.get(f"/api/reports/{queued.report_id}/pdf", headers=headers)
    assert r.status_code == 409 and error_code(r) == "report_not_ready"
    assert client.get(f"/api/reports/{'0' * 32}", headers=headers).status_code == 404
    assert client.get("/api/reports/not-an-id", headers=headers).status_code == 422


# ---------------------------------------------------------------- 11.3.1 rate limits
def test_login_is_rate_limited(runner):
    with make_client(runner, rate_limit_auth="3/minute") as c:
        codes = [c.post("/api/auth/login", json={"email": "x@example.com", "password": "whatever1"}).status_code
                 for _ in range(4)]
        assert codes == [401, 401, 401, 429]
        r = c.post("/api/auth/login", json={"email": "x@example.com", "password": "whatever1"})
        assert error_code(r) == "rate_limited" and int(r.headers["Retry-After"]) >= 1


def test_analysis_start_is_rate_limited_per_user(runner):
    with make_client(runner, rate_limit_analysis="1/minute") as c:
        asha, ravi = login(c), login(c, email="ravi@example.com")
        assert c.post("/api/analysis/start", json={"symbols": ["TCS"]}, headers=asha).status_code == 202
        assert c.post("/api/analysis/start", json={"symbols": ["TCS"]}, headers=asha).status_code == 429
        assert c.post("/api/analysis/start", json={"symbols": ["TCS"]}, headers=ravi).status_code == 202  # own counter
        runner.wait_idle()


def test_rate_limits_can_be_disabled(runner):
    with make_client(runner, rate_limit_auth="1/minute", rate_limit_enabled=False) as c:
        codes = {c.post("/api/auth/login", json={"email": "x@example.com", "password": "whatever1"}).status_code
                 for _ in range(3)}
        assert codes == {401}


# ---------------------------------------------------------------- 11.2.1 / 11.2.2
def test_stock_search(client, clean_db):
    insert_document(clean_db, m.StockDocument(symbol="RELIANCE.NS", company_name="Reliance Industries Limited",
                                              exchange="NSE", sector="Energy"))
    by_name = client.get("/api/stocks/search?q=reliance industries").json()
    assert by_name["items"][0]["symbol"] == "RELIANCE.NS" and by_name["items"][0]["source"] == "stored"
    exact = client.get("/api/stocks/search?q=tcs").json()
    assert exact["items"][0]["symbol"] == "TCS.NS" and exact["normalized"] == "TCS.NS"
    assert client.get("/api/stocks/search?q=500325").json()["normalized"] == "500325.BO"
    regex = client.get("/api/stocks/search?q=.*").json()  # treated as text, not as a pattern
    assert regex["total"] == 0 and regex["normalized"] is None
    assert client.get("/api/stocks/search?q=").status_code == 422
    assert client.get("/api/stocks/search?q=x&limit=51").status_code == 422


def test_news_sentiment(client, clean_db):
    now = datetime.now(UTC)

    def article(i, sentiment, relevance="high", days_ago=1):
        url = f"https://news.example.com/{i}"
        return m.FinancialNewsDocument(symbol="TCS.NS", headline=f"Headline {i}", publisher="Example",
                                       article_url=url, url_hash=nd.url_hash(url), sentiment=sentiment,
                                       relevance=relevance, source="rss:test",
                                       publication_date=now - timedelta(days=days_ago))

    for doc in (article(1, "positive"), article(2, "positive"), article(3, "negative"),
                article(4, "negative", relevance="low"), article(5, "neutral"), article(6, "negative", days_ago=30)):
        insert_document(clean_db, doc)
    body = client.get("/api/news/TCS.NS/sentiment?days=14").json()
    assert body["articles"] == 5 and body["breakdown"] == {"positive": 2, "negative": 2, "neutral": 1, "uncertain": 0}
    assert body["relevant_breakdown"]["negative"] == 1 and body["overall_sentiment"] == "positive"
    assert body["breakdown_pct"]["positive"] == 40.0 and "local AI model" in body["disclaimer"]
    assert client.get("/api/news/TCS.NS/sentiment?days=60").json()["overall_sentiment"] == "mixed"
    empty = client.get("/api/news/INFY.NS/sentiment").json()
    assert empty["articles"] == 0 and empty["overall_sentiment"] == "insufficient_data" and empty["note"]
    assert client.get("/api/news/TCS.NS/sentiment?days=91").status_code == 422


def test_stored_unsafe_url_is_not_returned(client, clean_db):
    """11.3.3: a link edited in the database to something unsafe is dropped on the way out."""
    doc = m.FinancialNewsDocument(symbol="TCS.NS", headline="H", publisher="P", article_url="https://example.com/a",
                                  url_hash="a" * 64, sentiment="neutral", source="rss:test",
                                  publication_date=datetime.now(UTC))
    insert_document(clean_db, doc)
    clean_db[m.FINANCIAL_NEWS].update_one({"url_hash": "a" * 64},
                                          {"$set": {"article_url": "http://127.0.0.1/admin"}})
    items = client.get("/api/news/TCS.NS").json()["items"]
    assert items[0]["article_url"] is None


# ---------------------------------------------------------------- 12.4.4 watchlist
def test_watchlist(client, clean_db):
    headers = login(client)
    assert client.get("/api/auth/me/watchlist").status_code == 401
    assert client.get("/api/auth/me/watchlist", headers=headers).json() == {"symbols": [], "max": 20}
    r = client.put("/api/auth/me/watchlist", json={"symbols": ["reliance", "TCS.NS", "RELIANCE.NS", "500325"]},
                   headers=headers)
    assert r.status_code == 200 and r.json()["symbols"] == ["RELIANCE.NS", "TCS.NS", "500325.BO"]
    assert client.get("/api/auth/me/watchlist", headers=headers).json()["symbols"][0] == "RELIANCE.NS"
    other = login(client, email="ravi@example.com")
    assert client.get("/api/auth/me/watchlist", headers=other).json()["symbols"] == []  # per user
    assert client.put("/api/auth/me/watchlist", json={"symbols": ["not a symbol!"]}, headers=headers).status_code == 422
    too_many = [f"{100000 + i}" for i in range(21)]
    assert client.put("/api/auth/me/watchlist", json={"symbols": too_many}, headers=headers).status_code == 422
    stored = clean_db[m.USERS].find_one({"email": "asha@example.com"})
    assert m.UserDocument.model_validate({k: v for k, v in stored.items() if k != "_id"}).watchlist


def test_risk_needs_login_when_required(runner):
    with make_client(runner, auth_required=True) as c:
        r = c.post("/api/risk/analyze", json={"symbols": ["TCS"]})
        assert r.status_code == 401


# ---------------------------------------------------------------- 11.3.4 secrets
def test_no_secrets_in_responses_or_openapi(client):
    headers = login(client)
    for r in (client.get("/api/auth/me", headers=headers), client.get("/api/health"), client.get("/openapi.json")):
        assert SECRET.get_secret_value() not in r.text and "password_hash" not in r.text
    spec = client.get("/openapi.json").json()
    assert spec["components"]["securitySchemes"]["HTTPBearer"]["scheme"] == "bearer"
