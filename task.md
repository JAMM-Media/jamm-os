# JAMM PX — Quick Fix

Read every instruction in this file before writing a single line of code.

---

## TASK 1 — Add GET /documents/{document_id} endpoint

**File to edit:** `app/api/documents.py`

There is no endpoint for fetching a single document by ID — only `/documents/{id}/download` and `/documents/{id}/audit` exist. The frontend document detail page calls `GET /documents/{document_id}` and gets a 404.

Add a new endpoint between the list endpoint and the download endpoint:

```python
# -----------------------------------------------------------------------
# GET /documents/{document_id} — Return a single document
# -----------------------------------------------------------------------
@router.get("/{document_id}", response_model=DocumentOut)
def get_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
):
    doc = crud_document.get_document(db, document_id=document_id, firm_id=current_firm.id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Enrich with envelope status
    from app.models.signature_envelope import SignatureEnvelope
    envelope = db.query(SignatureEnvelope).filter(
        SignatureEnvelope.signed_document_id == document_id
    ).first()
    envelope_status = envelope.status if envelope else "uploaded"

    return DocumentOut.model_validate(doc).model_copy(
        update={"envelope_status": envelope_status}
    )
```

Also update `mapDocument` in `frontend/src/lib/api/documents.ts` to read `envelope_status` as the status field:

**File to edit:** `frontend/src/lib/api/documents.ts`

Find:
```typescript
status: (raw.status as Document['status']) ?? 'uploaded',
```

Replace with:
```typescript
status: ((raw.envelope_status ?? raw.status) as Document['status']) ?? 'uploaded',
```

This means the frontend prefers `envelope_status` (from the backend enrichment) over `status` (which doesn't exist on the Document model). Documents with a signed envelope will show "signed", all others will show "uploaded".

No migration needed. Run TypeScript check after the frontend change.