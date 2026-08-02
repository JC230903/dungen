"""Tiny in-memory sliding-window rate limiter — one process, no Redis, matches
the rest of this app's "single uvicorn worker, in-memory state" model (see
`diagram_store.py`). Fine for a small self-hosted deployment; if this ever
runs multi-process, move the counters to Redis alongside the session store.
"""
from __future__ import annotations
import collections
import threading
import time


class RateLimiter:
    def __init__(self):
        self._hits: dict[str, collections.deque] = collections.defaultdict(collections.deque)
        self._lock = threading.Lock()

    def check(self, key: str, max_requests: int, window_seconds: float) -> bool:
        """True if this call is allowed (and records it); False if over limit."""
        now = time.time()
        cutoff = now - window_seconds
        with self._lock:
            dq = self._hits[key]
            while dq and dq[0] < cutoff:
                dq.popleft()
            if len(dq) >= max_requests:
                return False
            dq.append(now)
            return True

    def sweep(self, max_age_seconds: float = 3600):
        """Drop keys with no recent activity — call occasionally so this dict
        doesn't grow unbounded across many distinct IPs over a long uptime."""
        cutoff = time.time() - max_age_seconds
        with self._lock:
            dead = [k for k, dq in self._hits.items() if not dq or dq[-1] < cutoff]
            for k in dead:
                del self._hits[k]
