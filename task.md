# JAMM PX — Quick Fix

Read every instruction in this file before writing a single line of code.

---

## TASK 1 — Log incoming webhook headers for debugging

**File to edit:** `app/api/esign.py`

In the `handle_webhook` function, before the signature check, add temporary logging to see what headers Dropbox Sign is actually sending:

Find:
```python
signature_header = request.headers.get("Hash")
if not signature_header:
    raise HTTPException(status_code=400, detail="Missing webhook signature")
```

Replace with:
```python
import logging as _logging
_logging.getLogger(__name__).warning(
    "Webhook headers: %s", dict(request.headers)
)
signature_header = request.headers.get("Hash")
if not signature_header:
    # Try alternate header names Dropbox Sign might use
    signature_header = (
        request.headers.get("X-HelloSign-Signature") or
        request.headers.get("X-Dropbox-Sign-Signature") or
        request.headers.get("x-hellosign-signature")
    )
if not signature_header:
    _logging.getLogger(__name__).warning(
        "Missing webhook signature. Headers received: %s", dict(request.headers)
    )
    raise HTTPException(status_code=400, detail="Missing webhook signature")
```

No other changes. No frontend changes.