# JAMM PX — Quick Fix

Read every instruction in this file before writing a single line of code.

---

## TASK 1 — Fix duplicate S3 key in prepare_letter endpoint

**File to edit:** `app/api/esign.py`

In the `prepare_letter` function, find the S3 key construction:

```python
s3_key = (
    f"{current_firm.id}/letters/{payload.engagement_id}"
    f"/{template.name}_{date.today()}.pdf"
)
```

Replace with:

```python
import uuid as _uuid
s3_key = (
    f"{current_firm.id}/letters/{payload.engagement_id}"
    f"/{template.name}_{date.today()}_{_uuid.uuid4().hex[:8]}.pdf"
)
```

This appends a short random hex suffix to the filename so every send generates a unique S3 key, preventing the duplicate key constraint on the documents table.

No migration needed. No frontend changes needed.