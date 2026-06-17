"""Typed configuration loaded from environment / .env."""

from __future__ import annotations

import functools
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PACKAGE_ROOT = Path(__file__).resolve().parent.parent


def _resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else (PACKAGE_ROOT / p)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PACKAGE_ROOT / ".env"),
        env_prefix="",
        extra="ignore",
        populate_by_name=True,
    )

    # Anthropic
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    model: str = Field(default="claude-opus-4-20250514", alias="SPX_MODEL")
    prompt_cache_enabled: bool = Field(default=True, alias="SPX_PROMPT_CACHE_ENABLED")

    # Run tuning
    recent_state_count: int = Field(default=6, alias="SPX_RECENT_STATE_COUNT")
    image_max_dimension: int = Field(default=1568, alias="SPX_IMAGE_MAX_DIMENSION")
    max_report_chars: int = Field(default=24000, alias="SPX_MAX_REPORT_CHARS")
    max_output_tokens: int = Field(default=8000, alias="SPX_MAX_OUTPUT_TOKENS")
    include_memory: bool = Field(default=False, alias="SPX_INCLUDE_MEMORY")

    # Market data
    treasury_ticker: str = Field(default="^TNX", alias="SPX_TREASURY_TICKER")
    spx_ticker: str = Field(default="^GSPC", alias="SPX_TICKER")
    vix_ticker: str = Field(default="^VIX", alias="SPX_VIX_TICKER")

    # Paths (relative to package root unless absolute)
    framework_path_raw: str = Field(
        default="framework/SPX-Daily-Analysis-Framework.md",
        alias="SPX_FRAMEWORK_PATH",
    )
    role_path_raw: str = Field(
        default="framework/SPX-Claude-Role-Block.md",
        alias="SPX_ROLE_PATH",
    )
    data_dir_raw: str = Field(default="data", alias="SPX_DATA_DIR")
    memory_dir_raw: str = Field(default="memory", alias="SPX_MEMORY_DIR")
    output_dir_raw: str = Field(default="output", alias="SPX_OUTPUT_DIR")

    @property
    def framework_path(self) -> Path:
        return _resolve(self.framework_path_raw)

    @property
    def role_path(self) -> Path:
        return _resolve(self.role_path_raw)

    @property
    def data_dir(self) -> Path:
        return _resolve(self.data_dir_raw)

    @property
    def runs_dir(self) -> Path:
        return self.data_dir / "runs"

    @property
    def memory_dir(self) -> Path:
        return _resolve(self.memory_dir_raw)

    @property
    def daily_states_dir(self) -> Path:
        return self.memory_dir / "daily_states"

    @property
    def daily_reports_dir(self) -> Path:
        return self.memory_dir / "daily_reports"

    @property
    def rolling_dir(self) -> Path:
        return self.memory_dir / "rolling"

    @property
    def output_dir(self) -> Path:
        return _resolve(self.output_dir_raw)


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
