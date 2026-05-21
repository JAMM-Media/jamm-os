# JAMM PX — Quick Fix

Read every instruction in this file before writing a single line of code.

---

## TASK 1 — Fix prepare_letter endpoint: populate signers from client

**File to edit:** `app/api/esign.py`

In the `prepare_letter` function, find the envelope creation block:

```python
envelope_schema = SignatureEnvelopeCreate(
    client_id=client.id,
    engagement_id=payload.engagement_id,
    document_id=doc.id,
    subject=template.name,
    signers=[],
)
```

Replace with:

```python
envelope_schema = SignatureEnvelopeCreate(
    client_id=client.id,
    engagement_id=payload.engagement_id,
    document_id=doc.id,
    subject=template.name,
    signers=[{
        "name": getattr(client, "full_name", None) or client.name,
        "email": client.email or "",
        "status": "pending",
        "signed_at": None,
    }],
)
```

No other changes. No migration needed.