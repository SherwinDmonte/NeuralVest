"""Financial news collection from GDELT and publisher RSS feeds.

Security: all retrieved text is UNTRUSTED. It is reduced to plain text (HTML removed),
length-limited and never treated as instructions. URLs are validated (http/https only, no
embedded credentials) and normalized before hashing.

Rate limits: GDELT asks for at most one request every 5 seconds (confirmed by its 429
response on 2026-11-23). A process-wide limiter spaces requests further apart than that.

Sentiment, categories, relevance scoring and LLM summaries are added by the Financial News
Agent in Phase 5. This module only collects, cleans and de-duplicates.
"""

import difflib
import hashlib
import logging
import re
import threading
import time
from calendar import timegm
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import feedparser
import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from app.config import APP_VERSION, Settings, get_settings
from app.data.cache import FileCache
from app.data.symbols import base_ticker, load_seed_symbols, normalize_symbol
from app.utils.timing import utc_now

logger = logging.getLogger("neuralvest.data.news")

# Generic client name only: no personal details are sent to external services.
USER_AGENT = f"NeuralVest/{APP_VERSION} (educational research project)"
GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
MAX_FEED_BYTES = 5 * 1024 * 1024
MAX_SNIPPET_CHARS = 500
DUPLICATE_TITLE_SIMILARITY = 0.9

# Verified working and current on 2026-11-23 (Moneycontrol feeds excluded: last item April 2024).
# name -> (publisher shown to users, feed URL)
RSS_FEEDS: dict[str, tuple[str, str]] = {
    "economictimes_markets": ("The Economic Times", "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"),
    "economictimes_stocks": ("The Economic Times", "https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms"),
    "livemint_markets": ("Mint", "https://www.livemint.com/rss/markets"),
    "livemint_companies": ("Mint", "https://www.livemint.com/rss/companies"),
    "business_standard_markets": ("Business Standard", "https://www.business-standard.com/rss/markets-106.rss"),
    "business_standard_companies": ("Business Standard", "https://www.business-standard.com/rss/companies-101.rss"),
    "hindu_businessline_markets": ("The Hindu BusinessLine", "https://www.thehindubusinessline.com/markets/feeder/default.rss"),
    "ndtvprofit_latest": ("NDTV Profit", "https://feeds.feedburner.com/ndtvprofit-latest"),
}
GDELT_429_BACKOFF_SECONDS = 15  # extra wait per attempt after a rate-limit response

_TRACKING_PARAMS = re.compile(r"^(utm_.*|fbclid|gclid|mc_cid|mc_eid|ref|ref_src)$", re.I)
_COMPANY_SUFFIX = re.compile(r"\s+(limited|ltd\.?|ltd|pvt\.?|private|plc|inc\.?|corporation|corp\.?)$", re.I)


class NewsArticle(BaseModel):
    headline: str
    publisher: str
    url: str
    url_hash: str
    published_at: datetime | None
    source: str  # "gdelt" | "rss:<feed name>"
    snippet: str = ""
    matched_terms: list[str] = Field(default_factory=list)


@dataclass
class NewsCollection:
    symbol: str
    company_name: str
    articles: list[NewsArticle]
    fetched_at: datetime
    from_cache: bool
    duplicates_removed: int = 0
    source_status: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------- text and URL hygiene
def clean_text(value: str | None, max_chars: int = MAX_SNIPPET_CHARS, gdelt: bool = False) -> str:
    """HTML -> plain text, whitespace collapsed, spacing artefacts fixed, length-capped."""
    if not value:
        return ""
    text = BeautifulSoup(value, "html.parser").get_text(" ") if "<" in value else value
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:!?%)\]])", r"\1", text)  # "RIL , SAIL" -> "RIL, SAIL"
    text = re.sub(r"([(\[])\s+", r"\1", text)
    if gdelt:
        # GDELT tokenizes punctuation: "Asia - Pacific", "seven - month", "Reliance ' s"
        text = re.sub(r"(?<=\w) - (?=\w)", "-", text)
        text = re.sub(r"(?<=\w) ' (?=s\b)", "'", text)
    return text[:max_chars].rstrip()


def normalize_url(url: str | None) -> str | None:
    """Validated, canonical URL or None. Drops fragments and tracking parameters."""
    if not url or len(url) > 2048:
        return None
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return None
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
        return None
    if parts.username or parts.password:
        return None  # credentials in a URL are never acceptable
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                       if not _TRACKING_PARAMS.match(k)])
    netloc = parts.hostname.lower() + (f":{parts.port}" if parts.port else "")
    return urlunsplit((parts.scheme.lower(), netloc, parts.path or "/", query, ""))


def url_hash(normalized_url: str) -> str:
    return hashlib.sha256(normalized_url.encode("utf-8")).hexdigest()


def company_terms(company_name: str, symbol: str, aliases: list[str] | None = None) -> list[str]:
    """Search terms for a company, e.g. 'Reliance Industries Limited', RELIANCE.NS, ['RIL'] ->
    ['Reliance Industries', 'RELIANCE', 'RIL']. A plain first word such as 'Reliance' is NOT
    used, because it would also match other companies (Reliance Power, Reliance Capital...).
    Aliases are the abbreviations newsrooms actually use (curated in seed_symbols.json)."""
    terms: list[str] = []
    name = _COMPANY_SUFFIX.sub("", company_name.strip()).strip()
    if name:
        terms.append(name)
    ticker = base_ticker(symbol)
    if ticker.isalpha() and len(ticker) >= 3 and ticker.lower() != name.lower():
        terms.append(ticker)
    for alias in aliases if aliases is not None else symbol_aliases(symbol):
        if alias and alias.lower() not in (t.lower() for t in terms):
            terms.append(alias)
    return terms


def symbol_aliases(symbol: str) -> list[str]:
    """Curated news aliases for a symbol (empty if none)."""
    return load_seed_symbols().get("news_aliases", {}).get(symbol, [])


def match_terms(text: str, terms: list[str]) -> list[str]:
    """Whole-word matches. Company names match in any case; tickers (all caps) only as
    written, otherwise "RELIANCE" would match "Reliance Power"."""
    matched = []
    for term in terms:
        flags = 0 if term.isupper() else re.IGNORECASE
        if re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text, flags):
            matched.append(term)
    return matched


def _title_key(title: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", title.lower())


def deduplicate(articles: list[NewsArticle]) -> tuple[list[NewsArticle], int]:
    """Remove repeats: same URL hash, or near-identical headline (syndicated copies)."""
    unique: list[NewsArticle] = []
    seen_hashes: set[str] = set()
    for art in sorted(articles, key=lambda a: (a.published_at is None, a.published_at or utc_now())):
        if art.url_hash in seen_hashes:
            continue
        key = _title_key(art.headline)
        if any(difflib.SequenceMatcher(None, key, _title_key(u.headline)).ratio() >= DUPLICATE_TITLE_SIMILARITY
               for u in unique):
            continue
        seen_hashes.add(art.url_hash)
        unique.append(art)
    return unique, len(articles) - len(unique)


# ---------------------------------------------------------------- RSS
def _struct_to_dt(value) -> datetime | None:
    return datetime.fromtimestamp(timegm(value), tz=UTC) if value else None


def parse_feed(content: bytes, feed_name: str, terms: list[str], publisher: str | None = None) -> list[NewsArticle]:
    """Parse one RSS/Atom document and keep only entries mentioning the company."""
    parsed = feedparser.parse(content)
    publisher = publisher or clean_text(parsed.feed.get("title"), 120) or feed_name
    articles = []
    for entry in parsed.entries:
        headline = clean_text(entry.get("title"), 300)
        snippet = clean_text(entry.get("summary"))
        url = normalize_url(entry.get("link"))
        if not headline or not url:
            continue
        matched = match_terms(f"{headline} {snippet}", terms)
        if not matched:
            continue
        articles.append(NewsArticle(
            headline=headline, publisher=publisher, url=url, url_hash=url_hash(url),
            published_at=_struct_to_dt(entry.get("published_parsed") or entry.get("updated_parsed")),
            source=f"rss:{feed_name}", snippet=snippet, matched_terms=matched,
        ))
    return articles


def fetch_rss(client: httpx.Client, terms: list[str],
              feeds: dict[str, tuple[str, str]] = RSS_FEEDS) -> tuple[list[NewsArticle], dict[str, str]]:
    articles: list[NewsArticle] = []
    status: dict[str, str] = {}
    for name, (publisher, url) in feeds.items():
        try:
            resp = client.get(url)
            resp.raise_for_status()
            if len(resp.content) > MAX_FEED_BYTES:
                status[f"rss:{name}"] = "skipped: response too large"
                continue
            found = parse_feed(resp.content, name, terms, publisher)
            articles.extend(found)
            status[f"rss:{name}"] = f"ok ({len(found)} matching)"
        except httpx.HTTPError as exc:
            status[f"rss:{name}"] = f"error: {exc.__class__.__name__}"
            logger.warning("RSS feed %s failed: %s", name, exc.__class__.__name__)
    return articles, status


# ---------------------------------------------------------------- GDELT
class _RateLimiter:
    """Process-wide minimum spacing between calls (thread-safe)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last = 0.0

    def wait(self, min_interval: float) -> None:
        with self._lock:
            delay = self._last + min_interval - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            self._last = time.monotonic()


_gdelt_limiter = _RateLimiter()


def _parse_gdelt_date(value: str | None) -> datetime | None:
    try:
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC) if value else None
    except ValueError:
        return None


def parse_gdelt(payload: dict, terms: list[str]) -> list[NewsArticle]:
    articles = []
    for item in payload.get("articles", []) or []:
        headline = clean_text(item.get("title"), 300, gdelt=True)
        url = normalize_url(item.get("url"))
        if not headline or not url:
            continue
        articles.append(NewsArticle(
            headline=headline, publisher=clean_text(item.get("domain"), 120) or "unknown",
            url=url, url_hash=url_hash(url), published_at=_parse_gdelt_date(item.get("seendate")),
            source="gdelt", matched_terms=match_terms(headline, terms),
        ))
    return articles


def fetch_gdelt(client: httpx.Client, company_name: str, terms: list[str], lookback_days: int,
                settings: Settings, max_records: int = 50) -> tuple[list[NewsArticle], str]:
    query = f'"{_COMPANY_SUFFIX.sub("", company_name).strip()}" sourcecountry:IN sourcelang:english'
    params = {"query": query, "mode": "ArtList", "format": "json", "maxrecords": max_records,
              "timespan": f"{lookback_days}d", "sort": "DateDesc"}
    rate_limited = 0
    for attempt in range(3):
        # Spacing grows after each rate-limit response (observed: 6 s spacing is not always enough).
        _gdelt_limiter.wait(settings.gdelt_min_interval_seconds + GDELT_429_BACKOFF_SECONDS * rate_limited)
        try:
            resp = client.get(GDELT_URL, params=params, timeout=settings.gdelt_timeout_seconds)
        except httpx.HTTPError as exc:
            logger.warning("GDELT request failed: %s", exc.__class__.__name__)
            continue
        if resp.status_code == 429:
            rate_limited += 1
            logger.warning("GDELT rate limit (attempt %d)", attempt + 1)
            continue
        if resp.status_code != 200:
            return [], f"error: HTTP {resp.status_code}"
        if not resp.content.strip():
            return [], "ok (0 articles)"
        try:
            found = parse_gdelt(resp.json(), terms)
        except ValueError:
            return [], "error: invalid JSON"
        return found, f"ok ({len(found)} articles)"
    return [], "error: unavailable or rate-limited after retries"


# ---------------------------------------------------------------- public API
def _serialize(c: NewsCollection) -> dict:
    return {"company_name": c.company_name, "duplicates_removed": c.duplicates_removed,
            "source_status": c.source_status, "warnings": c.warnings,
            "articles": [a.model_dump(mode="json") for a in c.articles]}


def collect_news(
    symbol: str,
    company_name: str,
    lookback_days: int = 14,
    use_cache: bool = True,
    include_gdelt: bool = True,
    settings: Settings | None = None,
    transport: httpx.BaseTransport | None = None,  # tests inject a mock transport
) -> NewsCollection:
    """Collect, clean and de-duplicate recent news about one company."""
    settings = settings or get_settings()
    symbol = normalize_symbol(symbol)
    cache = FileCache(settings.data_cache_dir)
    key = f"{symbol}_{lookback_days}d_{'gdelt' if include_gdelt else 'rss'}"
    if use_cache and (hit := cache.read("news", key, timedelta(minutes=settings.news_cache_minutes))):
        data, fetched_at = hit
        return NewsCollection(symbol=symbol, company_name=data["company_name"],
                              articles=[NewsArticle(**a) for a in data["articles"]], fetched_at=fetched_at,
                              from_cache=True, duplicates_removed=data["duplicates_removed"],
                              source_status=data["source_status"], warnings=data["warnings"])

    terms = company_terms(company_name, symbol)
    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=settings.http_timeout_seconds,
                      follow_redirects=True, transport=transport) as client:
        articles, status = fetch_rss(client, terms)
        if include_gdelt:
            gdelt_articles, status["gdelt"] = fetch_gdelt(client, company_name, terms, lookback_days, settings)
            articles.extend(gdelt_articles)

    cutoff = utc_now() - timedelta(days=lookback_days)
    recent = [a for a in articles if a.published_at is None or a.published_at >= cutoff]
    unique, removed = deduplicate(recent)
    unique.sort(key=lambda a: a.published_at or datetime.min.replace(tzinfo=UTC), reverse=True)

    warnings = []
    if not unique:
        warnings.append(f"No news found for {company_name} in the last {lookback_days} days.")
    if all(s.startswith("error") for s in status.values()):
        warnings.append("All news sources failed; results may be incomplete.")
    if any(a.published_at is None for a in unique):
        warnings.append("Some articles have no publication date.")

    collection = NewsCollection(symbol=symbol, company_name=company_name, articles=unique, fetched_at=utc_now(),
                                from_cache=False, duplicates_removed=removed, source_status=status, warnings=warnings)
    collection.fetched_at = cache.write("news", key, _serialize(collection))
    return collection
