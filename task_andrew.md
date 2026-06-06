STANDING RULES — PERMANENT — DO NOT SKIP

Architecture rules:
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

MIGRATION PROCEDURE — FOLLOW EVERY TIME

1. alembic current — confirm starting revision before touching anything
2. alembic revision --autogenerate -m "description"
3. Read the generated file in full — if it contains tables beyond what you just added, delete it and write a clean manual migration
4. alembic upgrade head
5. alembic current — confirm now at head
All models must be imported in migrations/env.py or autogenerate silently misses them.

---

PHASE INSTRUCTIONS — CUSTOM SENDING DOMAIN WIZARD

This feature lets firm owners send client emails from their own domain (e.g. noreply@smithcpa.com) instead of noreply@jammpx.com. It uses the Postmark Domains API with the account-level token.

---

STEP 1 — CONFIG: app/core/config.py

Add POSTMARK_ACCOUNT_TOKEN field after POSTMARK_API_KEY:
  POSTMARK_ACCOUNT_TOKEN: str = ""

---

STEP 2 — MIGRATION

Current head: 0044_add_entity_subtype_to_clients

Write a clean manual migration -- do NOT use autogenerate for this one since we are adding multiple columns to firms:

revision = '0045_add_sending_domain_to_firms'
down_revision = '0044_add_entity_subtype_to_clients'

Add these columns to the firms table:
  sending_domain: VARCHAR(255), nullable=True
  sending_domain_postmark_id: INTEGER, nullable=True
  sending_domain_verified: BOOLEAN, nullable=False, server_default='false'
  sending_domain_dkim_host: VARCHAR(500), nullable=True
  sending_domain_dkim_value: VARCHAR(1000), nullable=True
  sending_domain_return_path_host: VARCHAR(500), nullable=True
  sending_domain_return_path_value: VARCHAR(500), nullable=True

Run alembic upgrade head. Confirm at new head.

---

STEP 3 — MODEL: app/models/firm.py

Add these fields after the feature_flags column:

    sending_domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sending_domain_postmark_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sending_domain_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    sending_domain_dkim_host: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    sending_domain_dkim_value: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    sending_domain_return_path_host: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    sending_domain_return_path_value: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

---

STEP 4 — SCHEMAS: app/schemas/firm.py

Add these fields to FirmOut (and FirmBase if it exists):
  sending_domain: Optional[str] = None
  sending_domain_verified: bool = False
  sending_domain_dkim_host: Optional[str] = None
  sending_domain_dkim_value: Optional[str] = None
  sending_domain_return_path_host: Optional[str] = None
  sending_domain_return_path_value: Optional[str] = None

Do NOT expose sending_domain_postmark_id in the schema -- internal only.

---

STEP 5 — BACKEND: app/api/sending_domain.py (new file)

Create app/api/sending_domain.py with three endpoints. Router prefix: /sending-domain. Tag: sending_domain. All endpoints require firm_owner role.

The Postmark Account API base URL is: https://api.postmarkapp.com
Account-level requests use header: X-Postmark-Account-Token: {POSTMARK_ACCOUNT_TOKEN}

-- ENDPOINT 1: POST /sending-domain/register --

Input body: { "domain": str } -- the domain the firm wants to send from (e.g. "smithcpa.com")

Validate: domain must be a non-empty string, no spaces, no http:// prefix. Strip whitespace and lowercase. If it starts with "http://" or "https://", strip the protocol. If it contains a path (slash after the domain), reject with 400.

Logic:
1. Call Postmark Domains API to create the domain:
   POST https://api.postmarkapp.com/domains
   Headers: X-Postmark-Account-Token, Content-Type: application/json, Accept: application/json
   Body: { "Name": domain }
2. Parse response. Postmark returns:
   { "ID": int, "Name": str, "DKIMVerified": bool, "ReturnPathDomain": str, "ReturnPathDomainCNAMEValue": str, "DKIMPendingHost": str, "DKIMPendingTextValue": str, ... }
   Use DKIMPendingHost and DKIMPendingTextValue for the DKIM records (these are the ones to add before verification).
   Use ReturnPathDomain as the return path host and ReturnPathDomainCNAMEValue as the return path value.
3. Save to firm:
   firm.sending_domain = domain
   firm.sending_domain_postmark_id = response["ID"]
   firm.sending_domain_verified = False
   firm.sending_domain_dkim_host = response["DKIMPendingHost"]
   firm.sending_domain_dkim_value = response["DKIMPendingTextValue"]
   firm.sending_domain_return_path_host = response["ReturnPathDomain"]
   firm.sending_domain_return_path_value = response["ReturnPathDomainCNAMEValue"]
4. db.commit()
5. Fire behavioral event: "sending_domain.registered"
6. Return the DNS records the firm needs to add.

If Postmark returns an error (domain already registered, invalid domain, etc.), return 400 with Postmark's error message.

Return shape:
{
  "domain": str,
  "dkim_host": str,
  "dkim_value": str,
  "return_path_host": str,
  "return_path_value": str,
  "verified": bool
}

-- ENDPOINT 2: POST /sending-domain/verify --

No input body. Uses the current firm's sending_domain_postmark_id.

If firm has no sending_domain or no sending_domain_postmark_id, return 400: "No domain registered. Register a domain first."

Logic:
1. Call Postmark to trigger verification:
   POST https://api.postmarkapp.com/domains/{sending_domain_postmark_id}/verifyDkim
   Headers: X-Postmark-Account-Token, Accept: application/json
2. Also call:
   POST https://api.postmarkapp.com/domains/{sending_domain_postmark_id}/verifyReturnPath
3. Then fetch domain status:
   GET https://api.postmarkapp.com/domains/{sending_domain_postmark_id}
4. Check response: if DKIMVerified is True and ReturnPathDomainVerified is True, mark firm.sending_domain_verified = True
5. db.commit()
6. Fire behavioral event: "sending_domain.verified" if newly verified
7. Return:
{
  "domain": str,
  "verified": bool,
  "dkim_verified": bool,
  "return_path_verified": bool,
  "message": "Domain verified successfully." or "DNS records not yet detected. Make sure the records are added and try again in a few minutes."
}

-- ENDPOINT 3: DELETE /sending-domain --

No input. Removes the sending domain from the firm.

If firm has a sending_domain_postmark_id, call Postmark to delete the domain:
  DELETE https://api.postmarkapp.com/domains/{sending_domain_postmark_id}
  Headers: X-Postmark-Account-Token

Then clear all sending domain fields on the firm. db.commit().
Fire behavioral event: "sending_domain.removed"
Return: { "message": "Sending domain removed." }

---

STEP 6 — REGISTER ROUTER: app/main.py

Import and register:
  from app.api.sending_domain import router as sending_domain_router
  app.include_router(sending_domain_router, prefix="/api/v1")

---

STEP 7 — EMAIL SERVICE UPDATE: app/services/email_service.py

Update EmailService._send() to use the firm's custom sending domain when it is verified.

The _send method currently hardcodes "noreply@jammpx.com". Add an optional parameter:
  sending_domain: str | None = None

When sending_domain is provided and non-empty, use:
  "From": f"{effective_name} <noreply@{sending_domain}>"
When sending_domain is None or empty, keep:
  "From": f"{effective_name} <noreply@jammpx.com>"

Also update get_firm_email_settings to return the sending domain:
  return {
    "reply_to": settings.get("email_reply_to") or None,
    "display_name": settings.get("email_display_name") or None,
    "sending_domain": firm.sending_domain if firm.sending_domain_verified else None,
  }

Update all callers of _send that pass email_settings to also pass sending_domain=email_settings.get("sending_domain"). Search for all calls to EmailService._send() and EmailService._send_raw() and add the sending_domain parameter where email_settings is already being read.

---

STEP 8 — FRONTEND: SendingDomainTab component

Create frontend/src/components/settings/SendingDomainTab.tsx

This tab has three states:

STATE A -- NO DOMAIN (default when sending_domain is null):
- Heading: "Custom Sending Domain"
- Description: "Send client emails from your own domain instead of noreply@jammpx.com. Requires adding two DNS records to your domain."
- Input field: domain name, placeholder "smithcpa.com", no http:// prefix
- "Register Domain" button: brand color. On click: POST /api/v1/sending-domain/register with { domain: inputValue }. Show loading state.
- On success: transition to STATE B with the DNS records from the response.
- On error: show inline red error message.

STATE B -- DOMAIN REGISTERED, NOT VERIFIED:
- Heading: "Add these DNS records"
- Subtext: "Add both records to your domain registrar (GoDaddy, Namecheap, Cloudflare, etc.), then click Verify. DNS changes can take up to 48 hours to propagate."
- Two DNS record cards, each showing:
  - Record type badge: "TXT" for DKIM, "CNAME" for Return-Path
  - Host field with copy button
  - Value field with copy button (truncated with ellipsis if long, full value in clipboard)
- "Verify DNS Records" button: brand color. On click: POST /api/v1/sending-domain/verify. Show loading state.
- On success verified=true: transition to STATE C.
- On success verified=false: show amber inline message "DNS records not yet detected. Try again in a few minutes."
- "Remove Domain" link: small muted text below the verify button. On click: DELETE /api/v1/sending-domain with confirmation. Returns to STATE A.

STATE C -- VERIFIED:
- Green checkmark + "smithcpa.com is verified" heading
- Subtext: "Client emails will now be sent from noreply@smithcpa.com"
- "Remove Domain" button: ghost/destructive style. Confirmation required before DELETE call.

On mount: read firm data from the existing useFetch for firm details. If sending_domain is set and sending_domain_verified is true, start in STATE C. If sending_domain is set but not verified, start in STATE B (pre-populate DNS records from firm data). If no sending_domain, start in STATE A.

Copy button behavior: use navigator.clipboard.writeText(). Show a brief "Copied!" tooltip or text change for 2 seconds.

Style: match existing settings tab cards exactly -- same card wrapper, same heading sizes, same input styles as other settings tabs.

---

STEP 9 — WIRE INTO SETTINGS PAGE: frontend/src/app/settings/page.tsx

1. Import SendingDomainTab
2. Add to TABS after 'portal_branding': { key: 'sending_domain', label: 'Email Domain' }
3. Add canSeeSendingDomain = isFirmOwner
4. Filter tab for non-owners
5. Render: {activeTab === 'sending_domain' && canSeeSendingDomain && <SendingDomainTab />}

---

DO NOT skip the migration. This build requires alembic upgrade head on the droplet.

After completing confirm:
- POSTMARK_ACCOUNT_TOKEN in config.py
- Migration 0045 exists and applied
- Seven new columns on firms table
- FirmOut schema includes sending domain fields
- app/api/sending_domain.py with three endpoints
- Router registered in main.py
- EmailService._send updated to accept sending_domain parameter
- get_firm_email_settings returns sending_domain when verified
- SendingDomainTab.tsx created with three states
- Settings page wired with Email Domain tab