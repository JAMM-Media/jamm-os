# app/core/middleware.py

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
    "img-src 'self' data: https:",
    "font-src 'self' data:",
    "connect-src 'self'",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "upgrade-insecure-requests",
])

_PERMISSIONS_POLICY = (
    "camera=(), microphone=(), geolocation=(), payment=(), "
    "usb=(), interest-cohort=()"
)


_CSP_EXEMPT_PATHS = {"/docs", "/openapi.json"}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = _PERMISSIONS_POLICY
        if request.url.path not in _CSP_EXEMPT_PATHS:
            response.headers["Content-Security-Policy"] = _CSP
        response.headers["X-XSS-Protection"] = "1; mode=block"

        return response
