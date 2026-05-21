# JAMM PX — Fix Webhook Handler

Read every instruction in this file before writing a single line of code.

---

## TASK 1 — Fix the Dropbox Sign webhook handler

**File to edit:** `app/api/esign.py`

Dropbox Sign sends webhooks as `multipart/form-data` POST requests with the event JSON in a field named `json`. The signature (`event_hash`) is inside the JSON payload itself, not in an HTTP header.

Find the `handle_webhook` function and replace it entirely with:

```python
@router.post("/webhook")
async def handle_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    import logging as _logging
    import hashlib
    import hmac as _hmac

    # Dropbox Sign sends multipart/form-data with event JSON in a field called "json"
    content_type = request.headers.get("content-type", "")
    
    if "multipart/form-data" in content_type:
        form = await request.form()
        json_str = form.get("json")
        if not json_str:
            raise HTTPException(status_code=400, detail="Missing json field in form data")
        try:
            data = json.loads(json_str)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON in form data")
    else:
        # Fallback: try reading as raw JSON body
        payload_bytes = await request.body()
        try:
            data = json.loads(payload_bytes)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid request body")

    # Validate event_hash from within the payload
    event = data.get("event", {})
    event_hash = event.get("event_hash")
    
    if event_hash:
        # Validate: HMAC-SHA256 of (event_time + event_type) using API key as secret
        event_time = str(event.get("event_time", ""))
        event_type = str(event.get("event_type", ""))
        settings = get_settings()
        secret = settings.DROPBOX_SIGN_API_KEY.encode()
        computed = _hmac.new(
            secret,
            (event_time + event_type).encode(),
            hashlib.sha256,
        ).hexdigest()
        if not _hmac.compare_digest(computed, event_hash):
            _logging.getLogger(__name__).warning(
                "Webhook signature mismatch: computed=%s received=%s",
                computed, event_hash
            )
            raise HTTPException(status_code=403, detail="Invalid webhook signature")

    event_type = event.get("event_type")
    
    # Dropbox Sign requires responding with {"status": "ok"} for the test event
    if event_type == "callback_test":
        return {"status": "ok"}

    signature_request = data.get("signature_request", {})
    signature_request_id = signature_request.get("signature_request_id")

    if not signature_request_id:
        return {"status": "ok"}

    # Silently ack if our record doesn't exist yet
    envelope = db.execute(
        select(SignatureEnvelope).where(
            SignatureEnvelope.provider_envelope_id == signature_request_id
        )
    ).scalars().first()
    if envelope is None:
        return {"status": "ok"}

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

    # Dropbox Sign retries unless it receives exactly {"status": "ok"}.
    return {"status": "ok"}
```

Check existing imports at the top of esign.py:
- `get_settings` — should already be imported
- `DROPBOX_SIGN_API_KEY` — accessed via `get_settings().DROPBOX_SIGN_API_KEY`
- `log_event` — already imported from previous task
- `io`, `json`, `datetime`, `timezone` — check and add if missing

No frontend changes. No migration needed.