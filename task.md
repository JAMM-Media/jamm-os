# JAMM PX — Quick Fix

Read every instruction in this file before writing a single line of code.

---

## TASK 1 — Add test_mode flag to Dropbox Sign send_envelope

**File to edit:** `app/services/dropbox_sign.py`

In the `send_envelope` function, find where the multipart form data is built and sent. It posts to `{_BASE_URL}/signature_request/send`. 

Find the `data` dict or the `requests.post` call that sends the signature request. Add `"test_mode": "1"` to the data payload so Dropbox Sign processes the request without requiring a paid API plan.

Read the current `send_envelope` function carefully first, then add `"test_mode": "1"` to whatever dict is being posted as form data.

Also add a comment: `# test_mode=1 — remove this line when upgrading to a paid Dropbox Sign API plan`

No migration needed. No frontend changes needed.