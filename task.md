# JAMM PX — Quick Fix

Read every instruction in this file before writing a single line of code.

---

## TASK 1 — Write webhook payload to file for debugging

**File to edit:** `app/api/esign.py`

In `handle_webhook`, immediately after `data` is parsed (after the multipart/form-data block), add:

```python
# DEBUG: write payload to file
try:
    import json as _json
    with open("/tmp/webhook_debug.json", "w") as _f:
        _json.dump(data, _f, indent=2, default=str)
except Exception:
    pass
```

This writes the raw parsed payload to `/tmp/webhook_debug.json` so we can see exactly what Dropbox Sign is sending. Remove after debugging.

No other changes.