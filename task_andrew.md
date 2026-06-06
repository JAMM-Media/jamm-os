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

# PHASE INSTRUCTIONS — WEEK 4: GMAIL BEHAVIORAL SIGNAL EXTRACTION

## Context
Gmail OAuth is already complete. The integration record exists with encrypted
access and refresh tokens stored on the Integration model. The scope granted
is gmail.metadata only — no email content is ever accessible or stored.
google-api-python-client and google-auth-oauthlib are already installed.
No migration needed. No frontend changes. One new service file, one new
cron job registration in main.py.

Security rules — non-negotiable:
- Never read, store, or log email subject lines, body content, or any
  message content field
- Never store sender or recipient email addresses beyond what is needed
  to match a client record — discard immediately after matching
- The behavioral event log entries contain only: signal type, computed
  numeric value, client_id, and firm_id — never raw email metadata
- If the Gmail API returns an error for any firm, log the error and
  continue to the next firm — never surface Gmail errors to users

---

## Pre-task checkpoint
git add -A
git commit -m "checkpoint before week 4 gmail signal extraction"

---

## VERIFY BEFORE STARTING
grep -n "encrypt_token\|decrypt_token" app/services/token_encryption.py
grep -n "GMAIL_SCOPES\|class GmailService\|gmail.metadata" app/services/gmail_service.py
grep -n "APScheduler\|add_job\|scheduler" app/main.py
Paste all three outputs before touching anything.

---

## Change 1: Create app/services/gmail_signals_service.py

Create this file from scratch. Path comment at top.

This service reads Gmail thread metadata for all firms with a connected
Gmail integration and fires behavioral events. It never reads message
content. It uses internalDate (millisecond timestamp on each message)
and thread structure only.

### Token refresh helper
Write a function get_fresh_credentials(integration: Integration) that:
- Decrypts the access token using decrypt_token from token_encryption
- Decrypts the refresh token using decrypt_token from token_encryption
- Builds a google.oauth2.credentials.Credentials object
- If token_expires_at is in the past or within 5 minutes of expiry,
  uses google.auth.transport.requests.Request() to refresh the token
- Returns the refreshed Credentials object
- Never logs the token values

### Signal extraction function
Write a function extract_gmail_signals(firm_id: UUID, db: Session) that:

1. Loads the Gmail integration for this firm
   - If not found or status != "connected", return immediately
   - Never raise — just return

2. Calls get_fresh_credentials(integration)
   - If this fails, log the error type only (not the token), return

3. Builds a Gmail API service using googleapiclient.discovery.build(
   "gmail", "v1", credentials=credentials)

4. Calls the Gmail API to list threads from the last 30 days:
   service.users().threads().list(
       userId="me",
       maxResults=100,
       q="after:" + thirty_days_ago_date_string
   ).execute()

5. For each thread returned:
   a. Call service.users().threads().get(
          userId="me",
          id=thread_id,
          format="metadata",
          metadataHeaders=["From", "To", "Date"]
      ).execute()
   b. Extract the list of messages in the thread
   c. From each message extract internalDate (divide by 1000 for seconds)
      and the From header value
   d. Determine if this thread involves a client:
      - Get all From addresses across all messages in the thread
      - Query Client where Client.email is in those addresses
        AND Client.firm_id == firm_id
      - If no client found: skip this thread, discard all addresses
      - If client found: use client.id for all event logging,
        discard the email addresses immediately
   e. Compute signals for this thread:
      - thread_depth: count of messages in the thread
      - last_contact_date: most recent internalDate in the thread
        converted to a date string
      - response_lag_hours: if there are 2 or more messages,
        find pairs where sender alternates (firm then client or
        client then firm) and compute average hours between pairs.
        If only 1 message, response_lag_hours is None.

6. After processing all threads, aggregate per client:
   - contact_frequency: count of distinct threads involving this client
     in the last 30 days
   - avg_response_lag_hours: average response lag across all threads
     for this client where lag was calculable
   - last_contact_date: most recent last_contact_date across all threads

7. Fire one behavioral event per client with signals found:
   Use log_event with a fresh SessionLocal() in try/finally.
   event_type: "gmail.signals_extracted"
   entity_type: "client"
   entity_id: client.id
   actor_type: "system"
   metadata:
     contact_frequency: int
     avg_response_lag_hours: float or None
     last_contact_date: string or None
     thread_count: int
   NEVER include email addresses in metadata.

8. Return a summary dict:
   firms_processed: 1
   clients_with_signals: count
   threads_processed: count
   errors: list of error type strings (never message content)

### Batch runner function
Write a function run_gmail_signals_for_all_firms() that:
- Creates its own SessionLocal() in try/finally
- Queries all Integration records where provider == "gmail"
  and status == "connected"
- Calls extract_gmail_signals(firm_id, db) for each
- Logs a summary of results
- Never raises — catches all exceptions per firm and continues
This is the function the cron job calls.

---

## Change 2: Register the cron job in app/main.py

Find where APScheduler jobs are registered in app/main.py.
Add one new job:

from app.services.gmail_signals_service import run_gmail_signals_for_all_firms

Register it to run daily at 6:00 AM UTC:
scheduler.add_job(
    run_gmail_signals_for_all_firms,
    "cron",
    hour=6,
    minute=0,
    id="gmail_signals_daily",
    replace_existing=True,
)

Place it alongside the other daily cron jobs already registered.

---

## Verify after all changes
grep -n "def extract_gmail_signals\|def run_gmail_signals\|def get_fresh_credentials" app/services/gmail_signals_service.py
grep -n "gmail_signals_daily\|run_gmail_signals" app/main.py
python -m py_compile app/services/gmail_signals_service.py
Compile must pass before deploying.

---

## Deploy sequence
git add -A
git commit -m "week 4 gmail behavioral signal extraction"
git push origin main
Then on the droplet:
git pull origin main
alembic upgrade head
alembic current
systemctl restart jammpx.service
journalctl -u jammpx.service -n 20 --no-pager