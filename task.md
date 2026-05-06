## Current Task — Replace AWS SES with Postmark for email sending

### Context
AWS SES production access was denied. Replacing with Postmark for all
transactional email. The existing email service is at app/services/email_service.py
and uses boto3/SES. Replace it entirely with the Postmark HTTP API.

Postmark API docs: https://postmarkapp.com/developer/api/email-api
The API key is in settings as POSTMARK_API_KEY.

### Step 1 — Read these files first

Read in full:
- app/services/email_service.py
- app/core/config.py

### Step 2 — Add POSTMARK_API_KEY to config

In app/core/config.py add:
    POSTMARK_API_KEY: str = ""

### Step 3 — Rewrite app/services/email_service.py

Replace the entire file with a Postmark implementation.

Use the requests library (already in requirements.txt) to call the
Postmark API directly — no SDK needed.

The Postmark API endpoint is:
POST https://api.postmarkapp.com/email

Headers required:
    Accept: application/json
    Content-Type: application/json
    X-Postmark-Server-Token: {POSTMARK_API_KEY}

Body format:
    {
        "From": "JAMM PX <noreply@jammpx.com>",
        "To": "recipient@example.com",
        "Subject": "Subject line",
        "HtmlBody": "<html>...</html>",
        "TextBody": "Plain text version",
        "MessageStream": "outbound"
    }

Preserve all existing public methods exactly — same method names,
same parameters, same behavior. Only the sending mechanism changes.
The methods to preserve are whatever exists in the current file.

If sending fails, log the error and raise an exception.
Never silently swallow send failures — the caller needs to know.

Add a _send() private method that handles the actual HTTP call and
error handling, then call it from each public method.

### Step 4 — Update requirements.txt

Check if requests is already in requirements.txt. If not, add:
    requests>=2.32.0

It is almost certainly already there — just confirm.

### Step 5 — Run pytest

Run: python -m pytest tests/ --tb=no -q

Report the summary line only. Confirm no new failures related to
email service.

### Step 6 — Report back

Paste:
- The full new email_service.py
- pytest summary line
- Confirm POSTMARK_API_KEY is in config.py