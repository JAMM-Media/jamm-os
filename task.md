# JAMM PX — Fix Document Response Enrichment

Read every instruction in this file before writing a single line of code. Execute in the order listed.

---

## TASK 1 — Backend: enrich DocumentOut with client_name, engagement_title, uploaded_by_name

**File to edit:** `app/schemas/document.py`

Add optional enrichment fields to `DocumentOut`:

```python
class DocumentOut(BaseModel):
    id: uuid.UUID
    firm_id: uuid.UUID
    client_id: uuid.UUID
    engagement_id: uuid.UUID
    uploaded_by: Optional[uuid.UUID]
    filename: str
    s3_key: str
    content_type: str
    size_bytes: int
    category: Optional[str] = "other"
    visibility: str = "internal"
    created_at: datetime
    updated_at: datetime
    envelope_status: Optional[str] = None
    # Enrichment fields — populated by API layer, not from DB model
    client_name: Optional[str] = None
    engagement_title: Optional[str] = None
    uploaded_by_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
```

---

## TASK 2 — Backend: populate enrichment fields in document list and get endpoints

**File to edit:** `app/api/documents.py`

The list endpoint already does manual pagination. Update it to also populate `client_name`, `engagement_title`, and `uploaded_by_name`.

After the existing envelope status enrichment block, add:

```python
# Fetch client names
from app.models.client import Client
from app.models.engagement import Engagement
from app.models.user import User

client_ids = [doc.client_id for doc in docs if doc.client_id]
engagement_ids = [doc.engagement_id for doc in docs if doc.engagement_id]
uploaded_by_ids = [doc.uploaded_by for doc in docs if doc.uploaded_by]

client_map = {}
if client_ids:
    clients = db.query(Client).filter(Client.id.in_(client_ids)).all()
    client_map = {c.id: c.name for c in clients}

engagement_map = {}
if engagement_ids:
    engagements = db.query(Engagement).filter(Engagement.id.in_(engagement_ids)).all()
    engagement_map = {e.id: e.name for e in engagements}

user_map = {}
if uploaded_by_ids:
    users = db.query(User).filter(User.id.in_(uploaded_by_ids)).all()
    user_map = {u.id: u.full_name or u.email for u in users}
```

Then update the `items` list to include these:

```python
items = [
    DocumentOut.model_validate(doc).model_copy(
        update={
            "envelope_status": envelope_status_map.get(doc.id, "uploaded"),
            "client_name": client_map.get(doc.client_id),
            "engagement_title": engagement_map.get(doc.engagement_id),
            "uploaded_by_name": user_map.get(doc.uploaded_by) if doc.uploaded_by else None,
        }
    )
    for doc in docs
]
```

Apply the same enrichment to the `GET /documents/{document_id}` single endpoint. After the envelope lookup, add:

```python
from app.models.client import Client
from app.models.engagement import Engagement  
from app.models.user import User

client = db.query(Client).filter(Client.id == doc.client_id).first()
engagement = db.query(Engagement).filter(Engagement.id == doc.engagement_id).first()
uploader = db.query(User).filter(User.id == doc.uploaded_by).first() if doc.uploaded_by else None

return DocumentOut.model_validate(doc).model_copy(
    update={
        "envelope_status": envelope_status,
        "client_name": client.name if client else None,
        "engagement_title": engagement.name if engagement else None,
        "uploaded_by_name": (uploader.full_name or uploader.email) if uploader else None,
    }
)
```

---

## TASK 3 — Frontend: use enrichment fields in mapDocument and fix file size display

**File to edit:** `frontend/src/lib/api/documents.ts`

Update the `Document` interface to include the new fields:

```typescript
export interface Document {
  id: string
  name: string
  clientId: string
  clientName: string
  engagementId: string
  engagementTitle: string
  status: 'uploaded' | 'pending' | 'pending_signature' | 'signed' | 'rejected'
  uploadedBy: string
  uploadedAt: string
  fileType: string
  fileSizeKb: number
}
```

Update `mapDocument` to use the enrichment fields:

```typescript
function mapDocument(raw: Record<string, unknown>): Document {
  return {
    id: String(raw.id),
    name: String(raw.filename ?? raw.file_name ?? raw.name ?? ''),
    clientId: String(raw.client_id ?? raw.clientId ?? ''),
    clientName: String(raw.client_name ?? raw.clientName ?? ''),
    engagementId: String(raw.engagement_id ?? raw.engagementId ?? ''),
    engagementTitle: String(raw.engagement_title ?? raw.engagementTitle ?? raw.engagement_name ?? ''),
    status: ((raw.envelope_status ?? raw.status) as Document['status']) ?? 'uploaded',
    uploadedBy: raw.uploaded_by_name
      ? String(raw.uploaded_by_name)
      : raw.uploaded_by
      ? 'Staff'
      : 'System',
    uploadedAt: String(raw.uploaded_at ?? raw.uploadedAt ?? ''),
    fileType: String(raw.file_type ?? raw.fileType ?? 'PDF'),
    fileSizeKb: raw.size_bytes
      ? Math.round(Number(raw.size_bytes) / 1024 * 10) / 10
      : Number(raw.file_size_kb ?? raw.fileSizeKb ?? 0),
  }
}
```

Key changes:
- `clientName` reads `raw.client_name` from the enriched response
- `engagementTitle` reads `raw.engagement_title` or `raw.engagement_name`
- `uploadedBy` shows the user's name, "Staff" for known users, "System" for null
- `fileSizeKb` rounds to 1 decimal place

Run TypeScript check after.

---

## EXECUTION ORDER

1. Task 1 — app/schemas/document.py
2. Task 2 — app/api/documents.py
3. Task 3 — frontend/src/lib/api/documents.ts

No migrations needed. Report every file modified.