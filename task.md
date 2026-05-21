# JAMM PX — Quick Fix

Read every instruction in this file before writing a single line of code.

---

## TASK 1 — Fix webhook response for Dropbox Sign test

**File to edit:** `app/api/esign.py`

In the `handle_webhook` function, find the `callback_test` handler:
```python
if event_type == "callback_test":
    return {"status": "ok"}
```

Replace with:
```python
if event_type == "callback_test":
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse("Hello API Event Received")
```

Also find the final return at the bottom of the function:
```python
return {"status": "ok"}
```

Replace with:
```python
from fastapi.responses import PlainTextResponse
return PlainTextResponse("Hello API Event Received")
```

All webhook responses must return the plain text string `Hello API Event Received` — not JSON. Apply to every return in the webhook handler.