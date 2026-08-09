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

TASK: Add the backend foundation for Peer Network DMs and subgroups: a real per-room membership table (which does not exist at all right now, confirmed live, every room is currently accessible to any active network member regardless of intent), room creation, and making list_rooms genuinely per-user instead of returning every room unconditionally.

USE: claude fable-5

ENVIRONMENT SANITY CHECK:

pwd

State plainly that no path in this task resolves against /mnt/c/Users or any Windows-side copy.

VERIFY BEFORE ACT:

.venv/bin/alembic heads

grep -n -B 3 -A 30 "class PeerNetworkRoom" app/models/peer_network.py

grep -n -B 3 -A 20 "def list_rooms\|def list_messages\|def post_message" app/api/peer_network.py

Confirm exactly one alembic head. Confirm the real current PeerNetworkRoom model and every real place a room gets looked up, since access control needs to be added consistently across all of them, not just the new ones.

WHAT THIS IS, PER THE LOCKED SPEC SECTION 6:

Direct messages (one-to-one) and multi-person private subgroups. Members create these freely, no approval needed. Subgroups can be named with a shared name. No cap on subgroups per member. This is fundamentally different from Main (open to every active network member) and Announcements (read-only, JAMM team posts only): DMs and subgroups need real, restricted membership, confirmed as a genuine gap right now since PeerNetworkRoom has no membership concept at all and any active member could theoretically access any room by ID.

CHANGE INSTRUCTIONS:

Add a new model, PeerNetworkRoomMember, in app/models/peer_network.py: id, room_id (FK peer_network_rooms.id, ondelete=CASCADE, index), member_id (FK peer_network_members.id, ondelete=CASCADE, index, this is a PeerNetworkMember id, not a raw user id, matching the existing pattern used throughout this feature), joined_at (DateTime with timezone). Add a real unique constraint on (room_id, member_id), someone can't be added to the same room twice.

Write the migration by hand, matching tonight's established real structure, down_revision set to the real current head confirmed above.

Add a real helper function, get_room_membership(db, room_id, member_id) or similar, in app/services/peer_network_service.py, returning the real PeerNetworkRoomMember row or None. This should be used to gate access specifically for room_type "dm" and "subgroup", NOT for "main" or "announcements", since those two remain open to every active network member exactly as they work today, do not change their access behavior.

Update list_messages and post_message: after the existing get_active_member check (unchanged), for rooms where room_type is "dm" or "subgroup", additionally require a real PeerNetworkRoomMember row for the calling member, real 403 if none exists. For "main" and "announcements", skip this additional check entirely, preserving current behavior exactly.

Add POST /peer-network/rooms, accepting {room_type: "dm" | "subgroup", member_ids: list[uuid], name: Optional[str]}. Validate room_type is one of these two values only, reject "main"/"announcements" creation attempts since those are singleton/admin-only concepts, not user-creatable. For "dm", require exactly 2 total participants (the creator plus exactly one other, reject any other count with a clear error). For "subgroup", require at least 2 total participants (creator plus at least one other) and allow name to be set; for "dm", name should always be null regardless of what's passed, DMs are not named per spec. Validate every real member_id in the request actually corresponds to a real, active PeerNetworkMember in this firm's network before creating anything, reject with a clear error listing which ids were invalid if any aren't. Create the PeerNetworkRoom row, then a PeerNetworkRoomMember row for the creator and for every valid target member, including the creator themselves.

Rewrite list_rooms to be genuinely per-user: for "main" and "announcements", these should always appear for every active member with no membership check, exactly as today. For "dm" and "subgroup", only include rooms where a real PeerNetworkRoomMember row exists for the calling member. Keep the existing my_handle/has_posted/is_muted/muted_reason fields in the response exactly as they are now, this is purely about which rooms get listed, not the shape of the per-user state already returned.

Add PATCH /peer-network/rooms/{room_id}, gated by real room membership (dm/subgroup only, per the new check), accepting {name: str}, renaming a subgroup only, reject with a clear error if called on a dm (dms are never named) or on main/announcements (not user-renameable).

VERIFY AFTER ACT:

grep -n "class PeerNetworkRoomMember" app/models/peer_network.py

grep -n "get_room_membership\|@router.post(\"/rooms\")\|@router.patch(\"/rooms" app/api/peer_network.py

.venv/bin/alembic heads

This must show exactly one head, the new migration's revision id. Run .venv/bin/alembic upgrade head and confirm it applies with no errors.

cd /home/corby/jamm-os
python3 -c "from app.main import app; print('app imports cleanly')"

MANUAL VERIFICATION:

Restart the backend. Using two real distinct member accounts from tonight's testing (the owner and the manager, both confirmed active members), create a real DM between them via POST /peer-network/rooms. Confirm both participants can call GET /peer-network/rooms and see the new DM listed, and confirm a real third account (the third-party test account created earlier tonight, also an active member but not part of this DM) does NOT see it in their own room list. Post a real message in the new DM as one participant, confirm the other participant can read it via GET /peer-network/rooms/{room_id}/messages, and confirm the real third-party account gets a real 403 attempting to read the same room directly by its real id. Try creating a DM with 3 member_ids, confirm a real, clear rejection. Create a real subgroup with a real name and 3 total participants, confirm it works and is named correctly. Report every real response.

GIT:

Do not commit until Ben confirms every real check above with actual API responses.