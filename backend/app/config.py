"""Application configuration loaded from environment variables / `backend/.env`.

All settings live in one typed object so that every module reads configuration the same
way and invalid values fail fast at startup instead of deep inside a request.
"""

from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent

APP_NAME = "NeuralVest API"
APP_VERSION = "0.3.0"

# Atlas free-tier (M0) storage quota covers documents + indexes.
ATLAS_FREE_TIER_LIMIT_MB = 512


class Settings(BaseSettings):
    """Typed settings. Unknown keys in `.env` (used by later phases) are ignored."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ----- App -----
    app_env: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    # Comma-separated list, e.g. "http://localhost:5173,http://127.0.0.1:5173"
    cors_origins: str = "http://localhost:5173"

    # ----- MongoDB Atlas -----
    mongodb_uri: SecretStr | None = None
    mongodb_db_name: str = "neuralvest_db"
    mongodb_test_db_name: str = "neuralvest_db_test"
    mongodb_server_selection_timeout_ms: int = Field(default=5000, ge=500, le=60000)
    mongodb_connect_timeout_ms: int = Field(default=10000, ge=500, le=60000)

    # ----- Storage guard (database_design.md §4.5) -----
    storage_limit_mb: float = Field(default=ATLAS_FREE_TIER_LIMIT_MB, gt=0)
    # Space used by OTHER projects on a shared cluster (NeuralVest cannot measure it).
    storage_reserved_mb: float = Field(default=0, ge=0)
    storage_warn_pct: float = Field(default=60, gt=0, lt=100)
    storage_block_pct: float = Field(default=85, gt=0, le=100)

    # ----- Retention -----
    market_data_max_years: int = Field(default=5, ge=1, le=50)

    # ----- Data collection (Phase 3) -----
    data_cache_dir: Path = PROJECT_ROOT / "data" / "cache"
    financial_reports_dir: Path = PROJECT_ROOT / "data" / "financial_reports"
    price_cache_hours: float = Field(default=12, ge=0)
    news_cache_minutes: float = Field(default=60, ge=0)
    fundamentals_cache_days: float = Field(default=7, ge=0)
    http_timeout_seconds: float = Field(default=20, gt=0, le=120)
    # GDELT asks for at most one request every 5 seconds; responses can take ~25 s.
    gdelt_min_interval_seconds: float = Field(default=6, ge=5)
    gdelt_timeout_seconds: float = Field(default=60, gt=0, le=180)

    # ----- Local LLM via Ollama (Phase 4) -----
    ollama_base_url: str = "http://localhost:11434"
    # Adaptive setup (decision after Phase 4): 1.7B when RAM allows, otherwise 0.6B.
    llm_primary_model: str = "qwen3:1.7b"
    # Empty = no second model; the deterministic template is the last fallback.
    llm_fallback_model: str | None = "qwen3:0.6b"
    llm_num_ctx: int = Field(default=2048, ge=512, le=8192)
    llm_temperature: float = Field(default=0.2, ge=0, le=1)
    llm_timeout_seconds: float = Field(default=90, gt=0, le=600)
    llm_keep_alive: str = "5m"  # how long Ollama keeps the model loaded between calls
    llm_min_free_ram_mb: int = Field(default=1800, ge=0)
    max_news_articles_llm: int = Field(default=8, ge=1, le=30)

    # ----- Orchestration (Phase 10) -----
    # sequential (default, 8 GB RAM) or parallel fan-out of News / Stock Analysis / Risk. LLM
    # calls stay serialized either way (one inference at a time).
    agent_execution_mode: Literal["sequential", "parallel"] = "sequential"
    # Extra attempts for an agent whose data source failed TEMPORARILY (network, rate limit).
    agent_retry_attempts: int = Field(default=1, ge=0, le=3)
    agent_retry_delay_seconds: float = Field(default=5, ge=0, le=60)
    # No new retries are started after this much workflow time (architecture §7: 15 min).
    workflow_time_budget_seconds: float = Field(default=900, ge=60, le=3600)
    # LangGraph SQLite checkpoints (optional; needs `pip install langgraph-checkpoint-sqlite`).
    workflow_checkpoints: bool = False
    # AI-written "key observations" in the final report (template text when false).
    report_llm_summary: bool = True

    # ----- Risk-free rate (Phase 8, decision D4): entered manually, all three required -----
    risk_free_rate_pct: float | None = Field(default=None, ge=-5, le=50)
    risk_free_rate_date: date | None = None
    risk_free_rate_source: str | None = None

    # ----- Authentication (Phase 11) -----
    # Generate locally: python -c "import secrets; print(secrets.token_urlsafe(48))"
    jwt_secret: SecretStr | None = None
    jwt_expire_minutes: int = Field(default=60, ge=5, le=1440)
    # true (Phase 12 default, the app has login pages): every analysis, portfolio, risk and report
    # endpoint needs a token. false: they also work without logging in (reports started that way
    # have no owner). A logged-in user's reports are always private to them.
    auth_required: bool = True

    # ----- Rate limits (Phase 11): "<count>/<second|minute|hour|day>", per user or IP -----
    rate_limit_enabled: bool = True
    rate_limit_auth: str = "10/minute"
    rate_limit_analysis: str = "5/minute"
    rate_limit_portfolio: str = "10/minute"
    rate_limit_pdf: str = "20/minute"

    @field_validator("jwt_secret", mode="before")
    @classmethod
    def _secret_placeholder(cls, value):
        if isinstance(value, str) and (not value.strip() or value.strip().startswith("<")):
            return None
        return value

    @field_validator("rate_limit_auth", "rate_limit_analysis", "rate_limit_portfolio", "rate_limit_pdf")
    @classmethod
    def _check_rate(cls, value: str) -> str:
        from limits import parse  # validated at startup, not on the first request

        try:
            parse(value)
        except ValueError as exc:
            raise ValueError(f"invalid rate limit '{value}' (use e.g. 5/minute)") from exc
        return value

    @property
    def auth_configured(self) -> bool:
        """A JWT secret of at least 32 characters is present."""
        return self.jwt_secret is not None and len(self.jwt_secret.get_secret_value().strip()) >= 32

    @field_validator("llm_fallback_model", mode="before")
    @classmethod
    def _empty_to_none(cls, value):
        return value.strip() or None if isinstance(value, str) else value

    @field_validator("risk_free_rate_pct", "risk_free_rate_date", "risk_free_rate_source", mode="before")
    @classmethod
    def _placeholder_to_none(cls, value):
        """Template placeholders like <value> or <YYYY-MM-DD> mean "not set yet"."""
        if isinstance(value, str) and (not value.strip() or value.strip().startswith("<")):
            return None
        return value

    @property
    def risk_free_rate(self) -> dict | None:
        """{value_pct, as_of_date, source} only when ALL three settings are present."""
        if self.risk_free_rate_pct is None or self.risk_free_rate_date is None or not self.risk_free_rate_source:
            return None
        return {"value_pct": self.risk_free_rate_pct, "as_of_date": self.risk_free_rate_date.isoformat(),
                "source": self.risk_free_rate_source.strip()}

    @model_validator(mode="after")
    def _check_thresholds(self) -> "Settings":
        if self.storage_warn_pct >= self.storage_block_pct:
            raise ValueError("STORAGE_WARN_PCT must be lower than STORAGE_BLOCK_PCT")
        if self.mongodb_db_name == self.mongodb_test_db_name:
            raise ValueError("MONGODB_DB_NAME and MONGODB_TEST_DB_NAME must differ")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def mongodb_configured(self) -> bool:
        """True only when a URI is present and its password placeholder was replaced."""
        if self.mongodb_uri is None:
            return False
        uri = self.mongodb_uri.get_secret_value().strip()
        return bool(uri) and "<password>" not in uri and "<username>" not in uri

    @property
    def active_db_name(self) -> str:
        """Tests always use the separate test database."""
        return self.mongodb_test_db_name if self.app_env == "test" else self.mongodb_db_name


@lru_cache
def get_settings() -> Settings:
    return Settings()
