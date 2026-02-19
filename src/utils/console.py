import os
import sys
from typing import Iterable, Optional

from termcolor import colored as _term_colored


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off", ""}


def _supports_color() -> bool:
    # Respect NO_COLOR convention and explicit force flag.
    if _bool_env("NO_COLOR", default=False):
        return False
    if _bool_env("FORCE_COLOR", default=False):
        return True

    stream = getattr(sys.stdout, "isatty", None)
    if not callable(stream) or not stream():
        return False

    term = (os.getenv("TERM") or "").strip().lower()
    if term == "dumb":
        return False
    return True


_ENABLE_COLOR = _supports_color()


def colored(
    text: object,
    color: Optional[str] = None,
    on_color: Optional[str] = None,
    attrs: Optional[Iterable[str]] = None,
) -> str:
    if not _ENABLE_COLOR:
        return str(text)
    return _term_colored(str(text), color=color, on_color=on_color, attrs=list(attrs) if attrs else None)

