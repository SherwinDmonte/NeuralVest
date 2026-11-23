"""Pydantic document models for the 8 MongoDB collections (docs/database_design.md §3).

These are the application-level validation layer: every document written through the
repository helpers is built from one of these models first. They are stricter than the
database `$jsonSchema` validators (schema_validators.py) because they also check
cross-field rules, such as price ordering and weights that must sum to 100.
"""

import re
from datetime import UTC, date, datetime
from typing import Annotated, Any, ClassVar, Literal

from bson import ObjectId
from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    Field,
    PlainSerializer,
    field_validator,
    model_validator,
)

from app.utils.timing import utc_now

SCHEMA_VERSION = 1

# ---------------------------------------------------------------- collection names
USERS = "users"
STOCKS = "stocks"
MARKET_DATA = "market_data"
FINANCIAL_NEWS = "financial_news"
AGENT_RESULTS = "agent_results"
RISK_REPORTS = "risk_reports"
PORTFOLIOS = "portfolios"
ANALYSIS_REPORTS = "analysis_reports"
ALL_COLLECTIONS = (
    USERS, STOCKS, MARKET_DATA, FINANCIAL_NEWS, AGENT_RESULTS, RISK_REPORTS, PORTFOLIOS, ANALYSIS_REPORTS,
)

# ---------------------------------------------------------------- shared vocabularies
AgentName = Literal[
    "market_research", "financial_news", "stock_analysis", "risk_assessment", "portfolio_optimization"
]
ExecutionStatus = Literal["pending", "running", "completed", "partial", "failed", "skipped", "interrupted"]
ReportStatus = Literal["queued", "running", "completed", "partial", "failed", "interrupted"]
Sentiment = Literal["positive", "negative", "neutral", "uncertain"]
NewsCategory = Literal[
    "company_announcement", "quarterly_results", "m_and_a", "government_policy", "regulatory",
    "economic", "industry", "governance", "legal", "other",
]
Relevance = Literal["high", "medium", "low"]
OptimizationMethod = Literal[
    "max_sharpe", "min_volatility", "efficient_risk", "efficient_return", "equal_weight",
    "inverse_volatility", "hrp",
]
Exchange = Literal["NSE", "BSE"]
REQUEST_SCOPE_KEY = "__request__"

# Yahoo-style tickers: RELIANCE.NS, 500325.BO, M&M.NS, BAJAJ-AUTO.NS, ^NSEI (benchmark)
SYMBOL_PATTERN = r"^\^?[A-Z0-9&\-]{1,20}(\.(NS|BO))?$"


# ---------------------------------------------------------------- reusable field types
def _to_utc(value: datetime) -> datetime:
    """Store every timestamp as timezone-aware UTC; naive datetimes are rejected."""
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware (UTC)")
    return value.astimezone(UTC)


UtcDatetime = Annotated[datetime, AfterValidator(_to_utc)]


def _to_object_id(value: Any) -> ObjectId:
    if isinstance(value, ObjectId):
        return value
    if isinstance(value, str) and ObjectId.is_valid(value):
        return ObjectId(value)
    raise ValueError("must be a valid ObjectId")


# Kept as a real ObjectId when written to MongoDB, shown as a hex string in JSON.
PyObjectId = Annotated[
    ObjectId,
    BeforeValidator(_to_object_id),
    PlainSerializer(lambda v: str(v), return_type=str, when_used="json"),
]
Symbol = Annotated[str, Field(pattern=SYMBOL_PATTERN)]
Uuid = Annotated[str, Field(pattern=r"^[0-9a-f]{32}$")]


class MongoDocument(BaseModel):
    """Base class: forbids unknown fields (typos fail loudly) and carries schema_version."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True, validate_assignment=True)
    collection: ClassVar[str]

    schema_version: int = SCHEMA_VERSION

    def to_document(self) -> dict[str, Any]:
        """Python-native dict (datetimes and ObjectIds preserved) ready for PyMongo."""
        return self.model_dump(mode="python")


# ---------------------------------------------------------------- 3.1 users
class UserDocument(MongoDocument):
    collection: ClassVar[str] = USERS

    user_id: Uuid
    name: str = Field(min_length=1, max_length=80)
    email: EmailStr
    password_hash: str = Field(pattern=r"^\$argon2")  # never a plaintext password
    created_at: UtcDatetime = Field(default_factory=utc_now)
    updated_at: UtcDatetime = Field(default_factory=utc_now)

    @field_validator("email")
    @classmethod
    def _lower_email(cls, v: str) -> str:
        return v.lower()


# ---------------------------------------------------------------- 3.2 stocks
class StockDocument(MongoDocument):
    collection: ClassVar[str] = STOCKS

    symbol: Symbol
    company_name: str = Field(min_length=1)
    exchange: Exchange
    sector: str | None = None
    industry: str | None = None
    company_information: dict[str, Any] = Field(default_factory=dict)
    updated_at: UtcDatetime = Field(default_factory=utc_now)


# ---------------------------------------------------------------- 3.3 market_data
class MarketDataDocument(MongoDocument):
    collection: ClassVar[str] = MARKET_DATA

    symbol: Symbol
    date: UtcDatetime
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    adjusted_close: float = Field(gt=0)
    volume: int = Field(ge=0)
    source: str = Field(min_length=1)
    fetched_at: UtcDatetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def _price_order(self) -> "MarketDataDocument":
        if not (self.low <= min(self.open, self.close) and max(self.open, self.close) <= self.high):
            raise ValueError("prices must satisfy low <= open, close <= high")
        return self


# ---------------------------------------------------------------- 3.4 financial_news
class FinancialNewsDocument(MongoDocument):
    collection: ClassVar[str] = FINANCIAL_NEWS

    symbol: Symbol
    headline: str = Field(min_length=1, max_length=500)
    publisher: str = Field(min_length=1)
    article_url: str = Field(pattern=r"^https?://", max_length=2048)
    url_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    publication_date: UtcDatetime | None = None
    sentiment: Sentiment
    summary: str = Field(default="", max_length=300)
    category: NewsCategory = "other"
    relevance: Relevance = "medium"
    source: str = Field(pattern=r"^(gdelt|rss:.+)$")
    fetched_at: UtcDatetime = Field(default_factory=utc_now)


# ---------------------------------------------------------------- 3.5 agent_results
class AgentResultDocument(MongoDocument):
    """Authoritative store of agent outputs (database_design.md §2.1)."""

    collection: ClassVar[str] = AGENT_RESULTS

    request_id: Uuid
    agent_name: AgentName
    scope: Literal["symbol", "request"]
    scope_key: str = Field(min_length=1)
    symbol: Symbol | None = None
    execution_status: ExecutionStatus = "pending"
    attempts: int = Field(default=1, ge=1)
    input_summary: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(default_factory=dict)
    status_detail: dict[str, list] = Field(default_factory=lambda: {"warnings": [], "errors": []})
    llm_model: str | None = None
    execution_time: float | None = Field(default=None, ge=0)
    created_at: UtcDatetime = Field(default_factory=utc_now)
    updated_at: UtcDatetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def _scope_consistency(self) -> "AgentResultDocument":
        # scope_key is never null, so the unique index never collides on missing values.
        if self.scope == "symbol":
            if self.symbol is None or self.scope_key != self.symbol:
                raise ValueError("scope 'symbol' requires symbol and scope_key == symbol")
        elif self.symbol is not None or self.scope_key != REQUEST_SCOPE_KEY:
            raise ValueError(f"scope 'request' requires symbol=None and scope_key == '{REQUEST_SCOPE_KEY}'")
        return self


# ---------------------------------------------------------------- 3.6 risk_reports
class RiskFreeRate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value_pct: float = Field(ge=-5, le=50)
    as_of_date: date
    source: str = Field(min_length=1)

    def to_document(self) -> dict[str, Any]:
        # BSON has no plain `date` type; store the ISO string (the $jsonSchema accepts it).
        return {"value_pct": self.value_pct, "as_of_date": self.as_of_date.isoformat(), "source": self.source}


class RiskReportDocument(MongoDocument):
    """Write-once projection of the Risk Assessment output."""

    collection: ClassVar[str] = RISK_REPORTS

    request_id: Uuid
    symbols: list[Symbol] = Field(min_length=1)
    volatility: dict[str, float] = Field(default_factory=dict)
    beta: dict[str, float | None] = Field(default_factory=dict)
    sharpe_ratio: dict[str, float | None] = Field(default_factory=dict)
    maximum_drawdown: dict[str, float] = Field(default_factory=dict)
    correlation: dict[str, dict[str, float]] = Field(default_factory=dict)
    risk_classification: dict[str, Literal["low", "moderate", "high"]] = Field(default_factory=dict)
    risk_free_rate: RiskFreeRate
    source_agent_result_ids: list[PyObjectId] = Field(default_factory=list)
    created_at: UtcDatetime = Field(default_factory=utc_now)

    def to_document(self) -> dict[str, Any]:
        doc = super().to_document()
        doc["risk_free_rate"] = self.risk_free_rate.to_document()
        return doc


# ---------------------------------------------------------------- 3.7 portfolios
class StockAllocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: Symbol
    weight_pct: float = Field(ge=0, le=100)
    amount_inr: float = Field(ge=0)
    shares: int = Field(ge=0)
    last_price: float = Field(gt=0)


class PortfolioDocument(MongoDocument):
    """Write-once projection of the Portfolio Optimization output."""

    collection: ClassVar[str] = PORTFOLIOS

    portfolio_id: Uuid
    request_id: Uuid
    user_id: Uuid | None = None
    stock_allocations: list[StockAllocation] = Field(min_length=1)
    investment_amount: float = Field(gt=0)
    optimization_method: OptimizationMethod
    expected_metrics: dict[str, Any] = Field(default_factory=dict)
    source_agent_result_ids: list[PyObjectId] = Field(default_factory=list)
    created_at: UtcDatetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def _weights_sum_to_100(self) -> "PortfolioDocument":
        total = sum(a.weight_pct for a in self.stock_allocations)
        if abs(total - 100) > 0.01:
            raise ValueError(f"allocation weights must sum to 100 (got {total:.4f})")
        return self


# ---------------------------------------------------------------- 3.8 analysis_reports
class StatusEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ReportStatus
    at: UtcDatetime = Field(default_factory=utc_now)
    reason: str | None = None


class SectionRef(BaseModel):
    """A report section: references to the authoritative agent_results + a small headline."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    agent_result_ids: list[PyObjectId] = Field(default_factory=list)
    headline: dict[str, Any] = Field(default_factory=dict)


class AnalysisReportDocument(MongoDocument):
    """Job record (status, inputs, history) and, once finished, the report."""

    collection: ClassVar[str] = ANALYSIS_REPORTS

    report_id: Uuid
    request_id: Uuid
    user_id: Uuid | None = None
    symbols: list[Symbol] = Field(min_length=1)
    request_params: dict[str, Any]
    status: ReportStatus = "queued"
    status_history: list[StatusEvent] = Field(min_length=1)
    interrupted_reason: Literal["server_restart_during_run"] | None = None
    retry_of: Uuid | None = None
    market_analysis: SectionRef | None = None
    news_analysis: SectionRef | None = None
    fundamental_analysis: SectionRef | None = None
    risk_analysis: SectionRef | None = None
    portfolio_analysis: SectionRef | None = None
    final_summary: dict[str, Any] | None = None
    error_summary: list[dict[str, Any]] = Field(default_factory=list)
    requested_at: UtcDatetime = Field(default_factory=utc_now)
    generated_at: UtcDatetime | None = None
    completed_at: UtcDatetime | None = None

    @model_validator(mode="after")
    def _status_matches_history(self) -> "AnalysisReportDocument":
        if self.status_history[-1].status != self.status:
            raise ValueError("status must equal the last status_history entry")
        if (self.status == "interrupted") != (self.interrupted_reason is not None):
            raise ValueError("interrupted_reason is required exactly when status is 'interrupted'")
        return self


MODEL_BY_COLLECTION: dict[str, type[MongoDocument]] = {
    m.collection: m
    for m in (
        UserDocument, StockDocument, MarketDataDocument, FinancialNewsDocument, AgentResultDocument,
        RiskReportDocument, PortfolioDocument, AnalysisReportDocument,
    )
}


def is_valid_symbol(value: str) -> bool:
    return re.fullmatch(SYMBOL_PATTERN, value) is not None
