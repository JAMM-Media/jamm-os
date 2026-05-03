# app/core/rate_limit.py

import os
import threading
import time

from slowapi import Limiter
from slowapi.util import get_remote_address

_enabled = os.getenv("RATE_LIMIT_ENABLED", "true").lower() != "false"
limiter = Limiter(key_func=get_remote_address, enabled=_enabled)

# ---------------------------------------------------------------------------
# Email-based rate limiter (in-memory, single-server)
# Tracks request timestamps per email address. Entries older than the window
# are pruned on each check. Use Redis in production for multi-server setups.
# ---------------------------------------------------------------------------

_email_tracker: dict[str, list[float]] = {}
_tracker_lock = threading.Lock()


def check_email_rate_limit(email: str, max_requests: int, window_seconds: int) -> bool:
    """
    Returns True if the request is allowed, False if rate-limited.
    Records the request timestamp on success.
    """
    now = time.time()
    key = email.lower()
    with _tracker_lock:
        bucket = _email_tracker.get(key, [])
        bucket = [t for t in bucket if now - t < window_seconds]
        if len(bucket) >= max_requests:
            _email_tracker[key] = bucket
            return False
        bucket.append(now)
        _email_tracker[key] = bucket
        return True
