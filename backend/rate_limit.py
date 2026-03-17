# rate_limit.py
import time
from collections import defaultdict
from fastapi import Request, HTTPException, status

class InMemoryRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window = window_seconds
        self.hits = defaultdict(list)

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        window_start = now - self.window

        recent = [ts for ts in self.hits[key] if ts >= window_start]
        self.hits[key] = recent

        if len(recent) >= self.max_requests:
            return False

        self.hits[key].append(now)
        return True

scan_limiter = InMemoryRateLimiter(max_requests=10, window_seconds=60)       # /api/verify
metrics_limiter = InMemoryRateLimiter(max_requests=10, window_seconds=60)    # /api/metrics
feedback_limiter = InMemoryRateLimiter(max_requests=10, window_seconds=60)   # /api/feedback

async def limit_scans(request: Request):
    ip = request.client.host or "unknown"
    if not scan_limiter.is_allowed(ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many scans from this IP. Please wait a bit.",
        )

async def limit_metrics(request: Request):
    ip = request.client.host or "unknown"
    if not metrics_limiter.is_allowed(ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many metric requests. Please slow down.",
        )

async def limit_feedback(request: Request):
    ip = request.client.host or "unknown"
    if not feedback_limiter.is_allowed(ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too much feedback from this IP. Please try again later.",
        )
