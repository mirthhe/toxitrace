"""Per-request data mode: offline replay or live APIs, and whether the LLM may be called.

Locally, the mode comes from settings (TOXITRACE_OFFLINE). On a public deployment with
DEMO_ACCESS_CODE set, every request is offline by default; only requests carrying the right
access code run live, within an hourly limit. This keeps a public demo from spending the
maintainer's API quota or making ToxIndex calls under their name.
"""

import hmac
import threading
import time
from collections import deque
from contextlib import contextmanager
from contextvars import ContextVar

from app.config import settings

_offline: ContextVar[bool | None] = ContextVar("offline", default=None)
_llm: ContextVar[bool | None] = ContextVar("llm", default=None)


def offline() -> bool:
    value = _offline.get()
    return settings.toxitrace_offline if value is None else value


def llm_enabled() -> bool:
    value = _llm.get()
    return True if value is None else value


@contextmanager
def use(offline_mode: bool, llm: bool):
    tokens = (_offline.set(offline_mode), _llm.set(llm))
    try:
        yield
    finally:
        _offline.reset(tokens[0])
        _llm.reset(tokens[1])


def access_granted(code: str | None) -> bool:
    """True when no access code is configured (local use) or the given code matches."""
    if not settings.demo_access_code:
        return True
    return bool(code) and hmac.compare_digest(code, settings.demo_access_code)


def resolve(code: str | None) -> tuple[bool, bool]:
    """(offline, llm) for a request. Without a configured access code, settings decide."""
    if not settings.demo_access_code:
        return settings.toxitrace_offline, True
    live = access_granted(code)
    return not live, live


class HourlyLimit:
    """Caps live analyses per hour, per running instance (best effort on serverless)."""

    def __init__(self) -> None:
        self._calls: deque[float] = deque()
        self._lock = threading.Lock()

    def allow(self, limit: int) -> bool:
        now = time.monotonic()
        with self._lock:
            while self._calls and now - self._calls[0] > 3600:
                self._calls.popleft()
            if len(self._calls) >= limit:
                return False
            self._calls.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._calls.clear()


live_limit = HourlyLimit()
