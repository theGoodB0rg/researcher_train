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


@dataclass(frozen=True)
class Settings:
    openai_api_key: Optional[str]
    openai_model: str
    max_iterations: int
    require_real_data: bool
    allow_mock_data: bool
    source_timeout_sec: int


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o"),
        max_iterations=_parse_int(os.getenv("MAX_ITERATIONS"), 5),
        require_real_data=_parse_bool(os.getenv("REQUIRE_REAL_DATA"), True),
        allow_mock_data=_parse_bool(os.getenv("ALLOW_MOCK_DATA"), False),
        source_timeout_sec=_parse_int(os.getenv("SOURCE_TIMEOUT_SEC"), 8),
    )
