from datetime import UTC, datetime

import pytest

from app.agents import financial_news as fn
from app.config import Settings
from app.data import news_data as nd
from app.database import models as m
from app.schemas.agents import AnalyzedArticle
from tests.agent_fakes import FakeLLM, news_transport

TERMS = ["Reliance Industries", "RELIANCE", "RIL"]


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch):
    # The synthetic feed is dated 20-21 Nov 2026; keep it inside the 14-day window.
    monkeypatch.setattr(nd, "utc_now", lambda: datetime(2026, 11, 22, tzinfo=UTC))


def settings(tmp_path) -> Settings:
    return Settings(_env_file=None, data_cache_dir=tmp_path)


def run(tmp_path, llm=None, status=200, **kw):
    return fn.run_financial_news("RELIANCE.NS", "Reliance Industries Limited", llm=llm, include_gdelt=False,
                                 settings=settings(tmp_path), transport=news_transport(status), **kw)


# ---------------------------------------------------------------- rules
@pytest.mark.parametrize(
    "llm_label, headline, matched, expected",
    [
        ("high", "Reliance Industries posts results", ["Reliance Industries"], "high"),
        ("high", "Fund managers raise gold exposure", ["RIL"], "medium"),  # named only in the snippet
        ("medium", "Markets close higher", [], "low"),  # not named at all
        ("low", "RIL shares rise", ["RIL"], "low"),  # the model may lower relevance
    ],
)
def test_check_relevance(llm_label, headline, matched, expected):
    assert fn.check_relevance(llm_label, headline, matched, TERMS) == expected


def art(sentiment, relevance="high") -> AnalyzedArticle:
    return AnalyzedArticle(headline="h", publisher="p", url="https://x.example/", url_hash="a" * 64,
                           published_at=None, source="rss:x", summary="s", sentiment=sentiment,
                           category="other", relevance=relevance, analysis_source="llm")


@pytest.mark.parametrize(
    "items, expected",
    [([], "insufficient_data"), ([art("positive"), art("negative"), art("positive")], "positive"),
     ([art("positive"), art("negative")], "mixed"), ([art("neutral"), art("uncertain")], "neutral"),
     ([art("negative", "low")], "insufficient_data")],
)
def test_overall_sentiment(items, expected):
    assert fn.overall_sentiment(items) == expected


# ---------------------------------------------------------------- agent runs
def test_analysis_with_llm(tmp_path):
    llm = FakeLLM()
    out = run(tmp_path, llm=llm)
    assert out.status == "completed" and out.articles_analyzed == len(out.articles) > 0
    assert "Reliance Power shares rise" not in [a.headline for a in out.articles]
    assert out.duplicates_removed > 0  # 8 feeds serve the same items
    assert llm.calls.count("news_analysis") == out.articles_analyzed and llm.calls[-1] == "news_digest"
    assert out.digest_source == "llm" and out.overall_sentiment == "positive"
    assert all(a.analysis_source == "llm" for a in out.articles)
    assert "not a prediction" in out.disclaimer


def test_without_llm_nothing_is_guessed(tmp_path):
    out = run(tmp_path, llm=None)
    assert out.status == "partial" and {a.sentiment for a in out.articles} == {"uncertain"}
    assert out.digest_source == "template" and "uncertain" in out.digest


def test_all_sources_down_fails(tmp_path):
    out = run(tmp_path, status=500)
    assert out.status == "failed" and out.articles == []


def test_article_limit(tmp_path):
    s = Settings(_env_file=None, data_cache_dir=tmp_path, max_news_articles_llm=1)
    llm = FakeLLM()
    out = fn.run_financial_news("RELIANCE.NS", "Reliance Industries Limited", llm=llm, include_gdelt=False,
                                settings=s, transport=news_transport())
    assert out.articles_analyzed == 1 and out.articles_collected > 1
    assert any("most relevant" in w for w in out.warnings)
    # One article: no LLM digest (it would only repeat the summary); factual digest instead.
    assert "news_digest" not in llm.calls and out.digest_source == "template"
    assert out.digest.startswith("1 recent article")


@pytest.mark.integration
def test_articles_and_references_saved(tmp_path, clean_db):
    out = run(tmp_path, llm=FakeLLM(), db=clean_db, request_id="b" * 32)
    assert clean_db[m.FINANCIAL_NEWS].count_documents({"symbol": "RELIANCE.NS"}) == out.articles_analyzed
    doc = clean_db[m.AGENT_RESULTS].find_one({"request_id": "b" * 32, "agent_name": "financial_news"})
    assert "articles" not in doc["output"]  # references, not copies
    assert sorted(doc["output"]["article_url_hashes"]) == sorted(a.url_hash for a in out.articles)
