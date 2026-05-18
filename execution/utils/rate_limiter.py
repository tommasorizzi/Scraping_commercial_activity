"""
Rate limiter with retry + exponential back-off.

Used by every script that makes external API calls to stay within
SerpAPI's free-tier limit (50 req/hour) and handle transient errors.
"""

import time
from typing import TypeVar, Callable, Any

T = TypeVar("T")


class RateLimiter:
    """Simple token-bucket-style rate limiter with retry logic."""

    def __init__(self, delay_seconds: float = 2.0, max_retries: int = 3):
        self.delay = delay_seconds
        self.max_retries = max_retries
        self._last_request: float = 0.0

    def wait(self) -> None:
        """Block until enough time has passed since the last request."""
        elapsed = time.time() - self._last_request
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_request = time.time()

    def execute(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Call *func* with rate limiting and retry on failure.

        Retries up to ``max_retries`` times with exponential back-off
        (delay × 2^attempt).  The last exception is re-raised if all
        retries are exhausted.
        """
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                self.wait()
                return func(*args, **kwargs)
            except Exception as exc:
                last_error = exc
                backoff = self.delay * (2 ** attempt)
                if attempt < self.max_retries - 1:
                    time.sleep(backoff)
        raise last_error  # type: ignore[misc]
