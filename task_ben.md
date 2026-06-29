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

# Section 3 - The task

# Task: Correct stale Signature Envelope navigation instructions that describe a non-existent Signatures tab

USE: claude sonnet

## VERIFY BEFORE ACT

sed -n '599,613p' /home/corby/jamm-os/app/api/concierge/prompts.py

Confirm the current 7-step "How to send a signature envelope" instructions, which describe navigating to Clients > [Client Name] > Engagements > [Engagement Name] > Signatures tab > New Signature Request, with manual signer name/email entry, a subject line, and an optional message.

## WHAT IS WRONG

Confirmed via direct live verification: there is no Signatures tab anywhere on an engagement detail page. The actual engagement tabs are Overview, Tasks, QC Checklist, and Documents only. The real signature-sending mechanism is the "Send Engagement Letter" button on the engagement detail page, which opens a modal with two tabs (Use a Template, Upload Your Own PDF), auto-populated client/engagement/date/deadline fields, a required Letter Template or PDF upload, a required Fee Amount, and a "Send for Signature" button. There is no manual signer name/email entry step, no subject line field, and no separate message field in the real flow -- the signer is implicitly the client on the engagement.

This is not a missing feature, it is incorrect existing documentation describing a flow that does not exist in the app, likely written in anticipation of a more generic feature that was replaced by the simpler engagement-letter-specific flow that was actually built. Giving the agent this wrong navigation path would send a firm owner looking for a tab that does not exist.

## ACTION

File: /home/corby/jamm-os/app/api/concierge/prompts.py

Replace the "How to send a signature envelope" section (the 7 numbered steps) with the real flow:

How to send an engagement letter for signature:
1. Navigate to Clients > [Client Name] > Engagements > [Engagement Name].
2. Select the Send Engagement Letter button at the top of the engagement detail page.
3. Choose either Use a Template or Upload Your Own PDF.
4. If using a template, select a Letter Template from the dropdown. If no templates exist yet, create one first under Templates > Engagement Letters. If uploading a PDF, select the file to upload.
5. Enter the Fee Amount.
6. Select Send for Signature. The client receives an email from Dropbox Sign with a link to review and sign.
Client, engagement, date, and deadline fields are auto-populated from the engagement and cannot be edited in this modal.

Keep the existing Statuses line, the Reminders line, the Dropbox Sign connection requirement line, and the entire signature_envelope_qa block exactly as they are, since those describe lifecycle concepts that remain accurate regardless of the specific UI path used to create one. Only the 7-step navigation instructions are being replaced.

Also check whether the existing signature_envelope_qa entries reference "the envelope detail view" for resending or cancelling -- if there is no separate envelope detail view in the real app (only the Dashboard Awaiting Signature panel and the engagement detail page itself), note this in your verify-after output rather than silently leaving those Q&A answers referencing a view that may not exist. Do not change those Q&A entries without first confirming whether a detail view genuinely exists; report this as a finding if you cannot confirm it from the codebase alone.

Do not change anything else in this file.

## VERIFY AFTER ACT

grep -n "Send Engagement Letter button" /home/corby/jamm-os/app/api/concierge/prompts.py

Expected: present.

grep -n "Signatures tab" /home/corby/jamm-os/app/api/concierge/prompts.py

Expected: no longer present.

python3 -c "from app.api.concierge.route import router; print('OK')"

Expected: OK, no import errors.

## MANUAL VERIFICATION

1. Restart the backend.
2. Ask the Concierge: "how do I send this engagement letter for signature?" while viewing an engagement.
3. Confirm the response describes the real Send Engagement Letter button and modal flow, not a Signatures tab.

Report the exact response text at step 3, and report explicitly what was found regarding the "envelope detail view" question above.

## GIT

cd /home/corby/jamm-os
git add -A
git commit -m "fix: correct stale signature envelope navigation instructions describing a non-existent Signatures tab, replaced with the real Send Engagement Letter button and modal flow"
git pull --rebase origin main
git push origin main

If conflicts on task.md use --theirs. Conflicts on source files use --ours.