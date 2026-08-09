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

TASK: Add @mentions to Peer Network, per spec section 4's explicit hard requirement: a mention must be stored as a reference to the real member, never as literal text, and resolved per-viewer at render time, mirroring the exact same mechanism already proven safe tonight for author_display. Autocomplete searches only the composing member's own private aliases (never a general directory), falling back to handle search for anyone unlabeled, per the real spec text confirmed just now.

USE: claude fable-5

ENVIRONMENT SANITY CHECK:

pwd

State plainly that no path in this task resolves against /mnt/c/Users or any Windows-side copy.

VERIFY BEFORE ACT:

.venv/bin/alembic heads

grep -n -B 3 -A 30 "def list_messages" app/api/peer_network.py

grep -n -B 3 -A 15 "class PeerNetworkAlias" app/models/peer_network.py

Confirm exactly one alembic head. Confirm the real current list_messages implementation (already resolving author_display via a real per-viewer alias lookup, the exact pattern mentions must reuse) and the real PeerNetworkAlias model.

WHAT THIS IS, PER THE LOCKED SPEC SECTIONS 4 AND 7:

A mention is composed by picking a real member, but what gets stored in the message body is a neutral reference token, never the literal alias text the composer saw on screen, since storing literal text would leak the composer's own private label for that person to every other viewer in the room, the exact deanonymization risk local aliases were built tonight specifically to prevent. At read time, each viewer's own alias for the mentioned member (or the real handle, if unlabeled) gets substituted in, per viewer, reusing the exact same resolution mechanism already proven correct for author_display, not a new, separate system.

Autocomplete when composing searches only the composing member's own real aliases (a private list only they have access to), falling back to real handle search for anyone unlabeled. This is explicitly not a member directory or general user search, which remain correctly out of scope per section 12, since a member can only be found this way if the composer already personally knows them by alias or already knows their exact handle.

Mentioned members get notified per spec section 8 ("@mention: notifies the mentioned member"), the only real-time notification the main room ever sends, since ordinary main-room messages deliberately notify nobody.

CHANGE INSTRUCTIONS:

Add a mentions column to PeerNetworkMessage: a JSON or ARRAY column storing a list of real target member UUIDs, matching the real proposed message shape from spec section 15. This is the queryable record of who was mentioned, never the source of truth for what displays in the body text.

Design the real token format for embedding a mention reference inside the message body text itself: use something unambiguous and unlikely to collide with real user text, for example @[member_id] using the real UUID, or a simpler bracketed reference like @{member_id}. Pick whichever is cleaner to parse reliably with a real regex, and use it consistently in both the compose-side encoding and the render-side decoding.

Add GET /peer-network/aliases, gated by real active membership, returning the calling member's own complete list of aliases they've personally set (target_member_id and label for each), the real new endpoint needed for autocomplete, since no such bulk listing endpoint currently exists.

In post_message, parse the real mention tokens out of the submitted body, extract the real target member IDs, validate each one is a real, currently active PeerNetworkMember (silently drop any that aren't, do not error the whole message over one invalid mention), and store the validated list in the new mentions column.

In list_messages (and any other real place a message body currently gets returned to a client), after resolving author_display exactly as already done, also parse and resolve any mention tokens in the body text into real per-viewer display text: for each real token found, look up whether the calling viewer has a real alias for that target member (reusing the same real alias-lookup query pattern already proven correct for author_display, do not write a second, different lookup mechanism), and substitute in either their real alias, or the target's real handle if unlabeled. The raw body sent to the database must never leak the mention token format to the client unresolved, every client-facing response must show real, human-readable resolved text.

On the frontend, wire a real @mention popover into the compose textarea: typing @ followed by characters searches the real GET /peer-network/aliases list first (matching against each alias's label), falling back to a real handle search if provided (check whether a real handle-search backend capability already exists or needs a small addition, report which). Selecting a real match inserts the correct token format into what actually gets sent on send, while displaying the person's real, familiar alias text to the composer as they type, not the raw token. Rendered messages in the feed must show the same real resolved-mention text, styled distinctly (bold or a subtle background, matching the existing app conventions), not the raw token format, ever.

VERIFY AFTER ACT:

grep -n "mentions" app/models/peer_network.py

grep -n "GET.*aliases\|def list_my_aliases" app/api/peer_network.py

.venv/bin/alembic heads

This must show exactly one head, the new migration's revision id. Run .venv/bin/alembic upgrade head and confirm it applies with no errors.

cd /home/corby/jamm-os
python3 -c "from app.main import app; print('app imports cleanly')"

cd frontend
npm run build

MANUAL VERIFICATION:

Restart both the backend and the frontend. Using two real accounts that already have a real alias relationship from earlier tonight (the owner has aliased the manager, or James, confirm which real pair has a working alias first), post a real message from the owner mentioning that person by typing @ and selecting them from the autocomplete. Confirm the sent message, viewed as the owner, shows the real alias text as the mention. Confirm the same message, viewed as a different real account with no alias set for that same person, shows the real handle instead, not the owner's private alias, proving the same per-viewer isolation already verified for author_display also holds for mentions. Confirm the mentioned member's real notification actually fires (check whatever real notification-listing endpoint already exists in this app, or the frontend's notification UI directly). Report every real response and a screenshot of both a mention being composed and the same message rendered two different ways for two different viewers.

GIT:

Do not commit until Ben confirms the real per-viewer mention resolution genuinely holds, with real evidence for both viewers, not a description.