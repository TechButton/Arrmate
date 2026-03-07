"""Simple in-memory fixed-window rate limiter for login endpoints.

No external dependencies — keeps track of (count, window_start) per key.
Not persisted across restarts, which is acceptable for brute-force throttling.
"""

import asyncio
import time
from collections import defaultdict
from typing import Tuple


class RateLimiter:
    """Fixed-window rate limiter keyed on an arbitrary string (e.g. client IP).

    Args:
        max_calls: Maximum number of calls allowed in *window_seconds*.
        window_seconds: Length of the counting window in seconds.
    """

    def __init__(self, max_calls: int = 10, window_seconds: int = 60) -> None:
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        # key → [count, window_start_time]
        self._counters: dict = defaultdict(lambda: [0, 0.0])
        self._lock = asyncio.Lock()

    async def check(self, key: str) -> Tuple[bool, int]:
        """Check whether *key* is within the rate limit.

        Returns:
            (allowed, retry_after_seconds)
            allowed is True when the call should proceed.
            retry_after_seconds is 0 when allowed, otherwise seconds until reset.
        """
        now = time.monotonic()
        async with self._lock:
            count, window_start = self._counters[key]
            if now - window_start >= self.window_seconds:
                # New window
                self._counters[key] = [1, now]
                return True, 0
            if count < self.max_calls:
                self._counters[key][0] += 1
                return True, 0
            retry_after = int(self.window_seconds - (now - window_start)) + 1
            return False, retry_after

    def _get_client_ip(self, request) -> str:
        """Extract the best-effort client IP from a FastAPI Request."""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.client.host if request.client else "unknown"


# Shared limiter instances — 10 attempts per IP per 60 seconds
login_limiter = RateLimiter(max_calls=10, window_seconds=60)
