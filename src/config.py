import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional


def _parse_bool(raw_value: Optional[str], default: bool) -> bool:
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_int(raw_value: Optional[str], default: int) -> int:
    if raw_value is None:
        return default
    try:
        return int(raw_value)
    except ValueError:
        return default


def _parse_float(raw_value: Optional[str], default: float) -> float:
    if raw_value is None:
        return default
    try:
        return float(raw_value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    openai_api_key: Optional[str]
    openai_model: str
    max_iterations: int
    require_real_data: bool
    allow_mock_data: bool
    enable_reddit_source: bool
    min_record_quality_score: float
    source_timeout_sec: int
    hn_lookback_days: int
    hn_include_comments: bool


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o"),
        max_iterations=_parse_int(os.getenv("MAX_ITERATIONS"), 5),
        require_real_data=_parse_bool(os.getenv("REQUIRE_REAL_DATA"), True),
        allow_mock_data=_parse_bool(os.getenv("ALLOW_MOCK_DATA"), False),
        enable_reddit_source=_parse_bool(os.getenv("ENABLE_REDDIT_SOURCE"), False),
        min_record_quality_score=_parse_float(os.getenv("MIN_RECORD_QUALITY_SCORE"), 0.50),
        source_timeout_sec=_parse_int(os.getenv("SOURCE_TIMEOUT_SEC"), 8),
        hn_lookback_days=_parse_int(os.getenv("HN_LOOKBACK_DAYS"), 180),
        hn_include_comments=_parse_bool(os.getenv("HN_INCLUDE_COMMENTS"), True),
    )
