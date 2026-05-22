# JAMM PX — Quick Fix

Read every instruction in this file before writing a single line of code.

---

## TASK 1 — Handle 409 from Dropbox Sign download in store_signed_document

**File to edit:** `app/api/esign.py`

In the `store_signed_document` function, find where `dropbox_sign.download_signed_document` is called. Currently it's called in `handle_webhook` before `store_signed_document`. The 409 means Dropbox Sign already served the PDF to a previous webhook attempt.

The fix has two parts:

### Part A — Check if envelope already has a signed document before downloading

In `handle_webhook`, find:
```python
if event_type == "signature_request_signed":
    try:
        pdf_bytes = dropbox_sign.download_signed_document(signature_request_id)
        store_signed_document(
```

Replace with:
```python
if event_type == "signature_request_signed":
    # Skip if already processed — envelope already has a signed document
    if envelope.signed_document_id:
        return PlainTextResponse("Hello API Event Received")
    try:
        pdf_bytes = dropbox_sign.download_signed_document(signature_request_id)
        store_signed_document(
```

### Part B — Handle 409 gracefully in the download service

**File to edit:** `app/services/dropbox_sign.py`

Find the `download_signed_document` function. It makes a GET request to Dropbox Sign. Find where it raises on non-ok status and add a specific check for 409:

```python
if r.status_code == 409:
    raise HTTPException(
        status_code=409,
        detail="Signed document already downloaded — Dropbox Sign only allows one download per signature request"
    )
if not r.ok:
    raise HTTPException(
        status_code=502,
        detail=f"Dropbox Sign API error: {r.status_code}"
    )
```

### Part C — Catch 409 in handle_webhook and treat as success

Back in `handle_webhook`, update the try/except around `store_signed_document`:

```python
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
    except HTTPException as _hex:
        if _hex.status_code == 409:
            # Already downloaded in a previous webhook attempt — treat as success
            pass
        else:
            import logging as _log
            _log.getLogger(__name__).error(
                "Failed to store signed document: %s", _hex, exc_info=True
            )
    except Exception as _exc:
        import logging as _log
        _log.getLogger(__name__).error(
            "Failed to store signed document: %s", _exc, exc_info=True
        )
```

No frontend changes. No migration needed.
