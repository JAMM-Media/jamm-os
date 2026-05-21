# JAMM PX — Quick Fix

Read every instruction in this file before writing a single line of code.

---

## TASK 1 — Run store_signed_document inline instead of as background task

**File to edit:** `app/api/esign.py`

The background task approach is causing intermittent 502s likely because downloading the PDF from Dropbox Sign is a blocking network call. Instead of using background_tasks, call store_signed_document directly in the webhook handler after updating the envelope status.

Find in `handle_webhook`:
```python
if event_type == "signature_request_signed":
    pdf_bytes = dropbox_sign.download_signed_document(signature_request_id)
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

Replace with:
```python
if event_type == "signature_request_signed":
    try:
        pdf_bytes = dropbox_sign.download_signed_document(signature_request_id)
        store_signed_document(
            str(envelope.id),
            str(envelope.firm_id),
            str(envelope.client_id),
            envelope.engagement_id,
            envelope.provider_envelope_id,
            pdf_bytes,
        )
    except Exception as _exc:
        import logging as _log
        _log.getLogger(__name__).error(
            "Failed to store signed document: %s", _exc, exc_info=True
        )
```

This calls store_signed_document directly (synchronously) rather than scheduling it as a background task. The webhook response is still fast enough for Dropbox Sign. Wrap in try/except so a failure here doesn't prevent the `{"Hello API Event Received"}` response from being returned.

No other changes. No frontend changes needed.