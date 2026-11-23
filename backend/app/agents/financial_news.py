"""Agent 2: Financial News.

Responsibility: find recent news about a company and describe it. Python collects,
cleans, de-duplicates and ranks articles. The LLM summarizes each article and labels
sentiment, category and relevance. Python then CHECKS those labels against facts it knows
(was the company actually named?) before anything is stored or shown.
"""

import logging
import time
from collections import Counter

from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.agents.common import LLMClient, save_agent_result
from app.config import Settings, get_settings
from app.data.errors import DataError, DataSourceError
from app.data.news_data import NewsArticle, collect_news, company_terms, match_terms
from app.data.symbols import normalize_symbol
from app.database.models import FinancialNewsDocument
from app.database.repository import bulk_upsert
from app.llm import prompts as p
from app.schemas.agents import AnalyzedArticle, DataSource, FinancialNewsOutput
from app.utils.timing import utc_now

logger = logging.getLogger("neuralvest.agents.financial_news")
AGENT_NAME = "financial_news"


def rank_articles(articles: list[NewsArticle], terms: list[str]) -> list[NewsArticle]:
    """Company named in the headline first, then named anywhere, then newest first."""
    def score(a: NewsArticle) -> tuple:
        in_headline = bool(match_terms(a.headline, terms))
        return (in_headline, bool(a.matched_terms), a.published_at.timestamp() if a.published_at else 0)
    return sorted(articles, key=score, reverse=True)


def check_relevance(llm_relevance: str, headline: str, matched_terms: list[str], terms: list[str]) -> str:
    """Rules applied on top of the model's label (small models over-rate relevance):
    'high' requires the company in the HEADLINE; no mention at all means 'low'."""
    if not matched_terms and not match_terms(headline, terms):
        return "low"
    if llm_relevance == "high" and not match_terms(headline, terms):
        return "medium"
    return llm_relevance


def overall_sentiment(articles: list[AnalyzedArticle]) -> str:
    """Majority of positive vs negative among relevant (high/medium) articles."""
    relevant = [a for a in articles if a.relevance in ("high", "medium")]
    if not relevant:
        return "insufficient_data"
    counts = Counter(a.sentiment for a in relevant)
    pos, neg = counts.get("positive", 0), counts.get("negative", 0)
    if pos == neg == 0:
        return "neutral"
    if pos == neg:
        return "mixed"
    return "positive" if pos > neg else "negative"


def run_financial_news(
    symbol: str,
    company_name: str,
    *,
    llm: LLMClient | None = None,
    db: Database | None = None,
    request_id: str | None = None,
    lookback_days: int = 14,
    include_gdelt: bool = True,
    settings: Settings | None = None,
    transport=None,  # tests inject a mock HTTP transport
) -> FinancialNewsOutput:
    settings = settings or get_settings()
    started = time.perf_counter()
    out = FinancialNewsOutput(symbol=str(symbol), company_name=company_name, lookback_days=lookback_days,
                              status="failed", generated_at=utc_now())
    try:
        out.symbol = normalize_symbol(symbol)
        news = collect_news(out.symbol, company_name, lookback_days=lookback_days, include_gdelt=include_gdelt,
                            settings=settings, transport=transport)
    except DataError as exc:
        out.errors.append(str(exc))
        out.retryable = isinstance(exc, DataSourceError)
        out.execution_seconds = time.perf_counter() - started
        return out

    out.source_status = news.source_status
    out.duplicates_removed = news.duplicates_removed
    out.articles_collected = len(news.articles)
    out.warnings.extend(news.warnings)
    out.data_sources.append(DataSource(source="RSS feeds + GDELT" if include_gdelt else "RSS feeds",
                                       detail=f"news, last {lookback_days} days", fetched_at=news.fetched_at))
    if include_gdelt and not out.source_status.get("gdelt", "").startswith("ok"):
        out.warnings.append("GDELT was unavailable (rate-limited or slow); results are from RSS feeds only.")

    # Analyse the most relevant articles (bounded: each one is an LLM call on the CPU).
    terms = company_terms(company_name, out.symbol)
    selected = rank_articles(news.articles, terms)[: settings.max_news_articles_llm]
    template_used = 0
    llm_meta = []
    for art in selected:
        fallback = p.news_analysis_fallback(art.headline, bool(art.matched_terms))
        if llm is not None:
            spec = p.news_analysis_prompt(company_name, out.symbol, art.headline, art.snippet, art.publisher,
                                          art.published_at)
            result = llm.generate_structured(spec, p.NewsAnalysisOutput, fallback)
            value, source, model = result.value, result.source, result.model
            llm_meta.append(result.metadata())
        else:
            value, source, model = fallback(), "template", None
        template_used += source == "template"
        out.articles.append(AnalyzedArticle(
            headline=art.headline, publisher=art.publisher, url=art.url, url_hash=art.url_hash,
            published_at=art.published_at, source=art.source, summary=value.summary,
            sentiment=value.sentiment, category=value.category,
            relevance=check_relevance(value.relevance, art.headline, art.matched_terms, terms),
            matched_terms=art.matched_terms, analysis_source=source, model=model,
        ))
    out.articles_analyzed = len(out.articles)
    if out.articles_collected > out.articles_analyzed:
        out.warnings.append(f"Analysed the {out.articles_analyzed} most relevant of {out.articles_collected} articles.")

    # Aggregate + digest
    out.sentiment_breakdown = dict(Counter(a.sentiment for a in out.articles))
    out.overall_sentiment = overall_sentiment(out.articles)
    if out.articles:
        latest = max(out.articles, key=lambda a: a.published_at.timestamp() if a.published_at else 0)
        fallback = p.news_digest_fallback(company_name, lookback_days, out.sentiment_breakdown,
                                          (latest.headline, latest.publisher))
        relevant = [a for a in out.articles if a.relevance != "low"] or out.articles
        items = [{"date": a.published_at.date().isoformat() if a.published_at else "unknown",
                  "sentiment": a.sentiment, "relevance": a.relevance, "summary": a.summary} for a in relevant]
        if llm is not None and len(items) >= 2:
            result = llm.generate_structured(p.news_digest_prompt(company_name, out.symbol, items),
                                             p.NewsDigestOutput, fallback)
            out.digest, out.digest_source = result.value.digest, result.source
            llm_meta.append(result.metadata())
        else:
            # One article (or no LLM): a digest would only repeat it, so use the factual count.
            out.digest, out.digest_source = fallback().digest, "template"
    else:
        out.digest = f"No recent news found for {company_name} in the last {lookback_days} days."

    models = sorted({m["model"] for m in llm_meta if m.get("model")})
    out.llm = {"calls": len(llm_meta), "models": models, "template_results": template_used,
               "model": models[0] if len(models) == 1 else ", ".join(models) or None}
    if template_used:
        out.warnings.append(f"{template_used} article(s) analysed without the AI model (sentiment 'uncertain').")

    all_failed = bool(news.source_status) and all(s.startswith("error") for s in news.source_status.values())
    out.status = "failed" if all_failed else "partial" if template_used else "completed"
    out.execution_seconds = time.perf_counter() - started
    _persist(db, request_id, out)
    return out


def _persist(db: Database | None, request_id: str | None, out: FinancialNewsOutput) -> None:
    if db is None:
        return
    # financial_news is the authoritative store of articles (database_design §2.1).
    try:
        docs = [FinancialNewsDocument(
            symbol=out.symbol, headline=a.headline[:500], publisher=a.publisher, article_url=a.url,
            url_hash=a.url_hash, publication_date=a.published_at, sentiment=a.sentiment,
            summary=a.summary[:300], category=a.category, relevance=a.relevance, source=a.source,
        ) for a in out.articles]
        if docs:
            bulk_upsert(db, docs, ["symbol", "url_hash"])
    except (PyMongoError, ValueError) as exc:
        out.warnings.append(f"Articles could not be saved to the database ({exc.__class__.__name__}).")
    # agent_results keeps references to the articles, not copies.
    stored = out.model_dump(mode="json", exclude={"articles"})
    stored["article_url_hashes"] = [a.url_hash for a in out.articles]
    if warning := save_agent_result(db, request_id, out, {"symbol": out.symbol, "company_name": out.company_name,
                                                          "lookback_days": out.lookback_days}, stored):
        out.warnings.append(warning)
