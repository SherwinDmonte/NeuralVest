"""Application configuration loaded from environment variables / `backend/.env`.

All settings live in one typed object so that every module reads configuration the same
way and invalid values fail fast at startup instead of deep inside a request.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent

APP_NAME = "NeuralVest API"
APP_VERSION = "0.2.0"

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

    @field_validator("llm_fallback_model", mode="before")
    @classmethod
    def _empty_to_none(cls, value):
        return value.strip() or None if isinstance(value, str) else value

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
