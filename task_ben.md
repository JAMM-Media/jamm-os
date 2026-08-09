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

TASK: Add the backend foundation for Peer Network reactions and one-level replies, per spec section 7: standard emoji set reactions on any message (toggle on/off, no custom uploads), and Slack-style one-level-deep replies (a reply attaches to a parent message; replies to replies flatten into the same thread rather than nesting).

USE: claude fable-5

ENVIRONMENT SANITY CHECK:

pwd

State plainly that no path in this task resolves against /mnt/c/Users or any Windows-side copy.

VERIFY BEFORE ACT:

.venv/bin/alembic heads

grep -n -B 3 -A 45 "def list_messages" app/api/peer_network.py

Confirm exactly one alembic head. Confirm the real current list_messages implementation in full (the batch-fetch-then-build-maps-then-construct-items pattern already established), since reactions and reply data need to follow this same real pattern, not a different approach.

WHAT THIS IS, PER THE LOCKED SPEC SECTION 7 AND THE PROPOSED MESSAGE SHAPE IN SECTION 15:

Reactions: emoji reactions on any message, standard set, no custom uploads. The real proposed response shape per message: "reactions": [{ "emoji": "👍", "count": 4, "reacted_by_me": true }]. Replies: one level deep only. A reply attaches to a parent message via parent_id and forms a thread. Replies to replies flatten into the same thread rather than nesting, meaning a reply's own parent_id must always point to a genuine top-level message, never to another reply, enforced server-side, not just a frontend convention. The real proposed shape includes reply_count on the parent.

CHANGE INSTRUCTIONS:

Add a new model, PeerNetworkReaction, in app/models/peer_network.py: id, message_id (FK peer_network_messages.id, ondelete=CASCADE, index), member_id (FK peer_network_members.id, ondelete=CASCADE, index), emoji (String, a real restricted set, define a real constant list of allowed standard emoji, for example 👍 ❤️ 😂 🎉 👏 💡, reject anything outside this set with a clear error rather than accepting arbitrary text), created_at. Add a real unique constraint on (message_id, member_id, emoji), the same person reacting with the same emoji twice should not create duplicate rows, toggling should remove it instead.

Add parent_id: Mapped[uuid.UUID | None] to PeerNetworkMessage, ForeignKey peer_network_messages.id, ondelete=SET NULL, nullable=True, index=True. When creating a reply, if the target parent message itself already has a non-null parent_id, reject with a clear error or automatically flatten by using the parent's own parent_id instead of the attempted grandparent (spec explicitly requires flattening, not rejecting, choose flattening to match "replies to replies flatten into the same thread" precisely, do not silently allow a real two-level chain to form).

Write the migration by hand, matching tonight's established real structure, down_revision set to the real current head confirmed above.

Add POST /peer-network/messages/{message_id}/reactions, accepting {emoji: str}, gated by real active membership and, if the message's room is dm/subgroup, real room membership too (reuse the exact same real checks already used in post_message). Validate emoji is in the real allowed set. Toggle behavior: if the calling member already has this exact reaction on this message, remove it (un-react); otherwise create it. Return the real updated reaction summary for this message.

Add a reply parameter to the existing POST /peer-network/rooms/{room_id}/messages endpoint: accept an optional parent_id in the request body. If provided, validate the parent message exists in this same room (reject if it's in a different room), and apply the real flattening rule described above if the target parent itself has a parent_id.

Update list_messages to include real reaction and reply data per message, following the exact same batch-fetch pattern already used for handles/aliases/jamm_team: batch-query all PeerNetworkReaction rows for every message id in the current page, group by message_id and emoji to build real counts, and check whether the calling member's own id appears in each group for reacted_by_me. Batch-query reply counts (a real COUNT grouped by parent_id) for every message id in the current page. Add "reactions": [...] and "reply_count": int and "parent_id": str | None to each item's real response dict, matching the exact real shape already established in section 15's proposed API.

VERIFY AFTER ACT:

grep -n "class PeerNetworkReaction" app/models/peer_network.py

grep -n "parent_id\|reactions.*POST\|@router.post(\"/messages" app/api/peer_network.py

.venv/bin/alembic heads

This must show exactly one head, the new migration's revision id. Run .venv/bin/alembic upgrade head and confirm it applies with no errors.

cd /home/corby/jamm-os
python3 -c "from app.main import app; print('app imports cleanly')"

MANUAL VERIFICATION:

Restart the backend. Using two real distinct accounts from tonight's testing, react to a real existing message with a real allowed emoji as each account, confirm the message's real reactions field shows count 2, reacted_by_me true for each account's own perspective, false for the other's. React again with the same emoji as one account, confirm it toggles off (count drops back to 1). Try reacting with a real disallowed emoji or arbitrary text, confirm a real, clear rejection. Post a real reply to an existing message, confirm the parent's reply_count increases. Attempt to reply to that same reply (a real attempted second-level nesting), confirm it correctly flattens to point at the real original top-level parent, not the reply, verify this with a real database query showing the actual stored parent_id. Report every real response and query result.

GIT:

Do not commit until Ben confirms every real check above with actual evidence.