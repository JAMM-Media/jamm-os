# tests/test_request_context.py

import asyncio
import uuid
import pytest
from jose import jwt

from app.core.request_context import (
    get_request_id,
    get_session_id,
    set_request_id,
    set_session_id,
)
from app.core.context_middleware import RequestContextMiddleware
from app.core.config import get_settings

settings = get_settings()


# --------------------------------------------------------------------------- #
# Test 1: defaults are None in a fresh context
# --------------------------------------------------------------------------- #
def test_context_vars_default_none():
    import contextvars
    ctx = contextvars.copy_context()

    def _check():
        assert get_request_id() is None
        assert get_session_id() is None

    ctx.run(_check)


# --------------------------------------------------------------------------- #
# Test 2: set_request_id / get_request_id round-trip
# --------------------------------------------------------------------------- #
def test_set_and_get_request_id():
    set_request_id("abc")
    assert get_request_id() == "abc"


# --------------------------------------------------------------------------- #
# Test 3: set_session_id / get_session_id round-trip
# --------------------------------------------------------------------------- #
def test_set_and_get_session_id():
    set_session_id("xyz")
    assert get_session_id() == "xyz"


# --------------------------------------------------------------------------- #
# Helpers for ASGI tests
# --------------------------------------------------------------------------- #

def _make_http_scope(headers=None):
    return {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": headers or [],
        "query_string": b"",
    }


async def _null_receive():
    pass


async def _null_send(message):
    pass


# --------------------------------------------------------------------------- #
# Test 4: middleware sets a valid request_id; session_id is None (no auth)
# --------------------------------------------------------------------------- #
def test_middleware_sets_request_id():
    holder = {}

    async def capture_app(scope, receive, send):
        holder["request_id"] = get_request_id()
        holder["session_id"] = get_session_id()

    async def run():
        middleware = RequestContextMiddleware(capture_app)
        scope = _make_http_scope()
        await middleware(scope, _null_receive, _null_send)

    asyncio.run(run())

    assert holder["request_id"] is not None
    # Must be a valid UUID string
    uuid.UUID(holder["request_id"])
    assert holder["session_id"] is None


# --------------------------------------------------------------------------- #
# Test 5: middleware reads jti from a valid bearer token
# --------------------------------------------------------------------------- #
def test_middleware_reads_jti_from_token():
    known_jti = str(uuid.uuid4())
    token = jwt.encode(
        {"sub": "user-123", "jti": known_jti},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )

    holder = {}

    async def capture_app(scope, receive, send):
        holder["session_id"] = get_session_id()

    async def run():
        middleware = RequestContextMiddleware(capture_app)
        scope = _make_http_scope(
            headers=[(b"authorization", f"Bearer {token}".encode())]
        )
        await middleware(scope, _null_receive, _null_send)

    asyncio.run(run())

    assert holder["session_id"] == known_jti


# --------------------------------------------------------------------------- #
# Test 6: malformed token does not raise; session_id is None
# --------------------------------------------------------------------------- #
def test_middleware_handles_malformed_token():
    holder = {}

    async def capture_app(scope, receive, send):
        holder["session_id"] = get_session_id()

    async def run():
        middleware = RequestContextMiddleware(capture_app)
        scope = _make_http_scope(
            headers=[(b"authorization", b"Bearer garbage")]
        )
        await middleware(scope, _null_receive, _null_send)

    asyncio.run(run())

    assert holder["session_id"] is None
