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

TASK: Add real partial mute to Peer Network, per Ben's explicit decision: a muted member can still read the room, but is blocked from posting new messages, per spec sections 9 and 10. This is genuinely separate from is_active (which represents "has real membership at all"), reusing it would incorrectly collapse two different real states into one.

USE: claude fable-5

ENVIRONMENT SANITY CHECK:

pwd

State plainly that no path in this task resolves against /mnt/c/Users or any Windows-side copy.

VERIFY BEFORE ACT:

.venv/bin/alembic heads

grep -n -B 3 -A 25 "def post_message" app/api/peer_network.py

grep -n -B 3 -A 20 "def get_active_member" app/services/peer_network_service.py

Confirm exactly one alembic head. Confirm the real current post_message endpoint and get_active_member function before adding a separate, real mute check to the write path only, leaving the read path completely untouched.

WHAT THIS IS, PER THE LOCKED SPEC:

Mutes are permanent pending manual appeal. The mute notice must state the specific T&C clause violated (spec section 9's real list: personal responsibility, no client-identifying information, pseudonymous not anonymous, other members may be competitors, permanent mutes pending appeal, messages persist after departure, screenshots expose private labels, JAMM may remove any message) and include a real appeal email address, since a muted member cannot message the team in-product. Muting is a real, separate state from is_active: is_active gates all access (read and write) and currently has no revoke path; mute specifically blocks only posting, confirmed by Ben's real decision, while reading stays open.

CHANGE INSTRUCTIONS:

Add to PeerNetworkMember: is_muted (Boolean, default False, nullable False), muted_reason (String, nullable, the specific T&C clause text), muted_at (DateTime with timezone, nullable), muted_by (UUID, ForeignKey users.id, ondelete SET NULL, nullable, the real system_admin who muted them).

Write the migration by hand, matching tonight's established real structure, down_revision set to the real current head confirmed above.

Add POST /peer-network/admin/members/{member_id}/mute, gated require_system_admin, accepting {reason: str} (the specific T&C clause text, required, not optional, since the spec is explicit a mute notice must cite a specific clause). Sets is_muted True, muted_reason to the provided reason, muted_at to now, muted_by to the calling admin's own user id.

Add POST /peer-network/admin/members/{member_id}/unmute, gated require_system_admin, sets is_muted False, clears muted_reason/muted_at/muted_by back to null/None, representing a real manual appeal reinstatement per spec ("a member who explains and acknowledges can be reinstated").

In post_message specifically, after the existing get_active_member call (which stays completely unchanged, still only checking is_active, still gating read access the same way it always has), add a new, separate check: if member.is_muted is True, raise a real 403 with a clear detail message including the real muted_reason and a real placeholder appeal email, appeals@jammpx.com, flagged in code with a comment that this is a placeholder pending a real support inbox. Do not add this check to list_messages or any read-path endpoint, reading must stay completely open for a muted member per Ben's real decision.

Add is_muted and muted_reason to the response of GET /peer-network/rooms (or wherever real membership state is already exposed to the frontend, matching the existing has_posted pattern from earlier tonight), so the frontend can show the real mute state without needing a separate call.

On the frontend, when the user's own membership state shows is_muted true, replace the normal compose box with a real, clear message showing the specific reason and the real appeal email, instead of a functioning send button. Do not hide the message feed itself, since reading stays open.

VERIFY AFTER ACT:

grep -n "is_muted\|muted_reason\|muted_at\|muted_by" app/models/peer_network.py

grep -n "admin/members.*mute" app/api/peer_network.py

.venv/bin/alembic heads

This must show exactly one head, the new migration's revision id. Run .venv/bin/alembic upgrade head and confirm it applies with no errors.

cd /home/corby/jamm-os
python3 -c "from app.main import app; print('app imports cleanly')"

cd frontend
npm run build

MANUAL VERIFICATION:

Restart both the backend and the frontend. Using the real system_admin token created earlier tonight (testadmin@jammpx.com), mute a real test member (use the manager account, ca968bf9-12a6-41d9-af45-1a52dc477da2, or james, 0e5754bd-612f-4fdc-b276-17e86d5890c7, whichever has a real peer network membership already) with a real reason citing one of the actual spec clauses. Confirm the response succeeds. As that muted user, call GET /peer-network/rooms/{room_id}/messages, confirm it still succeeds (reading stays open). Attempt POST /peer-network/rooms/{room_id}/messages as that same muted user, confirm a real 403 with the real reason and appeal email in the response, not a generic error. Unmute them via the real admin endpoint, confirm posting works again afterward. As a non-admin (owner or manager), attempt to call the mute endpoint directly, confirm a real 403. Report every real response.

GIT:

Do not commit until Ben confirms every real check above with actual API responses, not a description.