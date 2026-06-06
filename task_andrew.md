# STANDING RULES — PERMANENT, NEVER OVERWRITE THIS BLOCK
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
- Background tasks that touch the database must create their own SessionLocal() in a try/finally block — never pass the request db session into a background task
- Never use native_enum=True for enums whose values contain dots or special characters — always use sa.Enum(MyEnum, native_enum=False)
- Behavioral event log: fire-and-forget only, never block the main operation, service layer only, own session, never inherit the request session
- Always use SQLAlchemy 2.0 Mapped[] syntax — never Column() style
- Always use Pydantic v2 — model_dump() and field_validator() only, never .dict() or @validator
- DATABASE_URL uses postgresql+psycopg:// dialect prefix — never plain postgresql://
- Never use && to chain commands in PowerShell — separate every command onto its own line
- Never use em dashes anywhere in any string, copy, or comment

---

# MIGRATION PROCEDURE — FOLLOW EVERY TIME
1. alembic current — confirm starting revision before touching anything
2. alembic revision --autogenerate -m "description"
3. Read the generated file in full — if it contains tables beyond what you just added, delete it and write a clean manual migration
4. alembic upgrade head
5. alembic current — confirm now at head
All models must be imported in migrations/env.py or autogenerate silently misses them.

---

# PHASE INSTRUCTIONS — OUTLOOK OAUTH + SIGNAL EXTRACTION

## Context
Gmail OAuth and signal extraction are fully built and live.
The Outlook build follows the exact same pattern using Microsoft Graph API
instead of Google's Gmail API.
The Microsoft env vars are already in the .env file:
MICROSOFT_CLIENT_ID, MICROSOFT_CLIENT_SECRET, MICROSOFT_TENANT_ID,
MICROSOFT_REDIRECT_URI=https://api.jammpx.com/integrations/outlook/callback

The msal package is required. Check if it is installed before writing any code:
pip show msal
If not installed, add it to requirements.txt and note it must be installed on
the droplet during deploy.

No migration needed — the Integration model already supports any provider string.
No frontend changes needed — the connect button pattern already exists for Gmail.

Security rules — identical to Gmail, non-negotiable:
- Scope is Mail.Read only — metadata and headers only, never message body content
- Never store, log, or include email addresses in behavioral event metadata
- Email addresses used as lookup keys only — discard after matching client
- Raw message content never read, never stored, never logged

---

## Pre-task checkpoint
git add -A
git commit -m "checkpoint before outlook oauth build"

---

## VERIFY BEFORE STARTING
grep -n "GOOGLE_CLIENT_ID\|GOOGLE_CLIENT_SECRET\|GOOGLE_REDIRECT_URI" app/core/config.py
grep -n "class GmailService\|GMAIL_SCOPES\|handle_callback\|get_authorization_url" app/services/gmail_service.py
grep -n "gmail/connect\|gmail/callback" app/api/integrations.py
Paste all three outputs before touching anything.

---

## Change 1: Add Microsoft config fields to app/core/config.py

Find the Settings class in app/core/config.py.
Find where GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI are defined.
Add these four fields immediately after the Google fields:

    MICROSOFT_CLIENT_ID: str = ""
    MICROSOFT_CLIENT_SECRET: str = ""
    MICROSOFT_TENANT_ID: str = ""
    MICROSOFT_REDIRECT_URI: str = "https://api.jammpx.com/integrations/outlook/callback"

---

## Change 2: Check msal installation

Run: pip show msal
If msal is installed: note the version, proceed to Change 3.
If msal is not installed:
- Add msal to requirements.txt on its own line
- Note that pip install msal must be run on the droplet during deploy

---

## Change 3: Create app/services/outlook_service.py

Mirror the structure of app/services/gmail_service.py exactly.
Path comment at top.

OUTLOOK_SCOPES:
- "https://graph.microsoft.com/Mail.Read"
- "https://graph.microsoft.com/User.Read"
- "offline_access"

OUTLOOK_PROVIDER = "outlook"

class OutlookService:

### get_authorization_url(self, firm_id: UUID) -> str
Use msal.ConfidentialClientApplication:
    app = msal.ConfidentialClientApplication(
        client_id=settings.MICROSOFT_CLIENT_ID,
        client_credential=settings.MICROSOFT_CLIENT_SECRET,
        authority=f"https://login.microsoftonline.com/{settings.MICROSOFT_TENANT_ID}"
    )
    result = app.get_authorization_request_url(
        scopes=OUTLOOK_SCOPES,
        state=str(firm_id),
        redirect_uri=settings.MICROSOFT_REDIRECT_URI,
    )
    return result

### handle_callback(self, code: str, state: str, db: Session) -> Integration
Parse firm_id from state.
Load or create Integration record for this firm with provider="outlook".
Exchange code for tokens:
    app = msal.ConfidentialClientApplication(...)
    result = app.acquire_token_by_authorization_code(
        code=code,
        scopes=OUTLOOK_SCOPES,
        redirect_uri=settings.MICROSOFT_REDIRECT_URI,
    )
If result contains "error": raise ValueError with the error description.
Extract from result:
- access_token: result["access_token"]
- refresh_token: result.get("refresh_token")
- expires_in: result.get("expires_in", 3600)
- token_expiry: datetime.now(timezone.utc) + timedelta(seconds=expires_in)

Get the connected email address by calling Microsoft Graph:
    resp = http_requests.get(
        "https://graph.microsoft.com/v1.0/me",
        headers={"Authorization": f"Bearer {result['access_token']}"},
        timeout=10,
    )
    email = resp.json().get("mail") or resp.json().get("userPrincipalName")

Store on Integration:
- encrypted_access_token: encrypt_token(access_token)
- encrypted_refresh_token: encrypt_token(refresh_token) if refresh_token else unchanged
- token_expires_at: token_expiry
- scopes: " ".join(OUTLOOK_SCOPES)
- external_account_id: email
- status: "connected"
- connected_at: datetime.now(timezone.utc)

Fire behavioral event and write audit log — same pattern as gmail_service.py.
Use provider="outlook" in all metadata.
Return the integration.

---

## Change 4: Add Outlook connect and callback endpoints to app/api/integrations.py

Mirror the Gmail endpoints exactly. Find:
GET /integrations/gmail/connect
GET /integrations/gmail/callback

Add immediately after them:

GET /integrations/outlook/connect
- Same pattern as gmail/connect
- Uses OutlookService().get_authorization_url(current_firm.id)
- Checks for existing integration with provider="outlook"

GET /integrations/outlook/callback
- Same pattern as gmail/callback
- Uses OutlookService().handle_callback(code=code, state=state, db=db)
- Returns {"status": "connected", "message": "Outlook connected successfully"}

Import OutlookService at the top of the file alongside GmailService.

---

## Change 5: Create app/services/outlook_signals_service.py

Mirror app/services/gmail_signals_service.py exactly.
Path comment at top.

Use Microsoft Graph API instead of Gmail API.
No google packages needed — use http_requests directly with the access token.

### get_fresh_outlook_credentials(integration: Integration) -> str
Returns a valid access token string (not a credentials object).
- Decrypt access token using decrypt_token
- If token_expires_at is None or within 5 minutes of expiry:
  Use msal to refresh:
      app = msal.ConfidentialClientApplication(...)
      result = app.acquire_token_by_refresh_token(
          refresh_token=decrypt_token(integration.encrypted_refresh_token),
          scopes=OUTLOOK_SCOPES,
      )
  If refresh succeeds: return result["access_token"]
  If refresh fails: raise ValueError("Token refresh failed")
- Otherwise: return decrypted access token
- Never log the token value

### extract_outlook_signals(firm_id: UUID, db: Session) -> dict
Same structure as extract_gmail_signals.

1. Load outlook integration, check status == "connected", return early if not.

2. Get fresh access token via get_fresh_outlook_credentials.

3. Fetch messages from last 30 days using Microsoft Graph:
   GET https://graph.microsoft.com/v1.0/me/messages
   Query params:
     $select=id,conversationId,from,receivedDateTime,sender
     $filter=receivedDateTime ge {thirty_days_ago_iso}
     $top=100
   Headers: Authorization: Bearer {access_token}
   Never request body content. Never request subject lines.

4. Group messages by conversationId — this is the thread equivalent.

5. For each conversation group:
   a. Extract from address from each message:
      message["from"]["emailAddress"]["address"].lower().strip()
   b. Match to a client by email address scoped to firm_id — same logic as Gmail.
   c. If no client found: skip, discard addresses.
   d. Compute signals:
      - thread_depth: message count in conversation
      - last_contact_date: max receivedDateTime converted to date string
      - response_lag_hours: same alternating sender logic as Gmail version,
        using receivedDateTime parsed as ISO datetime for timestamps

6. Aggregate per client and fire behavioral events:
   event_type: "outlook.signals_extracted"
   metadata: contact_frequency, avg_response_lag_hours,
             last_contact_date, thread_count
   NEVER include email addresses in metadata.

7. Return summary dict: firms_processed, clients_with_signals,
   threads_processed, errors.

### run_outlook_signals_for_all_firms()
Identical structure to run_gmail_signals_for_all_firms.
Queries integrations where provider == "outlook" and status == "connected".
Never raises. Own SessionLocal in try/finally.

---

## Change 6: Register Outlook signals cron job in app/main.py

Find where gmail_signals_daily is registered.
Add immediately after it:

from app.services.outlook_signals_service import run_outlook_signals_for_all_firms

scheduler.add_job(
    run_outlook_signals_for_all_firms,
    "cron",
    hour=6,
    minute=15,
    id="outlook_signals_daily",
    replace_existing=True,
)

15 minutes after Gmail so they do not run simultaneously.

---

## Verify after all changes
grep -n "MICROSOFT_CLIENT_ID\|MICROSOFT_CLIENT_SECRET\|MICROSOFT_TENANT_ID" app/core/config.py
grep -n "class OutlookService\|OUTLOOK_SCOPES\|handle_callback" app/services/outlook_service.py
grep -n "outlook/connect\|outlook/callback" app/api/integrations.py
grep -n "def extract_outlook_signals\|def run_outlook_signals\|def get_fresh_outlook_credentials" app/services/outlook_signals_service.py
grep -n "outlook_signals_daily\|run_outlook_signals" app/main.py
python -m py_compile app/services/outlook_service.py
python -m py_compile app/services/outlook_signals_service.py
python -m py_compile app/api/integrations.py
All three compiles must pass before deploying.

---

## Deploy sequence
git add -A
git commit -m "outlook oauth and signal extraction"
git push origin main
Then on the droplet:
pip install msal --quiet (only if msal was not already installed)
git pull origin main
alembic upgrade head
alembic current
systemctl restart jammpx.service
journalctl -u jammpx.service -n 20 --no-pager