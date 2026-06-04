# STANDING RULES
- All file operations use the absolute path /home/corby/jamm-os/. Never use /mnt/c/Users paths. Never use Windows-style paths.
- Never use relative paths. Always use full absolute paths starting with /home/corby/jamm-os/.
- Never use the built-in file read tool to inspect file contents. Always use bash: cat, grep, sed. The file read tool caches stale content. Trust bash output only.
- Path comment at top of every file
- Never use && to chain commands
- Always use SQLAlchemy 2.0 Mapped[] syntax. Never use Column() style.
- Always scope every database query to firm_id. No exceptions.
- Never put business logic in routers. Logic goes in services/ or crud/.
- Always use get_current_firm from app.dependencies.tenant for auth. Never read firm_id from the request body.
- Background tasks need their own SessionLocal() in a try/finally block. Never pass the request db session into a background task.
- List endpoints return { items: [], total: N }. Never a plain array.
- Never use em dashes anywhere in any string, copy, or comment.
- Always use "engagements" not "projects". Always use "magic-link" not "portal link". Always use "automation presets" not "automation rules".

---

# VERIFY BEFORE ACT — MANDATORY FOR EVERY TASK
Before making any change to any file:
1. Run: pwd — confirm output is /home/corby/jamm-os. If it is not, run: cd /home/corby/jamm-os
2. Run grep using the full absolute path and paste the full bash output:
   grep -n "pattern" /home/corby/jamm-os/path/to/file
3. If the pattern is not found, run:
   cat /home/corby/jamm-os/path/to/file | grep -c "pattern"
   Paste that result too.
4. If both return zero, STOP and report exactly what bash returned. Do not proceed. Do not guess. Do not find the closest match. Do not trust the file read tool.
5. Only proceed when bash grep with the absolute path confirms the pattern exists on disk.

This rule cannot be skipped. If the task says "find this pattern" and bash grep cannot find it, the task description is wrong — not the file. Stop and wait for updated instructions.

---

# VERIFY AFTER ACT — MANDATORY FOR EVERY CHANGE
After every file change:
- Run grep -n for the exact new string using the full absolute path and paste the full output
- Never report a fix as working without showing the bash grep output
- Never report a file as created without running ls -la and showing the output
- If grep does not confirm the change, fix it before moving to the next step
- Trust bash output only — never the file read tool

---

# MIGRATION PROCEDURE
Before every migration: run alembic current first.
After autogenerate: read the generated file before running upgrade head. If it touches tables you did not intend, delete it and write a manual migration.
If alembic current shows a revision but no tables exist: run alembic stamp base, then alembic upgrade head.

---

# PRE-TASK
cd /home/corby/jamm-os
source .venv/bin/activate
python3 -c "from app.api.concierge.route import router; print('OK')"
If the import fails, stop and report. Do not proceed.
git add -A
git commit -m "checkpoint before [task name]"

---

# POST-TASK — run after task completes
find /home/corby/jamm-os/app/api/concierge/ -name "*.py" | sort
ls /home/corby/jamm-os/migrations/versions/ | tail -5
python3 -c "from app.api.concierge.route import router; print('OK')"
find /home/corby/jamm-os/frontend/src/components/concierge/ -name "*.tsx" | sort

---

# Prompt audit: Add IRS Authorization workflow section

Task: Replace the thin IRS AUTHORIZATION data model entry with a full workflow section
that covers how to create, send, and manage IRS authorizations in JAMM PX.

VERIFY BEFORE ACT:
grep -n "IRS AUTHORIZATION\|8821 allows\|A client with no active" /home/corby/jamm-os/app/api/concierge/prompts.py

Paste before touching anything.

OLD:
IRS AUTHORIZATION
Tracks Form 8821 (Tax Information Authorization) and Form 2848 (Power of Attorney) for a client.
Fields: id, firm_id, client_id, form_type (8821 | 2848), status (pending_signature | active | expired | revoked), tax_years (JSON array), valid_from, valid_until, signature_envelope_id, signed_document_id.
8821 allows the firm to receive IRS transcripts. 2848 allows full representation before the IRS.
A client with no active IRS authorization cannot have a transcript requested on their behalf.

NEW:
IRS AUTHORIZATION
Tracks Form 8821 (Tax Information Authorization) and Form 2848 (Power of Attorney) for each client. A client can have one active 8821 and one active 2848 simultaneously. Both are independent records.

Form 8821 allows the firm to receive IRS transcripts and account information on behalf of the client. Use this for tax prep and transcript requests.
Form 2848 gives the firm full Power of Attorney to represent the client before the IRS. Use this for audits, appeals, and collection matters.

A client with no active IRS authorization cannot have a transcript requested on their behalf inside JAMM PX.

How to send an IRS authorization:
1. Navigate to Clients and open the client record.
2. Select the IRS Authorizations tab.
3. Select Send Authorization.
4. Choose the form type: 8821 or 2848.
5. Enter the tax years the authorization should cover.
6. Set the valid from and valid until dates.
7. Select Send. JAMM PX generates a stub PDF and sends it to the client for signature via Dropbox Sign.

What happens after Send:
JAMM PX generates a pre-filled stub PDF containing the client and firm details, uploads it to secure storage, and creates a signature envelope. If Dropbox Sign is connected, the client receives an email with a link to sign electronically. If Dropbox Sign is not connected, the envelope stays in draft status and the firm must collect a manual signature and attach it to the record.

Authorization statuses:
- pending_signature: the form has been sent and is waiting for the client to sign
- active: the client has signed and the authorization is in effect
- expired: the valid_until date has passed
- revoked: the authorization was manually revoked

Expiry alerts:
JAMM PX automatically checks for authorizations expiring within 30 days and fires a proactive alert. The firm does not need to track expiry dates manually.

Common questions:
Q: Can I add both an 8821 and a 2848 for the same client?
A: Yes. They are separate records and can both be active at the same time.

Q: What if the client's email is not on file?
A: The signature envelope will be created but the email cannot be sent. Add the client's email address to their record first, then send the authorization.

Q: How do I know when the client has signed?
A: The authorization status changes from pending_signature to active automatically once the client signs via Dropbox Sign. The IRS Auth badge on the client record updates immediately.

Q: What if Dropbox Sign is not connected?
A: The authorization record is created but the envelope stays in draft. Connect Dropbox Sign under Settings, then resend the authorization.

Do not change anything else.

VERIFY AFTER ACT:
1. grep -n "IRS AUTHORIZATION\|pending_signature\|Dropbox Sign\|Power of Attorney" /home/corby/jamm-os/app/api/concierge/prompts.py
   Confirm all four present in the new section.
2. Restart the backend.
3. Browser test: ask "how do I send an IRS authorization to Patricia Nguyen".
   Confirm: response gives exact steps with correct UI labels, mentions Dropbox Sign, no hallucinated fields.