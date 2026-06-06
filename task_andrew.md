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

# PHASE INSTRUCTIONS — DOCUMENT ARCHIVE EXPORT (ASYNC)

## Context
The CSV firm export is already live at GET /api/v1/firm-export/download.
This build adds a separate async document archive export.

The document archive is async because fetching potentially hundreds of files
from S3 and assembling a ZIP could take 30-60 seconds -- too long for a
synchronous HTTP response.

Pattern:
1. Firm owner clicks "Request document archive" in settings
2. Backend kicks off a background job immediately, returns 202 Accepted
3. Background job: fetches all documents from S3, assembles ZIP,
   uploads ZIP to S3 under exports/{firm_id}/documents_{date}.zip,
   generates a presigned download URL (24 hour expiry),
   emails the firm owner with the download link
4. Firm owner gets an email with a download link within a few minutes

No migration needed. No new models needed.
S3 functions available: generate_presigned_url(s3_key),
upload_fileobj(fileobj, s3_key, content_type).
Document model has: s3_key, filename, content_type, size_bytes,
client_id, engagement_id, firm_id.

---

## Pre-task checkpoint
git add -A
git commit -m "checkpoint before document archive export"

---

## VERIFY BEFORE STARTING
grep -n "def upload_fileobj\|def generate_presigned_url" app/services/s3.py
grep -n "class Document\b\|s3_key\|filename" app/models/document.py
Paste both outputs before touching anything.

---

## Change 1: Create app/services/document_archive_service.py

Create this file from scratch. Path comment at top.

### Main function: generate_and_deliver_document_archive(firm_id: UUID) -> None

This function runs in a background thread. It owns its own database session
and S3 connections. It never raises to the caller -- all exceptions are caught
and logged.

Structure:

```python
def generate_and_deliver_document_archive(firm_id: UUID) -> None:
    import logging
    log = logging.getLogger(__name__)
    db = None
    try:
        from app.db.session import SessionLocal
        db = SessionLocal()
        _run_archive(firm_id, db, log)
    except Exception as exc:
        log.error("document_archive: top-level error firm=%s: %s", firm_id, type(exc).__name__)
    finally:
        if db:
            db.close()
```

### Inner function: _run_archive(firm_id, db, log)

Step 1: Load all documents for this firm
```python
from app.models.document import Document
from sqlalchemy import select
documents = db.execute(
    select(Document).where(Document.firm_id == firm_id)
).scalars().all()
```
If no documents: send email saying "No documents found to archive" and return.

Step 2: Assemble ZIP in memory
```python
import io, zipfile, requests as http_requests
zip_buf = io.BytesIO()
with zipfile.ZipFile(zip_buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
    for doc in documents:
        try:
            from app.services.s3 import generate_presigned_url
            url = generate_presigned_url(doc.s3_key)
            resp = http_requests.get(url, timeout=30)
            resp.raise_for_status()
            # Use client_id/engagement_id as folder structure in ZIP
            folder = str(doc.client_id)
            if doc.engagement_id:
                folder = f"{folder}/{doc.engagement_id}"
            zf.writestr(f"{folder}/{doc.filename}", resp.content)
        except Exception as exc:
            log.warning("document_archive: skipped doc %s: %s", doc.id, type(exc).__name__)
            continue
zip_buf.seek(0)
```

Step 3: Upload ZIP to S3
```python
from datetime import date
from app.services.s3 import upload_fileobj
s3_key = f"exports/{firm_id}/documents_{date.today().isoformat()}.zip"
upload_fileobj(zip_buf, s3_key, "application/zip")
```

Step 4: Generate presigned download URL with 24 hour expiry
```python
import boto3
from app.core.config import get_settings
settings = get_settings()
s3_client = boto3.client(
    "s3",
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    region_name=settings.AWS_REGION,
)
download_url = s3_client.generate_presigned_url(
    "get_object",
    Params={"Bucket": settings.S3_BUCKET_NAME, "Key": s3_key},
    ExpiresIn=86400,
)
```

Step 5: Find firm owner and send email
```python
from app.models.user import User
from app.models.firm import Firm
from app.core.enums import UserRole
from app.services.email_service import EmailService

firm_owner = db.query(User).filter(
    User.firm_id == firm_id,
    User.role == UserRole.firm_owner,
    User.is_active == True,
).first()
if not firm_owner:
    log.warning("document_archive: no firm owner found for firm %s", firm_id)
    return

firm = db.query(Firm).filter(Firm.id == firm_id).first()
firm_name = firm.name if firm else "Your firm"
doc_count = len(documents)

EmailService.send_notification_email(
    to_email=firm_owner.email,
    firm_name=firm_name,
    recipient_name=firm_owner.full_name or "Firm Owner",
    title="Your document archive is ready",
    body=f"Your document archive containing {doc_count} files is ready to download. The link below will expire in 24 hours.",
    app_url=download_url,
)
```

Step 6: Fire behavioral event
```python
from app.services.behavioral_log import log_event
log_event(
    firm_id=firm_id,
    event_type="firm.document_archive_requested",
    entity_type="firm",
    entity_id=firm_id,
    actor_type="staff",
    metadata={"document_count": doc_count},
)
```

---

## Change 2: Add endpoint to app/api/firm_export.py

Open the existing firm_export.py router.
Add one new endpoint: POST /firm-export/request-document-archive

- Auth: require_firm_owner
- Immediately starts background thread:
```python
  import threading
  from app.services.document_archive_service import generate_and_deliver_document_archive
  threading.Thread(
      target=generate_and_deliver_document_archive,
      kwargs={"firm_id": current_firm.id},
      daemon=True,
  ).start()
```
- Returns immediately:
```python
  return {"status": "processing", "message": "Your document archive is being prepared. You will receive an email with a download link shortly."}
```
- Write audit log: action "firm.document_archive_requested"
- No BackgroundTasks dependency needed -- use threading directly

---

## Change 3: Add "Request document archive" button to settings frontend

Find the DataExportSection component in frontend/src/app/settings/page.tsx.
It currently has one button: "Download export".

Add a second button below it: "Request document archive"
- Same styling as the download button
- On click: calls POST /api/v1/firm-export/request-document-archive
- Shows loading spinner while in flight
- On success: shows toast "Document archive requested. You will receive an email with a download link shortly."
- On error: shows toast "Request failed. Please try again."
- Add a second loading state: const [requestingArchive, setRequestingArchive] = useState(false)
- Add muted helper text below the button: "Large archives may take a few minutes. A download link will be sent to your email."

---

## Verify after all changes
grep -n "def generate_and_deliver_document_archive\|def _run_archive\|document_archive" app/services/document_archive_service.py
grep -n "request-document-archive\|document_archive" app/api/firm_export.py
python -m py_compile app/services/document_archive_service.py
python -m py_compile app/api/firm_export.py
Both compiles must pass before deploying.

---

## Deploy sequence
git add -A
git commit -m "async document archive export with email delivery"
git push origin main
Then on the droplet:
git pull origin main
alembic upgrade head
alembic current
systemctl restart jammpx.service
journalctl -u jammpx.service -n 20 --no-pager