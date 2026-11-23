"""Input/output contracts of the agents (docs/architecture.md §5).

Every agent output shares the same envelope: which agent, status, when, from which data
sources, warnings/errors, and how the LLM text was produced.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

AgentStatus = Literal["completed", "partial", "failed", "skipped"]


class DataSource(BaseModel):
    source: str
    detail: str | None = None
    fetched_at: datetime | None = None
    data_as_of: str | None = None


class AgentEnvelope(BaseModel):
    agent: str
    symbol: str
    status: AgentStatus
    generated_at: datetime
    execution_seconds: float = 0.0
    data_sources: list[DataSource] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    llm: dict[str, Any] | None = None  # LLMResult.metadata()


# ---------------------------------------------------------------- Agent 1: Market Research
class MarketResearchInput(BaseModel):
    symbol: str
    period: Literal["6mo", "1y", "2y", "5y"] = "1y"


class MarketResearchOutput(AgentEnvelope):
    agent: str = "market_research"
    company_name: str | None = None
    last_close: float | None = None
    last_close_date: str | None = None
    last_bar_may_be_incomplete: bool = False
    period_return_pct: float | None = None
    indicators: dict[str, Any] = Field(default_factory=dict)
    rsi_zone: str | None = None
    volume: dict[str, Any] = Field(default_factory=dict)
    trend: dict[str, Any] = Field(default_factory=dict)
    benchmark_comparison: dict[str, Any] | None = None
    validation: dict[str, Any] = Field(default_factory=dict)
    # Interpretations computed by Python rules (always correct); shown above the AI text.
    readings: dict[str, str] = Field(default_factory=dict)
    explanation: str | None = None


# ---------------------------------------------------------------- Agent 3: Stock Analysis
class StockAnalysisInput(BaseModel):
    symbol: str
    last_close: float | None = None  # from the Market Research Agent


class StockAnalysisOutput(AgentEnvelope):
    agent: str = "stock_analysis"
    company_name: str | None = None
    sector: str | None = None
    industry: str | None = None
    is_bank: bool = False
    price_used: float | None = None
    price_date: str | None = None
    statement_periods: dict[str, str | None] = Field(default_factory=dict)
    statements_stale: bool = False
    metrics: dict[str, dict[str, Any]] = Field(default_factory=dict)  # fundamentals.Metric.as_dict()
    assessments: dict[str, str] = Field(default_factory=dict)
    assessment_rules: dict[str, str] = Field(default_factory=dict)
    overall: str = "insufficient_data"
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    unavailable: list[str] = Field(default_factory=list)  # metric names that could not be computed
    explanation: str | None = None


# ---------------------------------------------------------------- Agent 4: Risk Assessment
RISK_DISCLAIMER = ("Historical risk measurements describe the past. They are not forecasts and do not "
                   "guarantee future volatility, losses or returns.")


class RiskSymbolOutput(AgentEnvelope):
    agent: str = "risk_assessment"
    window: dict[str, Any] = Field(default_factory=dict)  # from, to, observations
    annualized_volatility_pct: float | None = None
    annualized_return_pct: float | None = None
    beta: dict[str, Any] = Field(default_factory=dict)
    max_drawdown: dict[str, Any] = Field(default_factory=dict)
    sharpe: dict[str, Any] = Field(default_factory=dict)
    return_distribution: dict[str, Any] = Field(default_factory=dict)
    risk_classification: str = "insufficient_data"
    market_sensitivity: str | None = None
    readings: dict[str, str] = Field(default_factory=dict)
    risk_free_rate: dict[str, Any] | None = None
    rules: dict[str, str] = Field(default_factory=dict)
    explanation: str | None = None
    disclaimer: str = RISK_DISCLAIMER


class RiskPortfolioOutput(AgentEnvelope):
    """Request-level result (correlation, concentration, diversification)."""
    agent: str = "risk_assessment"
    symbol: str = "__request__"
    symbols: list[str] = Field(default_factory=list)
    correlation: dict[str, Any] = Field(default_factory=dict)
    concentration: dict[str, Any] = Field(default_factory=dict)
    weights_assumption: str = "equal weights (portfolio weights are added in Phase 9)"
    diversification: dict[str, Any] = Field(default_factory=dict)
    risk_free_rate: dict[str, Any] | None = None
    disclaimer: str = RISK_DISCLAIMER


# ---------------------------------------------------------------- Agent 2: Financial News
class FinancialNewsInput(BaseModel):
    symbol: str
    company_name: str
    lookback_days: int = Field(default=14, ge=1, le=90)
    include_gdelt: bool = True


class AnalyzedArticle(BaseModel):
    headline: str
    publisher: str
    url: str
    url_hash: str
    published_at: datetime | None
    source: str
    summary: str
    sentiment: Literal["positive", "negative", "neutral", "uncertain"]
    category: str
    relevance: Literal["high", "medium", "low"]
    matched_terms: list[str] = Field(default_factory=list)
    analysis_source: Literal["llm", "template"]
    model: str | None = None


class FinancialNewsOutput(AgentEnvelope):
    agent: str = "financial_news"
    company_name: str
    lookback_days: int
    articles_collected: int = 0
    articles_analyzed: int = 0
    duplicates_removed: int = 0
    articles: list[AnalyzedArticle] = Field(default_factory=list)
    sentiment_breakdown: dict[str, int] = Field(default_factory=dict)
    overall_sentiment: Literal["positive", "negative", "neutral", "mixed", "insufficient_data"] = "insufficient_data"
    digest: str = ""
    digest_source: Literal["llm", "template", "none"] = "none"
    source_status: dict[str, str] = Field(default_factory=dict)
    disclaimer: str = ("News sentiment is generated by a small local AI model from headlines and short "
                       "summaries. It can be wrong and is not a prediction of future stock returns.")
