"""News collection without network: synthetic RSS/GDELT fixtures and a mock HTTP transport."""

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from app.config import Settings
from app.data import news_data as nd

FIXTURES = Path(__file__).parent / "fixtures"
TERMS = ["Reliance Industries", "RELIANCE"]


# ---------------------------------------------------------------- URL hygiene
@pytest.mark.parametrize(
    "url, expected",
    [
        ("HTTPS://News.Example.com/a?id=1&utm_source=x#frag", "https://news.example.com/a?id=1"),
        ("http://example.com", "http://example.com/"),
        ("https://user:pass@example.com/a", None),
        ("javascript:alert(1)", None),
        ("ftp://example.com/file", None),
        ("", None),
        ("https://example.com/" + "a" * 3000, None),
    ],
)
def test_normalize_url(url, expected):
    assert nd.normalize_url(url) == expected


# ---------------------------------------------------------------- text hygiene
def test_clean_text_strips_html_and_scripts():
    out = nd.clean_text("<p>Hello <b>world</b></p><script>alert(1)</script>")
    assert "<" not in out and "Hello world" in out


def test_clean_text_fixes_gdelt_spacing():
    raw = "RIL , SAIL rise as Asia - Pacific funds buy Reliance ' s stock"
    assert nd.clean_text(raw, gdelt=True) == "RIL, SAIL rise as Asia-Pacific funds buy Reliance's stock"


def test_company_terms_avoid_ambiguous_short_names():
    assert nd.company_terms("Reliance Industries Limited", "RELIANCE.NS", aliases=[]) == ["Reliance Industries", "RELIANCE"]
    assert nd.company_terms("Mahindra & Mahindra Ltd.", "M&M.NS", aliases=[]) == ["Mahindra & Mahindra"]


def test_company_terms_include_curated_aliases():
    assert nd.company_terms("Reliance Industries Limited", "RELIANCE.NS") == ["Reliance Industries", "RELIANCE", "RIL"]
    assert "M&M" in nd.company_terms("Mahindra & Mahindra Ltd.", "M&M.NS")
    assert nd.match_terms("RIL shares gain after results", ["RIL"]) == ["RIL"]
    assert nd.match_terms("April sales", ["RIL"]) == []  # whole words only, case-sensitive


def test_match_terms_uses_word_boundaries():
    assert nd.match_terms("Reliance Industries posts results", TERMS) == ["Reliance Industries"]
    assert nd.match_terms("Reliance Power shares rise", TERMS) == []
    assert nd.match_terms("RELIANCEX is not a match", TERMS) == []


# ---------------------------------------------------------------- RSS parsing
def test_parse_feed_filters_cleans_and_validates():
    articles = nd.parse_feed((FIXTURES / "sample_feed.xml").read_bytes(), "example", TERMS)
    headlines = [a.headline for a in articles]
    assert "Reliance Power shares rise" not in headlines  # other company
    assert all("javascript" not in a.url for a in articles)  # bad scheme dropped
    first = next(a for a in articles if a.headline == "Reliance Industries reports quarterly results")
    assert first.url == "https://news.example.com/a/1?id=1"  # tracking + fragment removed
    assert "<" not in first.snippet and "alert" not in first.snippet
    assert first.published_at == datetime(2026, 11, 20, 2, 45, tzinfo=UTC)
    assert first.source == "rss:example" and first.publisher == "Example Markets News"  # feed title fallback
    named = nd.parse_feed((FIXTURES / "sample_feed.xml").read_bytes(), "example", TERMS, publisher="Mint")
    assert {a.publisher for a in named} == {"Mint"}
    # Untrusted text is kept as plain data; it is never executed or followed.
    assert any(a.headline.startswith("Ignore all previous instructions") for a in articles)


def test_deduplicate_removes_syndicated_copies():
    articles = nd.parse_feed((FIXTURES / "sample_feed.xml").read_bytes(), "example", TERMS)
    unique, removed = nd.deduplicate(articles + articles)
    assert removed == len(articles) * 2 - len(unique)
    titles = [a.headline for a in unique]
    assert sum(t.startswith("Reliance Industries reports quarterly results") for t in titles) == 1


# ---------------------------------------------------------------- GDELT parsing
def test_parse_gdelt():
    articles = nd.parse_gdelt(json.loads((FIXTURES / "sample_gdelt.json").read_text()), TERMS)
    assert len(articles) == 2  # ftp URL rejected
    assert articles[0].headline == "RIL, SAIL among top upgrades as Asia-Pacific funds turn overweight"
    assert articles[0].published_at == datetime(2026, 11, 20, 6, 45, tzinfo=UTC)
    assert articles[1].matched_terms == ["Reliance Industries"]


# ---------------------------------------------------------------- full flow with a mock transport
def _settings(tmp_path) -> Settings:
    return Settings(_env_file=None, data_cache_dir=tmp_path)


def test_collect_news_end_to_end_offline(tmp_path, monkeypatch):
    feed = (FIXTURES / "sample_feed.xml").read_bytes()
    gdelt = (FIXTURES / "sample_gdelt.json").read_bytes()
    monkeypatch.setattr(nd, "utc_now", lambda: datetime(2026, 11, 22, tzinfo=UTC))
    monkeypatch.setattr(nd._gdelt_limiter, "wait", lambda _s: None)
    calls = {"gdelt": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["User-Agent"].startswith("NeuralVest/")  # no personal data
        if request.url.host == "api.gdeltproject.org":
            calls["gdelt"] += 1
            # First call rate-limited, second succeeds: exercises the retry path.
            return httpx.Response(429) if calls["gdelt"] == 1 else httpx.Response(200, content=gdelt)
        if "livemint" in request.url.host:
            return httpx.Response(503)
        return httpx.Response(200, content=feed)

    result = nd.collect_news("RELIANCE", "Reliance Industries Limited", settings=_settings(tmp_path),
                             transport=httpx.MockTransport(handler))
    assert result.symbol == "RELIANCE.NS" and not result.from_cache
    assert calls["gdelt"] == 2 and result.source_status["gdelt"].startswith("ok")
    assert result.source_status["rss:livemint_markets"].startswith("error")
    assert result.duplicates_removed > 0  # the same feed served by 6 working feeds
    assert len({a.url_hash for a in result.articles}) == len(result.articles)
    dates = [a.published_at for a in result.articles]
    assert dates == sorted(dates, reverse=True)

    again = nd.collect_news("RELIANCE", "Reliance Industries Limited", settings=_settings(tmp_path),
                            transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    assert again.from_cache and len(again.articles) == len(result.articles)


def test_collect_news_all_sources_down(tmp_path):
    result = nd.collect_news("TCS", "Tata Consultancy Services Limited", include_gdelt=False,
                             settings=_settings(tmp_path),
                             transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    assert result.articles == []
    assert any("All news sources failed" in w for w in result.warnings)
