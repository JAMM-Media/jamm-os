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

TASK: Build the Growth Cooperative's main room frontend: a new page showing the message feed and a compose box, read/post only, no DMs, subgroups, reactions, replies, or mentions yet. This must be a genuinely separate component tree from Firm Chat, not importing its hooks or API client, even though the visual layout is intentionally similar per the spec.

USE: claude fable-5

ENVIRONMENT SANITY CHECK:

pwd

State plainly that no path in this task resolves against /mnt/c/Users or any Windows-side copy.

VERIFY BEFORE ACT:

grep -n -B 3 -A 30 "@router.get(\"/rooms/{room_id}/messages\")\|@router.post(\"/opt-in\")" app/api/cooperative.py

grep -n -B 5 -A 30 "function.*Layout\|nav" src/components/layout/Sidebar.tsx | head -40

Paste the real output of both. Confirm the exact real response shape of GET/POST messages, the exact real request body POST expects, the exact real 403 shape for a non-member, and the exact real response of POST /cooperative/opt-in, all confirmed live in batch 1 tonight. Confirm the real Sidebar nav item pattern to add a new entry to.

WHAT THIS IS:

This must be built as an entirely separate component tree from Firm Chat, per the spec's hard requirement confirmed and enforced at the backend layer in batch 1. Do not import useChannels, useMessages, or firmChatApi from the firm-chat directory, even for small pieces, write fresh, parallel versions of any needed logic (date-label formatting, same-day grouping, consecutive-same-author grouping within a short time window, timestamp formatting) directly in the new Cooperative files. These are generic display utilities with no firm-chat-specific coupling in their logic, but importing them from the firm-chat directory would still create an unwanted dependency the spec's isolation principle argues against, write them fresh.

Per spec section 14, avatars cannot use initials since members are pseudonymous. Generate a deterministic color from each message's author_handle string (a simple hash of the string mapped into a small fixed palette is sufficient), so the same handle always renders the same color throughout the room, unlike Firm Chat's simpler per-message-index color cycling, which would incorrectly show different colors for the same person across different messages.

The backend's current message response has no is_jamm_team field per message yet, so a JAMM team badge cannot be built accurately in this batch, do not build one, that's real scope for a later batch once the backend actually returns that field per message.

A user hitting this page needs a real membership check, not an assumption they already have access. Call GET /cooperative/rooms/{main room id}/messages first; if it returns a real 403 (confirmed live tonight as {"detail":"You do not have active access to the Growth Cooperative."}), do not show the message feed at all. Instead, show a real access-gate state: if the current user's role is firm_owner, show a genuine opt-in call to action wired to POST /cooperative/opt-in; for any other role, show a message explaining that Growth Cooperative access is granted by the firm owner, with no action available, since only the owner can grant it per spec section 5.

CHANGE INSTRUCTIONS:

Create frontend/src/lib/api/cooperative.ts, a new, separate API client file, not extending firmChat.ts. Export a CooperativeMessage interface matching the real confirmed response shape (id, room_id, author_handle, body, created_at), and a cooperativeApi object with optIn(), getMessages(roomId), and postMessage(roomId, body).

Fetch the real main room's id, do not hardcode the UUID confirmed live tonight, since that id is environment-specific. If the backend does not yet expose a way to list rooms, add a minimal GET /cooperative/rooms endpoint returning the singleton main room's real id and room_type, gated by the same real membership check as the messages endpoints, confirm whether this already exists before assuming it needs to be added, check the real file.

Create frontend/src/app/(app)/cooperative/page.tsx. Build the message feed: date dividers between days (fresh logic, not imported), consecutive messages from the same author_handle within a short time window grouped without repeating the avatar/handle header (fresh logic, not imported), each message showing its deterministic-colored circle avatar, the real handle text, the message body, and a formatted timestamp. Build a simple compose box at the bottom posting via cooperativeApi.postMessage, clearing on success, appending the new message to the feed without requiring a full refetch.

Add "Growth Cooperative" as a new nav item in the real Sidebar, following the exact real pattern already used for other nav items there.

VERIFY AFTER ACT:

cd /home/corby/jamm-os/frontend
npm run build

grep -n "cooperativeApi\|CooperativeMessage" src/lib/api/cooperative.ts

grep -rn "useChannels\|useMessages\|firmChatApi" "src/app/(app)/cooperative/page.tsx"

This last grep must return nothing, confirming no accidental import from the firm-chat directory.

git diff --stat

MANUAL VERIFICATION:

Restart the frontend dev server only, backend is already confirmed working from batch 1. Log in as owner@riverside-demo.com, navigate to Growth Cooperative from the sidebar. Since the owner already opted in during batch 1's testing, confirm the real message feed loads showing the real "Hello from the Growth Cooperative!" message with a real handle and a colored avatar, not initials. Post a new message, confirm it appears immediately without a full page reload. Log in as a different real user who has not been granted access, navigate to Growth Cooperative, confirm the real access-gate state appears instead of the message feed, with copy appropriate to their role (not an owner, so no opt-in button, just an explanation). Report back with a screenshot of both states.

GIT:

Do not commit until Ben confirms both states look and work correctly in the browser.