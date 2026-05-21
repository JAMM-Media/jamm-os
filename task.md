# JAMM PX — Quick Fix

Read every instruction in this file before writing a single line of code.

---

## TASK 1 — Fix store_signed_document to use its own DB session and be sync

**File to edit:** `app/api/esign.py`

The `store_signed_document` function is `async` and receives the request's `db` session. Background tasks run after the response is sent, so the request session is closed by then. Also, async background tasks can behave unexpectedly.

Find `store_signed_document` and replace it entirely with a sync version that creates its own session:

```python
def store_signed_document(
    envelope_id: str,
    firm_id: str,
    client_id: str,
    engagement_id,
    provider_envelope_id: str,
    pdf_bytes: bytes,
) -> None:
    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        from app.models.signature_envelope import SignatureEnvelope as _SE
        envelope = db.query(_SE).filter(_SE.id == envelope_id).first()
        if not envelope:
            return

        engagement_segment = (
            str(engagement_id) if engagement_id else "no_engagement"
        )
        s3_key = (
            f"{firm_id}/signed/{client_id}"
            f"/{engagement_segment}/{provider_envelope_id}.pdf"
        )

        s3_service.upload_fileobj(io.BytesIO(pdf_bytes), s3_key, "application/pdf")

        doc = crud_document.create_document(
            db=db,
            firm_id=uuid.UUID(firm_id),
            client_id=uuid.UUID(client_id),
            engagement_id=uuid.UUID(str(engagement_id)) if engagement_id else None,
            uploaded_by=None,
            filename=f"{provider_envelope_id}.pdf",
            s3_key=s3_key,
            content_type="application/pdf",
            size_bytes=len(pdf_bytes),
        )

        crud_envelope.update_signature_envelope(
            db,
            envelope,
            SignatureEnvelopeUpdate(
                signed_document_id=doc.id,
                status="signed",
            ),
        )
        db.commit()
    except Exception as exc:
        import logging as _log
        _log.getLogger(__name__).error("store_signed_document failed: %s", exc, exc_info=True)
        db.rollback()
    finally:
        db.close()
```

Then update the call site in `handle_webhook` to pass individual values instead of the envelope object:

Find:
```python
background_tasks.add_task(store_signed_document, db, envelope, pdf_bytes)
```

Replace with:
```python
background_tasks.add_task(
    store_signed_document,
    str(envelope.id),
    str(envelope.firm_id),
    str(envelope.client_id),
    envelope.engagement_id,
    envelope.provider_envelope_id,
    pdf_bytes,
)
```

Also check if `uuid` is imported at the top of the file — add `import uuid` if missing.

No frontend changes. No migration needed.