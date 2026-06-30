# app/core/context_middleware.py

import uuid
from jose import jwt

from app.core.request_context import set_request_id, set_session_id


class RequestContextMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        set_request_id(str(uuid.uuid4()))

        session_id = None
        try:
            headers = dict(scope.get("headers") or [])
            auth = headers.get(b"authorization")
            if auth:
                decoded = auth.decode("latin-1")
                if decoded.lower().startswith("bearer "):
                    token = decoded[7:]
                    # Decode WITHOUT verification -- we only need the jti for
                    # correlation. Real auth is enforced by the route dependencies.
                    claims = jwt.get_unverified_claims(token)
                    session_id = claims.get("jti")
        except Exception:
            session_id = None

        set_session_id(session_id)

        await self.app(scope, receive, send)
