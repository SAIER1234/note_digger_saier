"""Simple in-memory rate limiter for API endpoints.

Limits:
  - Transcription endpoints: 10 requests per minute per IP
  - Auth endpoints: 20 requests per minute per IP
  - Other endpoints: unlimited
"""

import time
from collections import defaultdict
from typing import Optional


class RateLimiter:
    """Token-bucket style rate limiter (simplified: sliding window)."""

    def __init__(self):
        self._windows: dict[str, dict[str, list[float]]] = defaultdict(
            lambda: defaultdict(list)
        )

    def check(self, key: str, ip: str, max_req: int, window_sec: float = 60.0) -> tuple[bool, int]:
        """Check if request is allowed. Returns (allowed, remaining)."""
        now = time.time()
        requests = self._windows[key][ip]

        # Remove expired entries
        cutoff = now - window_sec
        requests[:] = [t for t in requests if t > cutoff]

        remaining = max(0, max_req - len(requests))

        if len(requests) >= max_req:
            return False, 0

        requests.append(now)
        return True, remaining - 1  # -1 because we just added one

    def cleanup(self):
        """Remove stale entries to prevent memory leaks."""
        now = time.time()
        for key in list(self._windows.keys()):
            for ip in list(self._windows[key].keys()):
                self._windows[key][ip] = [
                    t for t in self._windows[key][ip] if t > now - 120
                ]
                if not self._windows[key][ip]:
                    del self._windows[key][ip]
            if not self._windows[key]:
                del self._windows[key]


# Global instance
_limiter = RateLimiter()


def check_rate_limit(ip: str, endpoint: str = "default") -> tuple[bool, int]:
    """Check rate limit. Returns (allowed, remaining_requests)."""
    limits = {
        "transcribe": 10,   # 10 transcription requests/min
        "auth": 20,         # 20 auth requests/min
        "default": 60,      # 60 general requests/min
    }

    # Classify endpoint
    if "transcribe" in endpoint:
        key = "transcribe"
    elif "auth" in endpoint:
        key = "auth"
    else:
        key = "default"

    max_req = limits.get(key, 60)
    return _limiter.check(key, ip, max_req, window_sec=60.0)


# Periodic cleanup — call every ~100 requests
_cleanup_counter = 0


def maybe_cleanup():
    global _cleanup_counter
    _cleanup_counter += 1
    if _cleanup_counter > 100:
        _limiter.cleanup()
        _cleanup_counter = 0
