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

TASK: Make the portal-link ring highlight reliably re-trigger on every request and extend its duration to 5 seconds

USE: claude sonnet

VERIFY BEFORE ACT:

sed -n '95,120p' /home/corby/jamm-os/frontend/src/app/\(app\)/clients/\[id\]/page.tsx

Confirm both the mount-time branch and the live listener branch currently call setPortalLinkHighlight(true) followed by a bare setTimeout(() => setPortalLinkHighlight(false), 3000), with no ref tracking or clearing of any prior pending timeout, before editing.

WHAT THIS IS:

Confirmed live: asking the Concierge to send a client's portal link a second time, while already on that client's page, did not restart the ring highlight. Confirmed live separately: the highlight visibly lasted closer to 2 seconds than the coded 3000ms in at least one observed case. Both symptoms point to the same root cause. Every time the highlight is triggered, a new setTimeout is scheduled to turn it off in 3000ms, but no reference to that timeout is kept and no prior pending timeout is ever cleared. If the highlight is triggered a second time while an earlier timeout from a previous trigger is still pending, the earlier timeout still fires on its own original schedule and turns the highlight off early or immediately, regardless of when the second trigger happened. There is no code path that fails to set portalLinkHighlight to true on a second request, the state is being set correctly each time, but an old, uncleared timer from a previous trigger is turning it back off unpredictably.

CHANGE INSTRUCTIONS:

Add a ref, near portalLinkHighlight's own useState declaration, to hold the current pending timeout id. In both the mount-time branch and the live listener branch where the highlight is currently triggered, before scheduling the new setTimeout to clear the highlight, check if the ref already holds a pending timeout id and call clearTimeout on it first if so. Then schedule the new setTimeout, store its id in the ref, and change the duration from 3000 to 5000. Apply this identically in both places, since they currently duplicate the same triggering logic and must stay in sync with each other. Do not change the scrollIntoView behavior or its own separate 100ms delay, only the highlight-clearing timeout.

VERIFY AFTER ACT:

grep -n "portalLinkTimeoutRef\|5000" /home/corby/jamm-os/frontend/src/app/\(app\)/clients/\[id\]/page.tsx

Expected: a new ref is declared and used in both branches, and 5000 appears in place of the old 3000 in both places.

npx tsc --noEmit

MANUAL VERIFICATION:

Restart the frontend.

While already on a client's page with the panel open, ask the Concierge to send that client's portal link. Confirm the ring highlight fires and lasts a full 5 seconds, timing it if possible.

Immediately after it fades, ask again for the same client. Confirm it fires again for a full 5 seconds.

Ask a third time while the highlight from the second request is still visibly active, partway through its 5 seconds. Confirm the highlight restarts cleanly rather than cutting off early or behaving unpredictably.

Report pass or fail for all three checks individually, noting the actual observed duration each time.

GIT:

git add -A

git commit -m "fix the portal-link ring highlight not reliably re-triggering on repeated requests and extend its duration from 3 to 5 seconds, root cause confirmed as an uncleared prior setTimeout turning the highlight off early or unpredictably whenever it was triggered more than once without the previous timer being cancelled first"

git pull --rebase origin main

git push origin main