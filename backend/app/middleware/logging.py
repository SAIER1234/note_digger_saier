"""Structured request logging middleware — zero external deps.

Logs every API request with timestamp, method, path, status, duration.
Aggregates error counts for system status monitoring.
"""

import logging
import time
from collections import defaultdict
from pathlib import Path

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.config import BASE_DIR

# Setup file logger
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

logger = logging.getLogger("note_digger")
logger.setLevel(logging.INFO)

# File handler with rotation-sized log
fh = logging.FileHandler(LOG_DIR / "api.log", encoding="utf-8")
fh.setLevel(logging.INFO)
fh.setFormatter(logging.Formatter(
    "%(asctime)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
))
logger.addHandler(fh)

# Also log to console (systemd journal)
ch = logging.StreamHandler()
ch.setLevel(logging.WARNING)
logger.addHandler(ch)

# In-memory error counters (reset on restart)
error_counts: dict[str, int] = defaultdict(int)
request_counts: dict[str, int] = defaultdict(int)  # "YYYY-MM-DD HH:00" → count
recent_errors: list[dict] = []  # Last 20 errors


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request with structured fields."""

    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        duration_ms = (time.time() - start) * 1000

        status = response.status_code
        method = request.method
        path = request.url.path

        # Count requests per hour
        hour_key = time.strftime("%Y-%m-%d %H:00", time.localtime())
        request_counts[hour_key] += 1

        # Log
        client = request.client.host if request.client else "?"
        if status >= 500:
            logger.error(f"{method} {path} → {status} ({duration_ms:.0f}ms) [{client}]")
            error_counts["5xx"] += 1
            recent_errors.append({
                "time": time.strftime("%H:%M:%S"),
                "method": method,
                "path": path,
                "status": status,
                "duration_ms": round(duration_ms),
            })
            if len(recent_errors) > 20:
                recent_errors.pop(0)
        elif status >= 400:
            error_counts["4xx"] += 1
            if status != 404:  # Don't log 404s as they're mostly bots
                logger.warning(f"{method} {path} → {status} ({duration_ms:.0f}ms) [{client}]")
        else:
            logger.info(f"{method} {path} → {status} ({duration_ms:.0f}ms) [{client}]")

        return response


def get_log_stats() -> dict:
    """Get logging statistics for system status endpoint."""
    # Count total requests today
    today = time.strftime("%Y-%m-%d", time.localtime())
    today_requests = sum(
        v for k, v in request_counts.items() if k.startswith(today)
    )

    return {
        "requests_today": today_requests,
        "errors_5xx": error_counts.get("5xx", 0),
        "errors_4xx": error_counts.get("4xx", 0),
        "recent_errors": recent_errors[-5:],  # Last 5 errors
        "log_file": str(LOG_DIR / "api.log"),
    }
