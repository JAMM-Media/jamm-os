# JAMM PX — Quick Fix

Read every instruction in this file before writing a single line of code.

---

## TASK 1 — Fix webhook signed document handling to use existing store_signed_document task

**File to edit:** `app/api/esign.py`

The new webhook handler handles `signature_request_signed` by uploading the PDF inline and using `signed_document_s3_key` which doesn't exist on the schema. There's already a `store_signed_document` background task that does this correctly — creates the document record, links it to the envelope via `signed_document_id`, and updates the status.

Find the `signature_request_signed` block in `handle_webhook`:

```python
if event_type == "signature_request_signed":
    pdf_bytes = dropbox_sign.download_signed_document(signature_request_id)
    s3_key = f"{envelope.firm_id}/signed/{envelope.id}.pdf"
    s3_service.upload_fileobj(
        io.BytesIO(pdf_bytes),
        s3_key,
        "application/pdf",
    )
    crud_envelope.update_signature_envelope(
        db,
        envelope,
        SignatureEnvelopeUpdate(status="signed", signed_document_s3_key=s3_key),
    )
    write_audit_log(
        db=db,
        firm_id=envelope.firm_id,
        action="esign.signed",
        actor_type="client",
        entity_type="signature_envelope",
        entity_id=envelope.id,
    )
    log_event(...)
```

Replace it with:

```python
if event_type == "signature_request_signed":
    pdf_bytes = dropbox_sign.download_signed_document(signature_request_id)
    background_tasks.add_task(store_signed_document, db, envelope, pdf_bytes)
    write_audit_log(
        db=db,
        firm_id=envelope.firm_id,
        action="esign.signed",
        actor_type="client",
        entity_type="signature_envelope",
        entity_id=envelope.id,
    )
    log_event(
        firm_id=envelope.firm_id,
        event_type="engagement_letter.signed",
        entity_type="signature_envelope",
        entity_id=envelope.id,
        actor_type="client",
        actor_id=None,
        metadata={
            "client_id": str(envelope.client_id),
            "engagement_id": str(envelope.engagement_id) if envelope.engagement_id else None,
            "days_to_sign": (
                (datetime.now(timezone.utc) - envelope.sent_at).days
                if hasattr(envelope, 'sent_at') and envelope.sent_at
                else None
            ),
        }
    )
```

The `store_signed_document` function already exists in this file — it uploads the PDF to S3, creates the document record with a proper filename, and updates the envelope with `signed_document_id` and `status="signed"`. No need to duplicate that logic.

Also check that `store_signed_document` is still defined in this file and not accidentally removed during previous edits. If it was removed, add it back from the original:

```python
async def store_signed_document(
    db: Session,
    envelope: SignatureEnvelope,
    pdf_bytes: bytes,
) -> None:
    engagement_segment = (
        str(envelope.engagement_id) if envelope.engagement_id else "no_engagement"
    )
    s3_key = (
        f"{envelope.firm_id}/signed/{envelope.client_id}"
        f"/{engagement_segment}/{envelope.provider_envelope_id}.pdf"
    )

    s3_service.upload_fileobj(io.BytesIO(pdf_bytes), s3_key, "application/pdf")

    doc = crud_document.create_document(
        db=db,
        firm_id=envelope.firm_id,
        client_id=envelope.client_id,
        engagement_id=envelope.engagement_id,
        uploaded_by=None,
        filename=f"{envelope.provider_envelope_id}.pdf",
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
```

No frontend changes. No migration needed.