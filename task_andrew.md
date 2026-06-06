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

PHASE INSTRUCTIONS — CUSTOM PORTAL DOMAIN WIZARD

This feature lets firm owners point a custom subdomain (e.g. portal.smithcpa.com) to the JAMM PX client portal instead of app.jammpx.com/portal. No third-party API needed -- verification is done by DNS lookup using Python's socket module.

The CNAME target is: cname.vercel-dns.com
This is Vercel's CNAME target for custom domains. The firm adds a CNAME record pointing their subdomain to cname.vercel-dns.com.

Note: actual Vercel domain routing requires adding the domain in the Vercel dashboard separately. This wizard handles the firm-side setup and verification tracking. Document this in a comment in the backend file.

---

STEP 1 — MIGRATION

Current head: 0045_add_sending_domain_to_firms

Write a clean manual migration:

revision = '0046_add_portal_domain_to_firms'
down_revision = '0045_add_sending_domain_to_firms'

Add these columns to the firms table:
  portal_domain: VARCHAR(255), nullable=True
  portal_domain_verified: BOOLEAN, nullable=False, server_default='false'
  portal_domain_verification_token: VARCHAR(100), nullable=True

Run alembic upgrade head on the droplet. Confirm at new head.

---

STEP 2 — MODEL: app/models/firm.py

After the sending_domain_return_path_value field, add:

    portal_domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    portal_domain_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    portal_domain_verification_token: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

---

STEP 3 — SCHEMAS: app/schemas/firm.py

Add to FirmBase (and thus inherited by FirmOut):
  portal_domain: Optional[str] = None
  portal_domain_verified: bool = False

Do NOT expose portal_domain_verification_token in the schema -- internal only.

---

STEP 4 — BACKEND: app/api/portal_domain.py (new file)

Create app/api/portal_domain.py with three endpoints. Router prefix: /portal-domain. Tag: portal_domain. All endpoints require firm_owner role.

Add a comment at the top of the file explaining:
  # NOTE: This wizard handles the firm-side CNAME setup and verification tracking.
  # After a firm verifies their domain here, the domain must also be added to the
  # Vercel project dashboard (vercel.com) to enable actual routing. This is a
  # manual step performed by the JAMM PX team.

-- ENDPOINT 1: POST /portal-domain/register --

Input body: { "domain": str } -- the subdomain the firm wants to use (e.g. "portal.smithcpa.com")

Validate: domain must be non-empty, no spaces, no http:// prefix. Strip whitespace and lowercase. If it starts with http:// or https://, strip the protocol. If it contains a path (slash after the domain name), reject with 400. Domain must contain at least one dot.

Logic:
1. Generate a verification token: secrets.token_hex(16)
2. Save to firm:
   firm.portal_domain = domain
   firm.portal_domain_verified = False
   firm.portal_domain_verification_token = token
3. db.commit()
4. Fire behavioral event: "portal_domain.registered"
5. Return the CNAME record the firm needs to add plus the TXT verification record:

Return shape:
{
  "domain": str,
  "cname_host": str,  -- the subdomain they entered, e.g. "portal.smithcpa.com"
  "cname_value": "cname.vercel-dns.com",
  "txt_host": str,  -- "_jammpx-verify." + domain, e.g. "_jammpx-verify.portal.smithcpa.com"
  "txt_value": str,  -- the verification token
  "verified": false
}

-- ENDPOINT 2: POST /portal-domain/verify --

No input body. Uses the current firm's portal_domain and portal_domain_verification_token.

If firm has no portal_domain, return 400: "No domain registered. Register a domain first."

Verification logic:
1. Check CNAME: use socket.getaddrinfo(firm.portal_domain, None) to resolve the domain. If it resolves without error, the CNAME is likely set. Wrap in try/except -- if socket.gaierror, CNAME not yet propagated.
2. Check TXT record: use the dnspython library if available, otherwise skip TXT check and rely on CNAME only. Import dns.resolver inside a try/except ImportError -- if not available, set txt_verified = True (optimistic, rely on CNAME).
   TXT host to check: "_jammpx-verify." + firm.portal_domain
   Look for a TXT record whose value matches firm.portal_domain_verification_token.
3. If both CNAME resolves AND txt_verified: set firm.portal_domain_verified = True, db.commit(). Fire behavioral event: "portal_domain.verified".
4. Return:
{
  "domain": str,
  "verified": bool,
  "cname_resolved": bool,
  "txt_verified": bool,
  "message": "Domain verified successfully." or "DNS records not yet detected. Make sure both records are added and try again in a few minutes."
}

-- ENDPOINT 3: DELETE /portal-domain --

No input. Clears all portal domain fields on the firm. db.commit().
Fire behavioral event: "portal_domain.removed"
Return: { "message": "Portal domain removed." }

---

STEP 5 — REGISTER ROUTER: app/main.py

Import and register:
  from app.api.portal_domain import router as portal_domain_router
  app.include_router(portal_domain_router, prefix="/api/v1")

---

STEP 6 — FRONTEND: PortalDomainTab component

Create frontend/src/components/settings/PortalDomainTab.tsx

This tab has three states identical in structure to SendingDomainTab.tsx -- read that file for the exact patterns to replicate.

STATE A -- NO DOMAIN:
- Heading: "Custom Portal Domain"
- Description: "Give your clients a branded portal URL like portal.smithcpa.com instead of app.jammpx.com/portal. Requires adding two DNS records to your domain."
- Input field: subdomain, placeholder "portal.smithcpa.com"
- "Set Up Domain" button: brand color. POST /api/v1/portal-domain/register with { domain: inputValue }.
- On success: transition to STATE B.
- On error: show inline red error message.

STATE B -- DOMAIN REGISTERED, NOT VERIFIED:
- Heading: "Add these DNS records"
- Subtext: "Add both records to your domain registrar, then click Verify. DNS changes can take up to 48 hours to propagate."
- Two DNS record cards:
  1. CNAME record:
     - Type badge: "CNAME"
     - Host: the domain they entered (e.g. "portal.smithcpa.com")
     - Value: "cname.vercel-dns.com"
  2. TXT verification record:
     - Type badge: "TXT"
     - Host: "_jammpx-verify." + domain
     - Value: the verification token from the response
  Each card has copy buttons for Host and Value.
- "Verify DNS Records" button: brand color. POST /api/v1/portal-domain/verify.
- On verified=true: transition to STATE C.
- On verified=false: amber inline message "DNS records not yet detected. Try again in a few minutes."
- "Remove Domain" link below verify button. Calls DELETE /api/v1/portal-domain with confirmation. Returns to STATE A.

STATE C -- VERIFIED:
- Green checkmark + "{domain} is verified" heading
- Subtext: "Your client portal is accessible at https://{domain}/portal"
- Small note in muted text: "Contact JAMM PX support to complete routing setup."
- "Remove Domain" button: ghost/destructive. Confirmation required.

On mount: read firm data. If portal_domain is set and portal_domain_verified is true, start in STATE C. If portal_domain is set but not verified, fetch the DNS record details by calling GET /api/v1/portal-domain/records (see below) or reconstruct from stored firm data. Actually -- reconstruct from firm data on the FirmDetails type: portal_domain is available. The TXT host can be reconstructed as "_jammpx-verify." + portal_domain. For the TXT value (verification token), we need a way to retrieve it.

Add a fourth endpoint to app/api/portal_domain.py:

-- ENDPOINT 4: GET /portal-domain/records --

Returns the current domain setup details for the firm. No input.
If no portal_domain set, return 404.
Return:
{
  "domain": str,
  "cname_host": str,
  "cname_value": "cname.vercel-dns.com",
  "txt_host": str,
  "txt_value": str,  -- the verification token
  "verified": bool
}

Frontend uses this on mount when portal_domain is set but not verified, to restore STATE B with the correct DNS record values.

Copy button behavior: navigator.clipboard.writeText(). Show "Copied!" for 2 seconds.

Style: match SendingDomainTab.tsx exactly -- same card wrapper, same DNS record cards, same button styles.

---

STEP 7 — WIRE INTO SETTINGS PAGE: frontend/src/app/settings/page.tsx

1. Import PortalDomainTab
2. Add to TABS after 'sending_domain': { key: 'portal_domain', label: 'Portal Domain' }
3. Add canSeePortalDomain = isFirmOwner
4. Filter tab for non-owners
5. Render: {activeTab === 'portal_domain' && canSeePortalDomain && <PortalDomainTab />}

---

DO NOT skip the migration. This build requires alembic upgrade head on the droplet.

After completing confirm:
- Migration 0046 exists and applied
- Three new columns on firms table
- FirmOut includes portal_domain and portal_domain_verified
- app/api/portal_domain.py with four endpoints
- Router registered in main.py
- PortalDomainTab.tsx created with three states and copy buttons
- Settings page wired with Portal Domain tab