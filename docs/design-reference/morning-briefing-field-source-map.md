# docs/design-reference/morning-briefing-field-source-map.md

Investigation date: 2026-09-25
Files read: app/models/surface_item.py, app/services/surface_item_service.py,
app/services/surface_generators.py, app/schemas/surface_item.py,
app/api/surface_items.py, app/models/invoice.py, app/models/engagement_member.py,
app/models/document.py, app/models/behavioral_event.py, app/models/client.py,
app/models/engagement.py; grep of app/models/firm.py for surface_narrative.

---

## Section 1: Ten Field Source Map

All seven generators write `client_id` and at least one entity identifier to
`SurfaceItem.payload` at generation time. The payload is already persisted when
a briefing row is served. The table below maps each of the ten fields to its
real source, join path, and computation type.

---

### 1. CLIENT

Real source: `clients.name`, `clients.id`
Real column: `Client.name` (String 200, nullable=False)
Join path:
  `payload["client_id"]` as UUID ->
  `SELECT name FROM clients WHERE id = :client_id AND firm_id = :firm_id`

Computation type: Directly stored. `Client.name` is read as-is.

Coverage: All seven generators write `client_id` to payload. Confirmed line by line:
- `invoice_overdue`: `payload["client_id"] = str(invoice.client_id)`
- `irs_auth_expiring`: `payload["client_id"] = str(auth.client_id)`
- `signature_stalled/declined/expired`: `payload["client_id"] = str(envelope.client_id)`
- `deadline_with_blockers`: `payload["client_id"] = str(engagement.client_id)`
- `work_unbilled`: `payload["client_id"] = str(engagement.client_id)`

Already computed inline on every GET /briefing call by `_attach_client_names`
in `surface_item_service.py` (batch query, one roundtrip for all rows). Result
is set as `row.client_name` and serialized in `SurfaceItemOut.client_name`.
No additional work needed for this field.

---

### 2. ENGAGEMENT

Real source: `engagements.name`, `engagements.id`, `engagements.status`
Real column: `Engagement.name` (String 200)

Coverage splits by item type:

**deadline_with_blockers, work_unbilled:**
`payload["engagement_id"]` and `payload["engagement_name"]` are directly
written to payload at generation time. No join required to get the name.
`Engagement.name` is embedded verbatim in `payload["engagement_name"]`.

**signature_stalled, signature_declined, signature_expired:**
`payload["engagement_id"]` is written (may be null when the envelope carries no
engagement). If non-null:
  `payload["engagement_id"]` as UUID ->
  `SELECT name FROM engagements WHERE id = :id AND firm_id = :firm_id`

**invoice_overdue:**
GAP: the generator does NOT write `engagement_id` to payload. Payload contains
only `invoice_id`, `invoice_number`, `client_id`, `balance`, `days_overdue`.
To get the engagement: `payload["invoice_id"]` -> `Invoice.engagement_id`
(nullable) -> `Engagement.name`. Two-hop join; engagement may be null if the
invoice was not created against an engagement.

**irs_auth_expiring:**
GAP: no `engagement_id` in payload. `IrsAuthorization` model was not in the
read set for this task. Whether IrsAuthorization carries an `engagement_id`
column is an open question (see Section 6).

---

### 3. ASSIGNED STAFF

Real source: `engagement_members.user_id`, `users.full_name` (or equivalent)
Real model: `EngagementMember` (engagement_id, user_id, is_administrator, firm_id)

Join path (for items with engagement_id in payload):
  `payload["engagement_id"]` as UUID ->
  `SELECT user_id FROM engagement_members WHERE engagement_id = :id AND firm_id = :firm_id` ->
  `SELECT full_name FROM users WHERE id = :user_id`

Coverage:
- `deadline_with_blockers`, `work_unbilled`: `payload["engagement_id"]` present. Direct.
- `signature_stalled/declined/expired`: `payload["engagement_id"]` present when not null.
- `invoice_overdue`: GAP. No engagement_id in payload. To reach EngagementMember
  requires `Invoice.engagement_id` first (nullable, two-hop). An alternative proxy
  for this item type only: `Invoice.created_by` (FK to `users.id`, nullable) is a
  real stored column identifying who created the invoice. That is one staff ID
  without any hop through engagement_members, but it is the creator, not the
  assigned preparer.
- `irs_auth_expiring`: GAP. No engagement in payload; no path to EngagementMember
  without knowing whether IrsAuthorization carries engagement_id (open question).

Computation type: Directly stored (`EngagementMember.user_id`, `User.full_name` are
real columns read as-is). The association itself is a real persisted fact.

---

### 4. INVOICE / BALANCE

Real source: `invoices.total_amount`, `invoices.amount_paid`, `invoices.invoice_number`

For `invoice_overdue` only:
`payload["balance"]` is written at generation time.
Calculation: `Invoice.total_amount - Invoice.amount_paid`
  where total_amount is Numeric(10,2) and amount_paid is Numeric(10,2).
`payload["invoice_number"]` is also written directly from `Invoice.invoice_number`.

Computation type: Deterministically calculated at generation time, stored in payload.
No join required to read balance or invoice_number for overdue items.

For other item types: No invoice identifier is in payload. Applicable only to
`invoice_overdue`. If an invoice total is needed for engagement-type items
(deadline_with_blockers, work_unbilled), a separate query on Invoice.engagement_id
is required and may return multiple invoice rows.

---

### 5. DAYS OVERDUE

Real source: `invoices.due_date`, compared against generation-time date

For `invoice_overdue` only:
`payload["days_overdue"]` is written at generation time.
Calculation: `(date.today() - invoice.due_date).days` at the moment the daily job runs.

Computation type: Deterministically calculated at generation time, stored in payload.
No join required for this field on overdue items.

Analogous fields on other item types (also stored in payload at generation time):
- `irs_auth_expiring`: `payload["days_to_expiry"]`
- `signature_stalled`: `payload["days_waiting"]`
- `signature_declined/expired`: `payload["days_since"]`
- `deadline_with_blockers`: `payload["days_remaining"]`
- `work_unbilled`: `payload["days_since_completion"]`

All of these are deterministically calculated and stored in payload. No joins needed
to display the time-elapsed number for any item type.

---

### 6. CURRENT WORKFLOW STATUS

Real source: `invoices.status` (for invoice items), `engagements.status` (for
engagement items), `irs_authorizations.status` (for irs items)

For `invoice_overdue`:
Real column: `Invoice.status` (InvoiceStatus enum: values include at minimum
draft, void; overdue and paid are referenced in clear conditions and generator
logic). Read as-is.
Join: `payload["invoice_id"]` -> `SELECT status FROM invoices WHERE id = :id AND firm_id = :firm_id`

For `deadline_with_blockers`, `work_unbilled`:
Real column: `Engagement.status` (str: "planning", "active", "completed", "archived"
and others -- multiple values referenced in generator conditions).
Join: `payload["engagement_id"]` -> `SELECT status FROM engagements WHERE id = :id AND firm_id = :firm_id`

For `signature_stalled/declined/expired`:
Real column: `SignatureEnvelope.status` (str: "sent", "signed", "declined", "expired",
others documented in generator module vocabulary note).
Join: `payload["envelope_id"]` -> `SELECT status FROM signature_envelopes WHERE id = :id AND firm_id = :firm_id`

For `irs_auth_expiring`:
Real column: `IrsAuthorization.status` (str: "active", "superseded" confirmed in
clear condition; others not confirmed from read set).
Join: `payload["authorization_id"]` -> `SELECT status FROM irs_authorizations WHERE id = :id AND firm_id = :firm_id`

Computation type: Directly stored. Status columns are real persisted values read as-is.
No computation.

GAP ACROSS ALL TYPES: None of the seven generators write the entity's status column
to payload. All item types require a join to get current workflow status. The payload
contains the status at the time the generator ran (implicitly -- the generator's WHERE
clause screened on it), but it is never stored as a payload field.

---

### 7. ISSUED DATE

Real source and join path by item type:

**invoice_overdue:**
Real column: `Invoice.sent_at` (DateTime nullable). The date the invoice was sent
to the client.
Join: `payload["invoice_id"]` -> `SELECT sent_at FROM invoices WHERE id = :id AND firm_id = :firm_id`
Computation type: Directly stored. `Invoice.sent_at` is set by the invoice send path.
NOT currently in payload. Requires a join.

**signature_stalled/declined/expired:**
Real column: `SignatureEnvelope.sent_at` (DateTime nullable). The date the envelope
was dispatched.
Join: `payload["envelope_id"]` -> `SELECT sent_at FROM signature_envelopes WHERE id = :id AND firm_id = :firm_id`
Computation type: Directly stored. NOT in payload.

**irs_auth_expiring:**
OPEN QUESTION: "Issued date" for an IRS authorization is not confirmed from the
models read. The IrsAuthorization model was not in the read set. The payload
contains `valid_until` (the expiry date, as an ISO string). A corresponding
"issued on" column may exist but cannot be confirmed without reading that model.

**deadline_with_blockers:**
OPEN QUESTION: "Issued date" meaning is unclear for an engagement deadline. The
payload contains `payload["deadline"]` (the filing deadline as ISO date). Whether
"issued date" means `Engagement.start_date`, `Engagement.created_at`, or the
deadline itself needs clarification from Ben before building.

**work_unbilled:**
OPEN QUESTION: No natural "issued date" for a completed-but-unbilled engagement.
`Engagement.completed_at` is a real stored column (stamped on status transition),
which is the closest real fact. Whether that is what "issued date" means here needs
clarification.

---

### 8. LAST CLIENT COMMUNICATION

Real source: This is the field with the most genuine uncertainty. No model in
the read set has a general-purpose "last_communicated_at" or "last_contacted_at"
column on Client, Engagement, or any entity.

The two closest real stored facts found:

**Invoice.last_reminder_sent_at** (DateTime nullable, on `invoices` table):
Stores when the most recent invoice reminder was sent. Also `Invoice.reminder_count`
(Integer, counts reminders). For `invoice_overdue` items, this is a real stored
fact about the last outbound reminder action on that specific invoice.
Join: `payload["invoice_id"]` -> `SELECT last_reminder_sent_at, reminder_count FROM invoices WHERE id = :id AND firm_id = :firm_id`

**Client.portal_last_login_at** (DateTime nullable, on `clients` table):
Stores when the client last logged in to the portal. A real stored fact about
client activity.
Join: `payload["client_id"]` -> `SELECT portal_last_login_at FROM clients WHERE id = :id AND firm_id = :firm_id`

The `behavioral_events` table (fields: firm_id, event_type, entity_type, entity_id,
actor_type, actor_id, occurred_at, metadata) WOULD contain communication events.
However, `surface_item_service.py` is explicitly governed by the rule "nothing here
reads behavioral_events to make a decision about a row" and states "Nothing here reads
behavioral_events to decide anything." Reading behavioral_events for display purposes
in a detail panel would not violate this rule strictly (no decision is made), but
it conflicts with the module's governing principle and the surface items system's
design intent. This should be an explicit decision before building.

OPEN QUESTION: What is the intended source for "Last Client Communication" -- the
most recent invoice reminder (`Invoice.last_reminder_sent_at`), portal login
(`Client.portal_last_login_at`), or something else? Cannot be answered from
the models read without more specificity on what "communication" means.

---

### 9. RELATED DOCUMENTS ON FILE

Real source: `Document` model (documents table)
Real columns: `Document.client_id`, `Document.engagement_id`, `Document.scope`
  ("engagement" | "client" | "firm_library"), `Document.deleted_at` (soft delete),
  `Document.is_superseded` (bool), `Document.filename`, `Document.category`

For items with engagement_id (deadline_with_blockers, work_unbilled, signature items
with non-null engagement):
  Deterministic COUNT:
  `SELECT COUNT(*) FROM documents WHERE engagement_id = :id AND firm_id = :firm_id
   AND deleted_at IS NULL AND is_superseded = FALSE`

For items with only client_id (invoice_overdue, irs_auth_expiring):
  Deterministic COUNT across client and engagement scopes:
  `SELECT COUNT(*) FROM documents WHERE client_id = :client_id AND firm_id = :firm_id
   AND deleted_at IS NULL AND is_superseded = FALSE`
  Note: this returns all documents for the client (engagement-scoped and client-scoped),
  because `Document.scope = 'engagement'` still carries `client_id NOT NULL`.

Computation type: Deterministically calculated (COUNT query). No interpretation.
Not in any payload today; requires a query at expand time.

---

### 10. OPEN ITEMS ALREADY IN THE RECORD

Real source: `Task`, `DocumentRequest`, `SignatureEnvelope` tables
(same three tables used by `_count_blockers` in surface_generators.py)

For `deadline_with_blockers`:
`payload["open_blockers"]` is already written at generation time. It is the
output of `_count_blockers(db, firm_id, engagement.id)`, which counts:
  - DocumentRequest checklist items with status NOT IN ("approved", "waived")
  - Tasks with `is_completed = FALSE`
  - SignatureEnvelopes with `status = 'sent'`
All scoped to the engagement. No join required for this field on deadline items.

For other item types with engagement_id in payload (work_unbilled, signature items):
Same `_count_blockers` logic applies. Requires three COUNT queries.

For invoice_overdue:
GAP. No `engagement_id` in payload. Would require `Invoice.engagement_id`
(nullable) as an intermediate step. If the invoice is not linked to an engagement,
a client-scoped count across all engagements would be needed instead.

For irs_auth_expiring:
GAP. No `engagement_id` in payload. Same open question as ENGAGEMENT field.

Computation type: Deterministically calculated. Values change as tasks and
document requests are completed.

---

## Section 2: Payload Identifier Sufficiency

Summary of what each generator writes to payload today, and what is missing for
the ten fields:

**invoice_overdue** writes: invoice_id, invoice_number, client_id, balance, days_overdue
Missing for full ten-field coverage:
  - engagement_id (needed for: ENGAGEMENT, ASSIGNED STAFF, OPEN ITEMS via
    the normal path). Workaround: two-hop via Invoice.engagement_id at expand time.
    That join is nullable; some invoices genuinely have no engagement.

**irs_auth_expiring** writes: authorization_id, client_id, form_type, valid_until, days_to_expiry
Missing for full ten-field coverage:
  - engagement_id (if IrsAuthorization model has one -- not confirmed from read set).
    Without it: ASSIGNED STAFF and OPEN ITEMS have no direct path.
  - "issued date" (see Section 1 open question)

**signature_stalled** writes: envelope_id, client_id, engagement_id (nullable), days_waiting
Missing: engagement_id may be null for client-only envelopes; all joins on engagement
  are therefore conditional.

**signature_declined** writes: envelope_id, client_id, engagement_id (nullable), days_since, ending
Same gap as signature_stalled.

**signature_expired** writes: envelope_id, client_id, engagement_id (nullable), days_since, ending
Same gap as signature_stalled.

**deadline_with_blockers** writes: engagement_id, client_id, engagement_name, deadline,
  days_remaining, open_blockers
No missing identifiers for the ten fields. This generator's payload is the most
complete. OPEN ITEMS is already in payload.

**work_unbilled** writes: engagement_id, client_id, engagement_name, days_since_completion
No missing identifiers for the ten fields. CURRENT WORKFLOW STATUS requires one
join (Engagement.status), and ISSUED DATE meaning is unclear (see Section 1).

Generator requiring a real payload change:
- `invoice_overdue` would benefit from adding `engagement_id` (from
  `Invoice.engagement_id`) to its payload IF the join is desired at serve or expand
  time without going through Invoice. However, `Invoice.engagement_id` is nullable,
  so the field should be written as null when not present rather than omitted. This
  is a judgment call for the build task, not a requirement to state here.
- No other generator strictly requires a payload change, as their engagement_id
  is either already present or unreachable through any path (irs_auth_expiring gap
  is model-knowledge-dependent).

---

## Section 3: Inline vs Lazy Recommendation

**Inline (added to every GET /api/v1/briefing response):**
For up to 5 rows, adding all ten fields inline would require, on every briefing
page load, approximately:
  - 1 batch client_name query (already done)
  - Up to 5 Invoice queries (status, sent_at, last_reminder_sent_at)
  - Up to 5 Engagement queries (status)
  - Up to 5 EngagementMember queries + 5 User queries (assigned staff)
  - Up to 5 Document COUNT queries
  - Up to 15 additional queries for open items (Task + DocumentRequest +
    SignatureEnvelope per engagement)
Total: roughly 30-40 additional queries per GET /briefing, every page load,
even if the user never opens a single detail panel.

`client_name` is inline because it is shown in every row unconditionally.
The detail fields are shown only when a row is expanded. Expand events will
be the minority of briefing views.

**Lazy (separate per-item request, fetched on expand click):**
Zero overhead on GET /briefing. Queries run only when a specific row is
expanded. For a single expand, the queries are bounded by what that one item
needs (typically 2-6 queries depending on item type). Already implemented as
an expand/collapse UI pattern in the briefing page (as of the previous build
session). `surfaceItemsApi.getNarrative()` currently covers the narrative
cache path; the detail field data would need its own per-item endpoint or
could be added to that response shape.

**Recommendation: Lazy, per-item expand endpoint.**
The added query cost at GET /briefing time is not justified when the fields
are only needed for expanded rows. A dedicated GET endpoint (e.g.
GET /api/v1/surface-items/{item_id}/detail) that returns the ten computed
fields for one item is the right shape. It keeps the briefing list fast,
computes only what is actually viewed, and isolates the join complexity
to one place rather than spreading it across the briefing service.

---

## Section 4: Tier 1 Summary Deterministic Template

All values below are read directly from `SurfaceItem.payload` fields written
at generation time. Zero additional queries. Zero AI.

```python
from collections import defaultdict
from decimal import Decimal


def build_tier1_summary(items: list) -> str:
    """
    Deterministic summary sentence from real payload counts and sums.
    items: list of SurfaceItem objects (already loaded by get_briefing).
    Reads only payload fields written by the generators.
    """
    groups: dict[str, list] = defaultdict(list)
    for item in items:
        groups[item.item_type].append(item)

    parts = []

    overdue = groups.get("invoice_overdue", [])
    if overdue:
        n = len(overdue)
        total = sum(Decimal(str(i.payload.get("balance", 0))) for i in overdue)
        noun = "invoice" if n == 1 else "invoices"
        parts.append(f"{n} {noun} overdue, balances totaling ${total:,.0f}")

    irs = groups.get("irs_auth_expiring", [])
    if irs:
        n = len(irs)
        noun = "IRS authorization" if n == 1 else "IRS authorizations"
        parts.append(f"{n} {noun} expiring")

    stalled = groups.get("signature_stalled", [])
    declined = groups.get("signature_declined", [])
    expired = groups.get("signature_expired", [])
    sigs = stalled + declined + expired
    if sigs:
        n = len(sigs)
        noun = "signature request" if n == 1 else "signature requests"
        parts.append(f"{n} {noun} pending")

    deadlines = groups.get("deadline_with_blockers", [])
    if deadlines:
        n = len(deadlines)
        total_blockers = sum(i.payload.get("open_blockers", 0) for i in deadlines)
        noun = "deadline" if n == 1 else "deadlines"
        item_noun = "open item" if total_blockers == 1 else "open items"
        parts.append(f"{n} {noun} with {total_blockers} {item_noun}")

    unbilled = groups.get("work_unbilled", [])
    if unbilled:
        n = len(unbilled)
        noun = "engagement" if n == 1 else "engagements"
        parts.append(f"{n} completed {noun} not yet invoiced")

    if not parts:
        return "You're all caught up."

    return "; ".join(parts) + "."
```

Example output (matching the target style):
  "3 invoices overdue, balances totaling $5,100; 2 deadlines with 7 open items."

This function is appropriate to call inside `get_briefing` in
`surface_item_service.py`, where `rows` is already loaded and `_attach_client_names`
has already been called. The result replaces the current AI-generated short text.

---

## Section 5: Implement Endpoint Confirmation

`POST /api/v1/surface-items/{item_id}/implement` exists and functions as built.

Verbatim from `app/api/surface_items.py`:

```python
@router.post("/surface-items/{item_id}/implement", response_model=SurfaceItemOut)
def implement_item(
    item_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_manager_or_above),
):
    item = surface_item_service.get_item_for_firm(db, item_id, current_firm.id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    return surface_item_service.implement_item(db, item, actor_id=current_user.id)
```

Behavior (from `surface_item_service.implement_item`):
Sets `implemented_at = now()`, stores `value_at_action = payload["measured"]`,
sets `suppressed_until = now() + suppression_days_for(item.kind)` (7 days for
Briefing, 14 for Observatory), sets `slotted_at = None`, commits, refreshes,
fires `surface_item.implemented` behavioral event (fire-and-forget; failure
does not roll back the row write). Returns `SurfaceItemOut`.

This endpoint is not proposed for removal or alteration. Confirmed as-built.

---

## Section 6: Genuine Open Questions

These are fields where the real source is ambiguous or depends on model
files not in the read set for this task. They are stated as real open
questions, not guessed answers.

**Q1: Assigned Staff for irs_auth_expiring**
`irs_auth_expiring` payload contains `authorization_id` and `client_id` but no
`engagement_id`. Whether `IrsAuthorization` carries an `engagement_id` column
was not confirmed (that model file was not in the read set). Without an
engagement_id, there is no path to `EngagementMember`. Cannot confirm
assigned staff join path for this item type.

**Q2: Issued Date for deadline_with_blockers and work_unbilled**
"Issued date" is clear for invoices (`Invoice.sent_at`) and signature envelopes
(`SignatureEnvelope.sent_at`). For an engagement deadline, there is no single
obvious "issued date." Candidates: `Engagement.start_date` (when work started),
`Engagement.created_at` (when the record was created), or `payload["deadline"]`
(the filing deadline, which is a due date not an issue date). Needs Ben's
clarification before building.

**Q3: Issued Date for irs_auth_expiring**
`IrsAuthorization` model not read. Payload has `valid_until` (expiry date).
Whether an "issued on" column exists on that model is not confirmed.

**Q4: Last Client Communication -- intended source**
No model read has a general-purpose "last communicated with client" column.
Two real stored facts are available: `Invoice.last_reminder_sent_at` (invoice
reminders only) and `Client.portal_last_login_at` (client-side portal activity).
The behavioral_event table has communication event data but reading it conflicts
with the system's governing rule. Which of these -- or something else -- is the
intended source needs explicit confirmation before building.

**Q5: Engagement for invoice_overdue at the expand panel**
`Invoice.engagement_id` is nullable. If an invoice was created without linking
it to an engagement, ENGAGEMENT, ASSIGNED STAFF, and OPEN ITEMS fields will
have no value for that row's expand panel. Is a null/missing display acceptable,
or does the invoice_overdue generator need to be updated to add `engagement_id`
to its payload when one exists?

---

## Section 7: surface_narrative Columns Drop Assessment

The three columns added to `Firm` -- `surface_narrative_date`,
`surface_narrative_short`, `surface_narrative_long` -- were examined in the
context of whether they are safe to drop.

Current state confirmed by reading `git show HEAD:app/models/firm.py` (no
output for surface_narrative) and `git status --short` (shows
`app/models/firm.py` as ` M` meaning unstaged, uncommitted modification):

**These three columns are NOT present in any committed revision of the codebase.**
They exist only in uncommitted working tree changes:
  - Unstaged modification to `app/models/firm.py`
  - Unstaged modification to `app/api/concierge/route.py`
    (surface_narrative_router import and `router.include_router` call)
  - Untracked file `app/api/concierge/surface_narrative.py`
    (the endpoint that reads/writes all three columns)
  - Untracked migration `migrations/versions/7e2f9a1b4c83_add_surface_narrative_fields_to_firm.py`
  - Uncommitted modification to `app/api/concierge/prompts.py`
    (SURFACE_NARRATIVE_SHORT_PROMPT, SURFACE_NARRATIVE_DETAIL_PROMPT)
  - Untracked `tests/test_surface_narrative.py`

If the AI narrative approach is abandoned: no committed code references these
columns. The path to discard them is to revert the uncommitted changes to
`firm.py`, `route.py`, `prompts.py`, and delete the four untracked files.
No migration downgrade is required for the production database provided the
untracked migration was never applied to production. If it was applied to
any local dev database, a downgrade is needed to keep that DB in sync.

The briefing page UI (`frontend/src/app/(app)/briefing/`) and its API type
(`frontend/src/lib/api/surfaceItems.ts`) are also untracked and use
`item_details` from this endpoint. If the endpoint is removed, those files
would need to be revised as well.
