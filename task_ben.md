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

TASK: Build the suppression list and unsubscribe mechanism for the nurture engine, per contract Section 6.6. Legally required before any real nurture email can send -- CAN-SPAM requires a working unsubscribe link in every marketing send, and a suppression list the engine checks before every send.

USE: claude fable-5

ENVIRONMENT SANITY CHECK:

pwd

State plainly that no path in this task resolves against /mnt/c/Users or any Windows-side copy.

VERIFY BEFORE ACT:

cat app/services/portal_magic_link.py
cat app/models/portal_session.py
cat app/models/enrollment.py
grep -n "class EnrollmentStatus" -A10 app/core/enums.py
.venv/bin/alembic heads

Paste all real output. Confirm the real token generate/hash/verify pattern from portal_magic_link.py before copying it. Confirm the real fresh alembic head, live -- do not trust any hash written in this task's own text, this exact mistake has happened multiple times tonight.

WHAT THIS IS:

Two genuinely separate mechanisms working together:

1. SuppressedEmail -- a permanent, firm-scoped table of email addresses that must never receive nurture mail. Checked by plain email lookup before every nurture send (that check itself is future step-execution logic, NOT built in this task -- this task only builds the table and the lookup function it will call).

2. An unsubscribe token tied to one specific Enrollment -- generated once per enrollment (or regenerated as needed), following the EXACT real pattern already proven in portal_magic_link.py: secrets.token_hex(32) for the raw token, only the SHA-256 hash ever stored, the raw value only exists transiently to embed in an email link. Clicking the resulting link (no login required, matching the magic-link precedent of a safe unauthenticated action gated by an unguessable hashed token) does three real things together: adds the enrollment's lead's email to SuppressedEmail for that firm, sets the enrollment's status to EnrollmentStatus.unsubscribed (this value already exists, added earlier tonight), and fires a real behavioral event.

CHANGE INSTRUCTIONS:

1. Create app/models/suppressed_email.py:

class SuppressedEmail(Base):
    __tablename__ = "suppressed_emails"
    id: UUID pk, default uuid4
    firm_id: FK firms.id, CASCADE, nullable=False, indexed
    email: String(255), nullable=False -- store lowercased, normalize in the CRUD layer, not the DB
    reason: String(50), nullable=True -- freeform for now, e.g. "unsubscribed", "bounced" (bounced is not built in this task, just leaving room)
    suppressed_at: DateTime(timezone=True), default lambda pattern, nullable=False
    Add a real unique constraint on (firm_id, email) -- an email is either suppressed for a firm or it isn't, no duplicate rows.

2. Add unsubscribe_token_hash: String(64), nullable=True, indexed and unsubscribe_token_expires_at: DateTime(timezone=True), nullable=True to the EXISTING Enrollment model in app/models/enrollment.py. Nullable because not every enrollment necessarily has an active unsubscribe link generated at every moment -- generation is a real operation, not automatic on enrollment creation, and that generation operation is NOT built in this task (it belongs with the future step-execution engine, which is what will actually construct and send emails). This task only adds the columns and the verification logic that CONSUMES a token once one exists.

3. Write ONE Alembic migration: create suppressed_emails with its unique constraint, add the two new columns to enrollments. Get the real fresh alembic head from VERIFY BEFORE ACT.

4. Create app/crud/suppressed_email.py:
   - is_suppressed(db, firm_id, email) -> bool -- the real lookup function future send-time code will call. Normalize email to lowercase before comparing.
   - add_suppression(db, firm_id, email, reason=None) -> SuppressedEmail -- real upsert-safe logic: if the (firm_id, email) pair already exists, do nothing and return the existing row rather than raising an IntegrityError on the unique constraint. This matters because a lead could click an unsubscribe link twice, or unsubscribe through two different enrollments with the same email.

5. Create app/services/unsubscribe_service.py, following the exact real hash/verify pattern from portal_magic_link.py:
   - verify_and_process_unsubscribe(db, raw_token) -> bool -- hash the incoming raw token with SHA-256, look up the Enrollment by unsubscribe_token_hash, check unsubscribe_token_expires_at has not passed. If not found or expired, return False (do not raise -- an expired or invalid unsubscribe link should show a plain "this link is no longer valid" state, not crash). If found and valid: call add_suppression for that enrollment's lead's email under that enrollment's firm_id, set the enrollment's status to EnrollmentStatus.unsubscribed and stopped_at to now, clear unsubscribe_token_hash and unsubscribe_token_expires_at (single-use, matching the real magic-link precedent of tokens not being reusable after their purpose is served), commit, fire a real behavioral event using the real confirmed log_event() signature -- event name lead.unsubscribed (not in the contract's Section 9.1 candidate list verbatim, but consistent with its naming convention; note this plainly in your summary as a task-introduced event name Andrew should bless alongside the others before deploy). Return True.

6. Create app/api/unsubscribe.py: GET /unsubscribe/{token}, fully public, no auth dependency of any kind (matching the intake form and inbound webhook's real precedent of genuinely public endpoints elsewhere in this codebase). Calls verify_and_process_unsubscribe. Return a simple real response indicating success or an already-invalid/expired state -- this is a backend-only task, no frontend page in this task; a plain JSON response is sufficient for now, a real frontend confirmation page is future work, flag this plainly rather than silently building UI as scope creep.

Register the new router in app/main.py, following the exact real existing include_router pattern.

Do NOT build the token-generation function that creates a fresh unsubscribe token for an enrollment in this task -- that's tightly coupled to the future step-execution engine's email-sending logic (a token should be generated at the moment an email is actually about to send, not speculatively ahead of time). This task only builds what happens when an already-generated token is used.

VERIFY AFTER ACT:

.venv/bin/alembic heads
.venv/bin/alembic upgrade head

PGPASSWORD=postgres psql -h localhost -U postgres -d jammpx_dev -c "\d suppressed_emails"
PGPASSWORD=postgres psql -h localhost -U postgres -d jammpx_dev -c "\d enrollments" | grep unsubscribe

git diff --stat

Paste all real output. Confirm the real table shape, confirm the unique constraint, confirm the two new columns landed on enrollments, confirm single clean alembic head and clean upgrade.

MANUAL VERIFICATION:

**Restart the backend.** Confirm clean boot, no import errors. Then Ben will run a real test. Claude Code must provide the EXACT real SQL and curl commands in its summary, using a real enrollment row -- since no enrollment currently has an unsubscribe_token_hash set (nothing generates one yet), Ben will need to manually set one via a real UPDATE statement first, using a real raw token and its real SHA-256 hash that Claude Code computes and provides explicitly (do not make Ben compute a hash by hand -- provide the exact real python3 -c command to generate a matching raw-token/hash pair together).

Real test sequence Claude Code must lay out explicitly:
1. Generate a real raw_token and its real sha256 hash together (paired, not independently generated).
2. UPDATE a real enrollment row, setting unsubscribe_token_hash to the real hash and unsubscribe_token_expires_at to a future timestamp.
3. GET /unsubscribe/{raw_token} -- the RAW token, never the hash, in the URL.
4. Confirm via psql: the enrollment's status is now unsubscribed, stopped_at is set, unsubscribe_token_hash is now null.
5. Confirm via psql: a real row exists in suppressed_emails for that lead's email under the correct firm_id.
6. Hit the SAME URL a second time. Confirm it now returns the invalid/expired state, not a second success -- proving the token is genuinely single-use.

CRITICAL SECURITY REMINDER FOR THIS TASK'S SUMMARY: do not print any real generated token, hash, or credential value directly in your summary text where Ben would need to paste it back into this chat for confirmation. Provide the exact commands Ben should run himself in his own terminal to generate and use these values locally, and ask Ben to confirm success by describing the RESULT (e.g. "the psql query showed status=unsubscribed"), not by pasting the raw token or hash itself back into this conversation. This is a real, repeated pattern from tonight -- three separate credential leaks already happened this session because task summaries printed real secret values in plaintext.

GIT:

Do not commit until Ben confirms all six real verification steps pass, described by their results, not by pasting any raw token or hash value into this chat.

MANUAL VERIFICATION NOTE FOR BEN: when Claude Code gives you the token-generation command, run it yourself and keep the output in your own terminal. When you report back here, describe what happened rather than pasting the actual token or hash.