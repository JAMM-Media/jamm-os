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

PHASE: QBO Deep Link Endpoint

WHAT WE ARE BUILDING
One new endpoint added to app/api/integrations.py:
  GET /integrations/quickbooks/deep-link/client/{client_id}

Returns a direct URL that opens the client's record in QuickBooks Online.
No redirect — returns the URL as JSON so the frontend can open it in a new tab.

STEP 1 — ADD ENDPOINT TO app/api/integrations.py
Add after the existing QBO routes and before the Gmail routes.
Must be defined before the generic /{provider} routes to avoid shadowing.

GET /integrations/quickbooks/deep-link/client/{client_id}
  Requires JWT + manager_or_above role.
  Verify the client belongs to current_firm (tenant isolation).
  Look up the client's quickbooks_customer_id field.
  If quickbooks_customer_id is None: return 404 with detail
  "This client is not linked to a QuickBooks customer."
  Look up the QBO integration for this firm.
  If not connected: return 400 with detail "QuickBooks is not connected."
  Build the deep link URL:
    https://app.qbo.intuit.com/app/customerdetail?nameId={quickbooks_customer_id}
  Return {"url": deep_link_url, "quickbooks_customer_id": quickbooks_customer_id}
  Fire behavioral event:
    event_type = "integration.qbo_deep_link_opened"
    entity_type = "client"
    entity_id = client_id
    metadata = {"quickbooks_customer_id": quickbooks_customer_id}

MIGRATION
No migration needed.