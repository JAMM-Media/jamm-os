# JAMM PX — Quick Fix

Read every instruction in this file before writing a single line of code.

---

## TASK 1 — Fix get_settings name in webhook handler

**File to edit:** `app/api/esign.py`

In the `handle_webhook` function, find:
```python
settings = get_settings()
secret = settings.DROPBOX_SIGN_API_KEY.encode()
```

Replace with:
```python
settings = _get_settings()
secret = settings.DROPBOX_SIGN_API_KEY.encode()
```

That is the only change. `_get_settings` is the aliased import already at the top of the file.