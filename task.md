# JAMM PX — Quick Fix

Read every instruction in this file before writing a single line of code.

---

## TASK 1 — Add event type logging to webhook handler

**File to edit:** `app/api/esign.py`

In `handle_webhook`, after `event_type = event.get("event_type")` is set, add:

```python
import logging as _logging
_logging.getLogger(__name__).warning(
    "Webhook received: event_type=%s signature_request_id=%s",
    event_type,
    data.get("signature_request", {}).get("signature_request_id", "none"),
)
```

Also after the `if envelope is None` check, add:

```python
_logging.getLogger(__name__).warning(
    "Webhook envelope lookup: provider_id=%s found=%s status=%s signed_doc_id=%s",
    signature_request_id,
    envelope is not None,
    envelope.status if envelope else "n/a",
    envelope.signed_document_id if envelope else "n/a",
)
```

No other changes. No frontend changes.