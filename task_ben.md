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

TASK: Add a real Terms and Conditions gate to Peer Network, blocking first access until accepted, per spec section 11, which the app currently does not enforce at all despite two real accounts already having posted messages tonight with zero gate in front of them.

USE: claude fable-5

ENVIRONMENT SANITY CHECK:

pwd

State plainly that no path in this task resolves against /mnt/c/Users or any Windows-side copy.

VERIFY BEFORE ACT:

.venv/bin/alembic heads

grep -n -B 3 -A 30 "class PeerNetworkMember" app/models/peer_network.py

grep -n -B 5 -A 20 "def get_active_member" app/services/peer_network_service.py

Confirm exactly one alembic head. Confirm the real current PeerNetworkMember fields. Confirm the real get_active_member function, since this is the real single choke point every existing endpoint already calls to check access, and the terms gate needs to hook into this same function rather than duplicating the check elsewhere.

WHAT THIS IS, PER THE LOCKED SPEC SECTION 11:

Terms must be accepted before first access, and must cover at minimum: members are responsible for what they share about themselves and their firms; client-identifying information must never be posted; the room is pseudonymous, not anonymous, and handles persist; other members may include firms in the same geographic market who may recruit staff or compete for clients; grounds for muting and that mutes are permanent pending appeal; messages persist after a member or firm leaves the platform; screenshots publish your own private labels, since a member who screenshots the room exposes the names they have attached to other members, not just the message text; JAMM may remove any message.

The real proposed endpoint from spec section 15 is POST /cooperative/accept-terms, which under tonight's rename becomes POST /peer-network/accept-terms.

CHANGE INSTRUCTIONS:

Add a terms_accepted_at column to PeerNetworkMember (DateTime, timezone=True, nullable=True). Write the migration by hand, matching tonight's established real structure, down_revision set to the real current head confirmed above.

Add POST /peer-network/accept-terms, gated by real active PeerNetworkMember status via get_active_member. Sets terms_accepted_at to now for the calling user's own member record. Idempotent, if already accepted, do not error, just confirm accepted.

Modify get_active_member (or add a real, explicit check in each endpoint that currently calls it, whichever is the correct single choke point per the real code confirmed above) so that GET and POST on messages, reactions, and any other real content-producing or content-reading endpoint require terms_accepted_at to be non-null, returning a real, distinct 403 with a clear detail message like "Terms and conditions must be accepted before accessing the Peer Network." Opting in and granting access (POST /opt-in, POST /members/{id}/grant) should NOT require terms acceptance themselves, since a member cannot accept terms before they have a member record to accept them on, but every real content endpoint after that point should.

On the frontend, when the access-gate check (already built tonight, the real membership check on page load) reveals the user has active membership but has not yet accepted terms (a new real 403 reason distinguishable from "no membership at all"), show a real terms modal, not the existing owner-opt-in or non-owner-explanation gates. The modal must contain real, complete text covering all 8 real points from the spec listed above, written in plain, direct language, not placeholder text, with a single "I Understand and Agree" button that calls the new accept-terms endpoint, then reloads the real message feed on success.

VERIFY AFTER ACT:

grep -n "terms_accepted_at" app/models/peer_network.py

grep -n "POST.*accept-terms\|accept_terms" app/api/peer_network.py

.venv/bin/alembic heads

This must show exactly one head, the new migration's revision id. Run .venv/bin/alembic upgrade head and confirm it applies with no errors.

cd /home/corby/jamm-os
python3 -c "from app.main import app; print('app imports cleanly')"

cd frontend
npm run build

MANUAL VERIFICATION:

Restart both the backend and the frontend, since this touches both. Using a real token for a user who already has active membership from tonight's testing but has never accepted terms (their terms_accepted_at should be null after the migration adds the column, since it's a new column with no historical value to backfill), confirm GET /peer-network/rooms/{room_id}/messages now returns a real, distinct 403 for terms-not-accepted, not the old membership-based 403. Call POST /peer-network/accept-terms with that same real token, confirm success. Call the messages endpoint again with the same token, confirm it now succeeds. In the real browser, log in as that same user, navigate to Peer Network, confirm the real terms modal appears with the actual full text, not a placeholder, click through it, confirm the real message feed then loads normally. Report every real response and a screenshot of the modal.

GIT:

Do not commit until Ben confirms the real terms modal text and flow work correctly in the browser.