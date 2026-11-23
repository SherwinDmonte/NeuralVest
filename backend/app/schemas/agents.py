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


# ---------------------------------------------------------------- Agent 5: Portfolio Optimization
PORTFOLIO_DISCLAIMER = ("Illustrative allocation based on historical data. It is not personalised investment "
                        "advice (NeuralVest is not a SEBI-registered adviser), and past performance, including "
                        "the backtest, does not guarantee future results.")
PortfolioMethod = Literal["max_sharpe", "min_volatility", "efficient_risk", "efficient_return", "equal_weight",
                          "inverse_volatility", "hrp"]
RiskPreferenceLiteral = Literal["conservative", "moderate", "aggressive"]
MAX_INVESTMENT_INR = 1_000_000_000  # Rs 100 crore: guards against typing errors


class PortfolioConstraints(BaseModel):
    min_weight_pct: float = Field(default=0.0, ge=0, le=100)
    max_weight_pct: float | None = Field(default=None, gt=0, le=100,
                                         description="Default from the risk preference (25/35/50%)")
    allow_short: Literal[False] = Field(default=False, description="Short selling is not supported")


class PortfolioOptimizationInput(BaseModel):
    symbols: list[str] = Field(min_length=2, max_length=10)
    investment_amount: float = Field(gt=0, le=MAX_INVESTMENT_INR, description="Amount in INR")
    risk_preference: RiskPreferenceLiteral = "moderate"
    method: PortfolioMethod | None = Field(default=None, description="Overrides the risk preference's method")
    constraints: PortfolioConstraints = Field(default_factory=PortfolioConstraints)
    target_volatility_pct: float | None = Field(default=None, gt=0, le=200)
    target_return_pct: float | None = Field(default=None, ge=-100, le=500)
    returns_model: Literal["mean", "ema"] = "mean"
    covariance_model: Literal["ledoit_wolf", "sample"] = "ledoit_wolf"
    backtest: bool = True
    rebalance: Literal["monthly", "quarterly", "none"] = "quarterly"
    transaction_cost_bps: float = Field(default=10.0, ge=0, le=200)


class PortfolioOutput(AgentEnvelope):
    """Request-level result: weights, rupee amounts, whole shares, expected figures, backtest."""
    agent: str = "portfolio_optimization"
    symbol: str = "__request__"
    portfolio_id: str
    symbols: list[str] = Field(default_factory=list)
    excluded_symbols: dict[str, str] = Field(default_factory=dict)  # symbol -> reason
    investment_amount: float
    risk_preference: str
    method_requested: str | None = None
    method: str | None = None
    method_source: str | None = None  # "requested" | "risk_preference"
    method_label: str | None = None
    fallback_reason: str | None = None
    constraints: dict[str, Any] = Field(default_factory=dict)
    assumptions: dict[str, Any] = Field(default_factory=dict)
    allocations: list[dict[str, Any]] = Field(default_factory=list)
    invested_inr: float | None = None
    leftover_cash_inr: float | None = None
    expected_metrics: dict[str, Any] = Field(default_factory=dict)
    inputs_per_stock: dict[str, dict[str, Any]] = Field(default_factory=dict)
    concentration: dict[str, Any] = Field(default_factory=dict)
    backtest: dict[str, Any] | None = None
    backtest_reason: str | None = None
    readings: dict[str, str] = Field(default_factory=dict)
    rules: dict[str, str] = Field(default_factory=dict)
    risk_free_rate: dict[str, Any] | None = None
    explanation: str | None = None
    disclaimer: str = PORTFOLIO_DISCLAIMER


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
