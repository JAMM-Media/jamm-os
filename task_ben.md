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

TASK: Build the LeadMessage model -- a thread of messages attached to a Lead, closely following the real, existing ClientMessage pattern. This closes a real gap flagged twice tonight: both inbound reply capture (contract Section 6.5) and the future lead detail view (Section 7.3) need a thread to attach to, and none exists yet.

USE: claude sonnet

ENVIRONMENT SANITY CHECK:

pwd

State plainly that no path in this task resolves against /mnt/c/Users or any Windows-side copy.

VERIFY BEFORE ACT:

cat app/models/message.py
cat app/schemas/message.py
cat app/models/lead.py
.venv/bin/alembic heads

Paste all real output. Confirm the real current alembic head fresh, live -- do not trust any hash written in this task's own text.

WHAT THIS IS:

ClientMessage has no separate Thread table -- client_id itself IS the thread, identified by firm_id + client_id together. LeadMessage follows the exact same shape: lead_id itself is the thread. Unlike ClientMessage, do NOT build a read-receipts table in this task -- the contract's Section 6.5 only requires that inbound replies attach to the lead thread and fire a behavioral event; nothing requires staff read-state tracking on lead messages, and adding it now would be scope the contract never asked for.

sender_role uses "staff" or "lead" as its two real values, matching the exact real vocabulary convention already established by ClientMessage's "staff"/"client" pair (confirmed in VERIFY BEFORE ACT and via prior grep across app/crud/message.py, app/services/message_service.py, app/api/portal.py). sender_id is nullable and null when the sender is the lead/prospect themselves, exactly matching how ClientMessage handles the client side (a prospect has no User account, same reasoning that already justifies ClientMessage.sender_id being nullable for the client side).

CHANGE INSTRUCTIONS:

1. Create app/models/lead_message.py:

class LeadMessage(Base):
    __tablename__ = "lead_messages"
    id: UUID pk, default uuid4
    firm_id: FK firms.id, CASCADE, nullable=False, indexed
    lead_id: FK leads.id, CASCADE, nullable=False, indexed
    sender_id: FK users.id, ondelete SET NULL, nullable=True -- null when sender_role is "lead"
    sender_role: String(30), nullable=False -- "staff" or "lead"
    body: Text, nullable=False
    source: String(30), nullable=True -- e.g. "inbound_email", "staff_note", "form_reply" -- freeform for now, populated by whichever future capture mechanism creates the row; not enforced as an enum since the real full set of sources is not yet finalized
    is_deleted: Boolean, nullable=False, default=False, server_default="false" -- matching ClientMessage's exact real pattern
    created_at: DateTime(timezone=True), server_default=func.now(), default lambda pattern, nullable=False -- matching ClientMessage's exact real pattern including the server_default

    Composite index matching ClientMessage's exact real pattern: Index("ix_lead_messages_firm_lead", "firm_id", "lead_id")

    Relationships: sender: relationship("User", foreign_keys=[sender_id]) -- matching ClientMessage exactly. Also add messages: relationship("LeadMessage", back_populates="lead") -- wait, correct this: add a lead relationship on LeadMessage pointing back to Lead, and add the reverse messages relationship on Lead itself in app/models/lead.py, following the exact real relationship pattern Lead already uses for enrollments (added earlier tonight).

2. Write ONE Alembic migration creating lead_messages with the composite index. Get the real fresh alembic head from VERIFY BEFORE ACT, do not trust any hash in this text -- this exact mistake has happened multiple times tonight.

3. Create app/schemas/lead_message.py with LeadMessageOut only (read-only, from_attributes=True) -- no Create/Update schema. Matching the exact real security reasoning already documented in app/schemas/message.py: sender_id and sender_role must be injected server-side by whichever future function creates a row (a staff-compose endpoint, the future Postmark inbound webhook), never accepted directly from a request body. Building a generic LeadMessageCreate schema now would invite exactly the mistake that comment in message.py exists to prevent. No CRUD functions beyond a bare get_messages_for_lead(db, lead_id, firm_id) -> list[LeadMessage] ordered by created_at. No API router, no message-creation logic, no Postmark integration in this task -- data layer only.

VERIFY AFTER ACT:

.venv/bin/alembic heads
.venv/bin/alembic upgrade head

PGPASSWORD=postgres psql -h localhost -U postgres -d jammpx_dev -c "\d lead_messages"

git diff --stat

Paste all real output. Confirm the real table shape matches ClientMessage's pattern minus read receipts, confirm the composite index exists, confirm single clean alembic head and clean upgrade.

MANUAL VERIFICATION:

**Restart the backend.** Confirm clean boot, no import errors.

GIT:

Do not commit until Ben confirms clean backend boot and the real table shape confirmed via psql.