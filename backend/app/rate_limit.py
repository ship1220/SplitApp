"""Small, dependency-free per-IP rate limiter for the API process."""

import asyncio
import os
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Tuple


class RateLimiter:
    """Sliding-window limiter with separate budgets for auth, writes, and reads."""

    def __init__(self) -> None:
        self.window_seconds = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
        self.auth_limit = int(os.getenv("RATE_LIMIT_AUTH_PER_WINDOW", "10"))
        self.write_limit = int(os.getenv("RATE_LIMIT_WRITE_PER_WINDOW", "60"))
        self.read_limit = int(os.getenv("RATE_LIMIT_READ_PER_WINDOW", "240"))
        self._requests: Dict[Tuple[str, str], Deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    def limit_for(self, method: str, path: str) -> Tuple[str, int]:
        if path.startswith("/api/auth/"):
            return "auth", self.auth_limit
        if method in {"POST", "PUT", "PATCH", "DELETE"}:
            return "write", self.write_limit
        return "read", self.read_limit

    async def check(self, client_ip: str, method: str, path: str) -> Tuple[bool, int, int]:
        """Return (allowed, configured_limit, seconds_until_next_request)."""
        category, limit = self.limit_for(method, path)
        if limit <= 0:  # Explicit opt-out for local development or troubleshooting.
            return True, limit, 0

        now = time.monotonic()
        cutoff = now - self.window_seconds
        key = (client_ip, category)
        async with self._lock:
            timestamps = self._requests[key]
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()
            if len(timestamps) >= limit:
                retry_after = max(1, int(timestamps[0] + self.window_seconds - now) + 1)
                return False, limit, retry_after
            timestamps.append(now)
            return True, limit, 0
