# JAMM PX — Quick Fix

Read every instruction in this file before writing a single line of code.

---

## TASK 1 — Add explicit error logging to send_envelope endpoint

**File to edit:** `app/api/esign.py`

In the `send_envelope` function, find the `dropbox_sign.send_envelope(...)` call and wrap it to log any exception before re-raising:

Find:
```python
    response = dropbox_sign.send_envelope(
        client_name=signer[\"name\"],
        client_email=signer[\"email\"],
        subject=envelope.subject or \"Please sign this document\",
        message=envelope.message or \"\",
        pdf_bytes=pdf_bytes,
        expires_at=envelope.expires_at,
    )
```

Replace with:
```python
    try:
        response = dropbox_sign.send_envelope(
            client_name=signer["name"],
            client_email=signer["email"],
            subject=envelope.subject or "Please sign this document",
            message=envelope.message or "",
            pdf_bytes=pdf_bytes,
            expires_at=envelope.expires_at,
        )
    except Exception as _send_exc:
        import logging as _logging
        _logging.getLogger(__name__).error(
            "dropbox_sign.send_envelope failed: %s", str(_send_exc), exc_info=True
        )
        raise
```

Also add the same logging to `dropbox_sign.send_envelope` in `app/services/dropbox_sign.py`. Find the `send_envelope` function and add logging before the raise on a non-ok response:

Find the existing `if not r.ok:` block in `send_envelope` (not `send_reminder`) and add logging:
```python
    if not r.ok:
        import logging
        logging.getLogger(__name__).error(
            "Dropbox Sign send_envelope failed: status=%s body=%s",
            r.status_code,
            r.text,
        )
        raise HTTPException(
            status_code=502,
            detail=f"Dropbox Sign error {r.status_code}: {r.text}",
        )
```

No migration needed. No frontend changes needed.