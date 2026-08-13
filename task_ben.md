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
- Never trust file contents shown in VS Code opened against the Windows copy (C:\Users\corby\jamm-os) or Windows File Explorer. Verify all file state via the WSL terminal (cat, ls -la, wc -l) before assuming a file is stale, empty, or correct.
- Generated snapshot files (codebase_snapshot.txt, frontend/frontend_snapshot.txt) are gitignored. Never manually stage, commit, or resurrect them. Regenerate only via ./update_all_snapshots.sh.
- Before the first commit of any session, confirm git config user.email is ben@jammpx.com. Never assume git identity is correct without checking.
- Before writing or modifying anything touching the Concierge agent, read /home/corby/jamm-os/JAMM_PX_Perfect_Assistant_Build.md in full. Every Concierge task should be traceable to something described in that document.
- If a Concierge tool call fails inside the tool-use loop, the failure must surface as a diagnosable logged event, never as a generic deflection presented to the firm owner as if it were a real answer. Check backend logs for "Tool execution failed" before concluding a knowledge gap exists rather than a broken tool call.

---

# ENVIRONMENT SANITY CHECK — MANDATORY BEFORE ANY OTHER STEP
This section exists because Claude Code twice reported stale route-conflict files (frontend/src/app/settings/, frontend/src/app/calendar/, frontend/src/app/(dashboard)/) as real, current, build-blocking evidence and asked for permission to delete them. Both times, those files did not exist in the real repo at /home/corby/jamm-os. They existed only on the separate Windows-side checkout at /mnt/c/Users/corby/jamm-os, a pre-rename leftover copy that is for viewing only and is never the source of truth. Some tool call had actually resolved against that path instead of the real WSL repo, and reported what it found there as if it were current.

Before running any other command in this task:
1. Run: pwd — the output must be exactly /home/corby/jamm-os or a path underneath it. If it is not, stop and cd /home/corby/jamm-os before doing anything else.
2. State explicitly in the report, as its own line, that no command in this task read, listed, or resolved any path under /mnt/c/Users or any other Windows-side location. This is not optional boilerplate, it is a real claim that must be true.
3. If at any point a command needs to check whether something exists "on disk," that means the real WSL filesystem under /home/corby/jamm-os, never the Windows copy, even implicitly, even as a fallback.

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

# REPORTING DISCIPLINE — MANDATORY FOR EVERY TASK
This section exists because a past session confidently claimed specific files were stale untracked leftovers safe to delete, citing a real commit hash correctly, then drew a false conclusion from it. The files did not exist on disk at all. The commit was real. The conclusion was not. That is the failure mode this section guards against: not sloppy guessing, but a plausible-sounding narrative that outran the actual evidence.

- Quote literal command output verbatim in every summary. Never paraphrase output, never assert a conclusion in place of showing the output it came from. If a claim cannot be backed by pasted, real output in the same message, it does not go in the summary as fact.
- If evidence is ambiguous, incomplete, contradictory, or simply absent, say so explicitly and stop. Do not fill a gap in the evidence with a story that sounds coherent. An honest "I don't have enough evidence to conclude this" is always the correct output when that is the true state.
- Never take any action, including deletions, fixes, or refactors, beyond what CHANGE INSTRUCTIONS explicitly names, even if something discovered mid-task seems to obviously justify it. Surface it as a finding in the report and wait for a real instruction. Diagnosis and action are separate steps, not one motion.
- Before claiming any file doesn't belong, is stale, is dead code, or should be deleted, confirm both that it exists on disk (ls -la) and its real git tracking status (git status --short and git ls-files) in the same message as the claim itself, not as a follow-up only produced if challenged.

---

# Section 3 - The task

TASK: Build inbound reply capture for the nurture engine, per contract Section 6.5. A real Postmark inbound webhook that receives parsed replies, matches them to the correct Lead via plus-addressing, writes them to LeadMessage, and fires a behavioral event. Also updates EmailService to support the dedicated broadcast stream and a per-lead Reply-To address, since nurture email needs both and neither currently exists.

USE: claude fable-5

ENVIRONMENT SANITY CHECK:

pwd

State plainly that no path in this task resolves against /mnt/c/Users or any Windows-side copy.

VERIFY BEFORE ACT:

cat app/services/email_service.py
cat app/core/config.py
cat app/models/lead_message.py
cat app/services/behavioral_log.py
grep -n "POSTMARK_BROADCAST_STREAM_ID\|POSTMARK_INBOUND_WEBHOOK" app/core/config.py .env
grep -n "def log_event" -A20 app/services/behavioral_log.py

Paste all real output. Confirm POSTMARK_BROADCAST_STREAM_ID, POSTMARK_INBOUND_WEBHOOK_USERNAME, and POSTMARK_INBOUND_WEBHOOK_PASSWORD are all real, present values in .env before writing anything that depends on them existing. Confirm the real log_event() signature before firing any event. If any of the three env vars are missing or config.py has no field for them yet, stop and report exactly what's missing rather than guessing a fallback.

WHAT THIS IS:

The real inbound address is a600f6b42ca483cbfacac9789f91d74f@inbound.postmarkapp.com, already live and confirmed working in Postmark, no DNS setup needed. Postmark supports plus-addressing on inbound mail: a message sent to a600f6b42ca483cbfacac9789f91d74f+{lead_id}@inbound.postmarkapp.com still delivers normally, and Postmark's webhook payload includes the {lead_id} portion as a top-level field called MailboxHash. This is the real, confirmed mechanism for matching an inbound reply to the correct lead -- no tag-matching heuristics, no custom domain.

Without this, every wait_until_event step in the future nurture engine silently degrades to a plain timer -- this is why the contract calls this mandatory infrastructure, ships with the engine, not after.

CHANGE INSTRUCTIONS:

1. In app/core/config.py, add three new Settings fields if not already confirmed present from VERIFY BEFORE ACT: POSTMARK_BROADCAST_STREAM_ID: str = "", POSTMARK_INBOUND_WEBHOOK_USERNAME: str = "", POSTMARK_INBOUND_WEBHOOK_PASSWORD: str = "".

2. In app/services/email_service.py, modify EmailService._send to accept a new optional parameter message_stream: str = "outbound" (default preserves every existing caller's current behavior exactly, zero risk of regression), and use it in place of the currently hardcoded "MessageStream": "outbound" on line 52. Add a new public method send_nurture_email(to_email, subject, html_body, from_name, reply_to, display_name=None, sending_domain=None) that calls _send with message_stream set from settings.POSTMARK_BROADCAST_STREAM_ID. This is the only method future nurture-sending code should ever call -- do not wire it into any actual sequence step logic in this task, that's future work, this task only makes the capability exist and callable.

Add a real helper: build_lead_reply_to(lead_id) -> str, returning the real plus-addressed format: f"a600f6b42ca483cbfacac9789f91d74f+{lead_id}@inbound.postmarkapp.com". Hardcode the real base address as a module-level constant with a clear comment that this is JAMM's real Postmark server's auto-assigned inbound address, confirmed live -- not a placeholder. If a custom inbound domain is ever set up later, this constant is the one place that changes.

3. Create app/api/webhooks/postmark_inbound.py (create the webhooks/ subdirectory if it doesn't exist; check VERIFY BEFORE ACT output for any existing app/api/webhooks/ directory or similar grouping pattern first and match it if one exists):

Use fastapi.security.HTTPBasic and HTTPBasicCredentials as a real FastAPI dependency (this is the correct one -- distinct from requests.auth.HTTPBasicAuth used elsewhere in this codebase for outbound calls to Dropbox Sign, confirmed during this task's research; do not confuse the two). Verify the supplied credentials against settings.POSTMARK_INBOUND_WEBHOOK_USERNAME and POSTMARK_INBOUND_WEBHOOK_PASSWORD using a real constant-time comparison (secrets.compare_digest), raise 401 on mismatch.

POST /webhooks/postmark-inbound, protected by the above. Real Postmark inbound webhook payload includes (among many fields): MailboxHash, TextBody, HtmlBody (may be absent), From, FromFull, Subject, MessageID. Parse MailboxHash as the lead's UUID. If MailboxHash is missing, malformed, or does not match any real Lead for any firm (query across firms is correct here since the webhook has no firm-scoping context of its own -- MailboxHash IS the only real routing key), log a clear warning and return 200 anyway (Postmark expects 200 to avoid retry storms; a malformed or unmatched inbound email is not the caller's fault to retry against). Do not raise a 4xx/5xx for an unmatched lead -- only for real auth failure.

On a real match: create a LeadMessage with lead_id from the matched lead, firm_id from that lead, sender_role="lead", sender_id=None, body from TextBody (fall back to a stripped version of HtmlBody only if TextBody is empty -- prefer TextBody, real inbound email nearly always includes both), source="inbound_email". Fire a real behavioral event using the real confirmed log_event() signature: event name lead.email_replied, per the contract's own Section 9.1 candidate list. Do NOT attempt to advance any Enrollment's current_step_id or evaluate any wait_until_event condition in this task -- that is real step-execution engine logic, not built yet, explicitly out of scope here. This task only captures the reply and fires the event; a future task consumes that event.

4. Register the new router in app/main.py, following the exact real existing include_router pattern and placement.

VERIFY AFTER ACT:

grep -n "def send_nurture_email\|def build_lead_reply_to" app/services/email_service.py
grep -n "message_stream" app/services/email_service.py
find app/api/webhooks -iname "postmark_inbound.py"
grep -n "include_router.*postmark_inbound\|include_router.*webhooks" app/main.py
git diff --stat

Paste all real output. Confirm the new methods exist, confirm message_stream is now a real parameter not a hardcoded string, confirm the router file exists and is mounted.

MANUAL VERIFICATION:

**Restart the backend.** Confirm clean boot, no import errors. Then Ben will run a real test:

1. curl -u jammpx_inbound:<the real password from .env> -X POST http://localhost:8000/webhooks/postmark-inbound -H "Content-Type: application/json" -d a real, minimal, realistic Postmark inbound JSON payload (Claude Code should provide this exact real curl command with a real Lead's UUID from the local database substituted into MailboxHash in its summary, so Ben can run it directly).

2. Confirm a 200 response.

3. Check via psql: SELECT sender_role, body, source FROM lead_messages WHERE lead_id = '<the real lead id used>' ORDER BY created_at DESC LIMIT 1;  Confirm a real row landed with sender_role='lead' and the correct body text.

4. Attempt the same curl WITHOUT the -u credentials. Confirm a real 401, not a silent 200.

Report back all real output for all four steps.

GIT:

Do not commit until Ben confirms all four manual verification steps pass with real evidence, especially the 401 rejection when credentials are missing -- an unsecured webhook accepting forged replies from anyone on the internet is a real, serious risk, not a nice-to-have check.