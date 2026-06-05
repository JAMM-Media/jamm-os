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

# PHASE INSTRUCTIONS — WEEK 3, RUN 3 OF 3: IRS ACK FILE PARSER

## Context
This run builds the .ack file parser endpoint and the frontend drag-and-drop UI.
The Engagement model already has efiled_at, irs_confirmation_number, and
is_efileable from Run 2. The acknowledged status is already in EngagementStatus.
No migration needed — this run is a new service file, a new endpoint, and
frontend UI only.

The .ack file is a small structured text file produced by tax software after
the IRS accepts or rejects an e-filed return. It contains one record per return.
Different tax software produces slightly different formats but all share the same
core fields on each line, typically pipe-delimited or fixed-width.

Security rules for this endpoint — non-negotiable:
- Parse only: confirmation number, form type, accept/reject status, and tax ID
- Tax ID is used as a lookup key only — find the matching client, then discard it
- Tax ID must never be written to any column, log, or behavioral event metadata
- Raw file contents must never be stored anywhere
- The behavioral event log entry contains only: confirmation number, form type,
  status, and engagement ID — never the tax ID

---

## Pre-task checkpoint
git add -A
git commit -m "checkpoint before week 3 ack parser"

---

## VERIFY BEFORE STARTING
grep -n "efiled_at\|irs_confirmation_number\|is_efileable" app/models/engagement.py
grep -n "acknowledged\|EFILEABLE_ENGAGEMENT_TYPES" app/core/enums.py
Paste both outputs before touching anything.

---

## Change 1: Create app/services/ack_parser_service.py

Create this file from scratch. Path comment at top.

This service does one thing: parse a .ack file and return a list of structured
records. It never touches the database. It never receives or returns a tax ID
after the initial parse — the tax ID is returned only so the calling endpoint
can use it as a lookup key and then discard it.

The service must handle two common .ack file formats:

FORMAT A — pipe-delimited lines:
Each line looks like:
RECTYPE|TAXPAYER_ID|CONFIRMATION_NUM|FORM_TYPE|STATUS|TAX_YEAR
Example:
ACK|123456789|20240415123456789|1040|A|2023

FORMAT B — fixed-width or key=value lines:
Some software produces lines like:
TaxpayerID=123456789 ConfirmationNum=20240415123456789 FormType=1040 Status=A

The parser should:
1. Detect which format the file uses based on whether lines contain pipe characters
2. For each valid record line, extract:
   - taxpayer_id (string, 9 digits, used for lookup only)
   - confirmation_number (string)
   - form_type (string, e.g. "1040", "1120")
   - status (string: "A" = accepted, "R" = rejected)
   - tax_year (string or int, optional)
3. Skip blank lines and header lines
4. Return a list of dicts with these keys:
   taxpayer_id, confirmation_number, form_type, status, tax_year
5. Raise a ValueError with a plain English message if the file cannot be parsed
   or contains no valid records

Function signature:
def parse_ack_file(contents: str) -> list[dict]:

---

## Change 2: Create app/api/ack_parser.py

Create this router from scratch. Path comment at top.
Register it in app/main.py under the prefix /ack-parser.

Single endpoint: POST /ack-parser/upload
- Auth: require_manager_or_above
- Accepts: UploadFile
- File size limit: 512KB — reject anything larger with a 400
- File type check: filename must end in .ack — reject anything else with a 400
- Encoding: read as bytes, decode as utf-8 with errors="replace"

Processing logic:
1. Call parse_ack_file(contents) from the service
2. For each record returned:
   a. Use taxpayer_id to find the matching Client in this firm:
      query Client where Client.firm_id == current_firm.id
      and Client.tax_id == taxpayer_id
      Do not search across firms. Do not log the taxpayer_id anywhere.
   b. If no client found: add to unmatched list with confirmation_number
      and form_type only — never include taxpayer_id in the response
   c. If client found: find the most recent non-archived engagement for
      that client where engagement.is_efileable is True
   d. If no efileable engagement found: add to unmatched list
   e. If engagement found:
      - Set engagement.efiled_at = datetime.now(timezone.utc)
      - Set engagement.irs_confirmation_number = record["confirmation_number"]
      - If record["status"] == "A": set engagement.status = EngagementStatus.acknowledged
      - If record["status"] == "R": leave status unchanged, flag as rejected
      - db.commit()
      - Fire behavioral event (fire-and-forget, own session):
        event_type: "engagement.efiled"
        entity_type: "engagement"
        entity_id: engagement.id
        actor_type: "staff"
        metadata: confirmation_number, form_type, status (A or R), tax_year
        NEVER include taxpayer_id in metadata
      - Write audit log entry: action "engagement.efiled"
3. Return a response with:
   - matched: count of engagements successfully updated
   - acknowledged: count where status set to acknowledged
   - rejected: count where IRS returned rejection
   - unmatched: list of dicts with confirmation_number and form_type only
   - total_records: total records found in the file

---

## Change 3: Register the router in app/main.py

Find where other routers are registered in app/main.py.
Add:
from app.api.ack_parser import router as ack_parser_router
app.include_router(ack_parser_router, prefix="/api/v1", tags=["ACK Parser"])

---

## Change 4: Frontend drag-and-drop component

Create a new file:
frontend/src/components/engagements/AckFileUploader.tsx

This is a self-contained drag-and-drop upload component.
It renders a drop zone that accepts .ack files only.
On drop or file select:
- Validate file extension is .ack before uploading
- Show a loading state while the upload is in progress
- POST the file to /api/v1/ack-parser/upload using FormData
- On success: show a summary of the result using the response fields:
  matched count, acknowledged count, rejected count, and a list of
  unmatched confirmation numbers if any
- On error: show the error message from the API response
- Allow the user to upload another file after a result is shown

Styling: use the existing JAMM PX design system tokens.
Drop zone: brand blue dashed border, muted background, centered text.
Success state: green status indicator with counts.
Rejected or unmatched: amber warning with details.

---

## Change 5: Add AckFileUploader to the Engagements page

Find the engagements list page in the frontend.
It is likely at:
frontend/src/app/(dashboard)/engagements/page.tsx

Add the AckFileUploader component in a collapsible or card section
below the main engagements table with the label:
"IRS Acknowledgment File"

Import AckFileUploader and render it. Keep it visually secondary
to the main engagements list — it should not dominate the page.

---

## Verify after all changes
grep -n "def parse_ack_file\|taxpayer_id\|confirmation_number" app/services/ack_parser_service.py
grep -n "def upload_ack\|parse_ack_file\|unmatched" app/api/ack_parser.py
grep -n "ack_parser_router\|ack-parser" app/main.py
python -m py_compile app/services/ack_parser_service.py
python -m py_compile app/api/ack_parser.py
All compiles must pass before deploying.

---

## Deploy sequence
git add -A
git commit -m "week 3 ack file parser endpoint and frontend uploader"
git push origin main
Then on the droplet:
git pull origin main
alembic upgrade head
alembic current
systemctl restart jammpx.service
journalctl -u jammpx.service -n 20 --no-pager