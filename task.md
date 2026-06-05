STANDING RULES — PERMANENT, NEVER OVERWRITE THIS BLOCK

- All models use UUID primary keys, firm_id FK, created_at and updated_at (timezone-aware)
- Every module has 4 Pydantic schemas: XBase, XCreate, XUpdate, XOut
- Routers are thin — no business logic ever
- All list endpoints paginated using PaginatedResponse[T]
- RBAC enforced at every endpoint
- Tenant isolation absolute — every query scoped to firm_id without exception
- Signed URLs only for all file access — never public S3 URLs, 1 hour maximum expiry
- Audit logging on every sensitive action
- Always use string names in relationship() to avoid circular imports
- Every generated file starts with a path comment
- Background tasks that touch the database must create their own SessionLocal() session in a try/finally block
- Never use native_enum=True for enums whose values contain dots or special characters
- Behavioral event log: fire-and-forget, never block main operation, service layer only, own session, never inherit request session

MIGRATION PROCEDURE — FOLLOW EVERY TIME

1. alembic current
2. alembic revision --autogenerate -m "description"
3. Read the generated file in full — if it contains tables beyond what you just added, delete it and write a clean manual migration
4. alembic upgrade head
5. alembic current — confirm at head

---

PHASE: Gmail OAuth Integration

WHAT WE ARE BUILDING
Two new routes added to app/api/integrations.py following the exact QBO pattern:
  GET /integrations/gmail/connect — returns a Google authorization URL, firm_owner only
  GET /integrations/gmail/callback — Google redirects here after user approves, no JWT required

A new service file: app/services/gmail_service.py
This handles the OAuth handshake, token exchange, token encryption/storage, and behavioral
event firing. Metadata-only scope — no email content ever read or stored.

STEP 1 — ADD TO app/core/config.py
Add these fields to the Settings class:
  GOOGLE_CLIENT_ID: str = ""
  GOOGLE_CLIENT_SECRET: str = ""
  GOOGLE_REDIRECT_URI: str = "https://api.jammpx.com/integrations/gmail/callback"

STEP 2 — CREATE app/services/gmail_service.py
Use google_auth_oauthlib.flow.Flow for the OAuth handshake.

Scopes (metadata only — never request mail.readonly or any content scope):
  https://www.googleapis.com/auth/gmail.metadata
  https://www.googleapis.com/auth/userinfo.email
  openid

GmailService class with these methods:

get_authorization_url(firm_id: UUID) -> str
  Build a Flow with the three scopes above.
  State parameter = str(firm_id) — same pattern as QBO.
  access_type="offline" to get a refresh token.
  Return the authorization URL.

handle_callback(code: str, state: str, db: Session) -> Integration
  Exchange code for tokens using the Flow.
  Extract the connected email address from the id_token or userinfo endpoint.
  Encrypt tokens using encrypt_token() from app/services/token_encryption.py.
  Upsert the Integration record:
    provider = "gmail"
    status = "connected"
    encrypted_access_token = encrypt_token(credentials.token)
    encrypted_refresh_token = encrypt_token(credentials.refresh_token) if present
    token_expires_at = credentials.expiry (timezone-aware)
    scopes = " ".join(credentials.scopes)
    external_account_id = the connected Gmail address
    connected_at = now()
  Fire behavioral event:
    event_type = "integration.connected"
    entity_type = "integration"
    metadata = {"provider": "gmail", "scopes": scopes_string}
  Write audit log — same pattern as QBO callback.
  Return the integration record.

STEP 3 — ADD ROUTES TO app/api/integrations.py
Add after the existing QBO routes and before the generic /{provider} routes.
Follow the exact same structure as the QBO connect and callback routes.

GET /integrations/gmail/connect
  Requires JWT + firm_owner.
  Get-or-create Integration record with provider="gmail".
  Call gmail_service.get_authorization_url(current_firm.id).
  Return {"authorization_url": url}.

GET /integrations/gmail/callback
  No JWT — Google calls this directly.
  Query params: code, state (firm_id as string).
  Call gmail_service.handle_callback(code=code, state=state, db=db).
  On success return {"status": "connected", "message": "Gmail connected successfully"}.
  On exception raise HTTP 400 with the error detail.

STEP 4 — INSTALL DEPENDENCIES
Add to requirements.txt:
  google-auth-oauthlib
  google-auth-httplib2
  google-api-python-client

MIGRATION
No migration needed. The integrations table already has all required fields.