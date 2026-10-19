"""API key check and a small in-memory rate limiter."""
import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings


class ApiGuardMiddleware(BaseHTTPMiddleware):
    """Optional X-API-Key check plus a per-IP sliding window rate limit."""

    def __init__(self, app):
        super().__init__(app)
        self.hits: dict[str, deque] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS" or not request.url.path.startswith("/api"):
            return await call_next(request)

        if settings.API_KEY and request.headers.get("x-api-key") != settings.API_KEY:
            return JSONResponse({"detail": "Invalid or missing API key"}, status_code=401)

        limit = settings.RATE_LIMIT_PER_MINUTE
        if limit > 0:
            ip = request.client.host if request.client else "unknown"
            now = time.monotonic()
            window = self.hits[ip]
            while window and now - window[0] > 60:
                window.popleft()
            if len(window) >= limit:
                return JSONResponse(
                    {"detail": "Rate limit exceeded. Try again in a minute."},
                    status_code=429,
                    headers={"Retry-After": "60"},
                )
            window.append(now)

        return await call_next(request)
