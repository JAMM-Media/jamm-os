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

TASK: Add the missing portal-magic-link branch to the mount-time pending action reader on the client detail page

USE: claude sonnet

VERIFY BEFORE ACT:

sed -n '83,99p' /home/corby/jamm-os/frontend/src/app/\(app\)/clients/\[id\]/page.tsx

sed -n '100,118p' /home/corby/jamm-os/frontend/src/app/\(app\)/clients/\[id\]/page.tsx

Confirm the mount-time effect at 83-99 currently only checks action.modal === 'new-engagement', while the separate live onConciergeAction listener at 100-118 already correctly handles action.modal === 'portal-magic-link' by setting the active tab to overview, setting portalLinkHighlight true, scrolling the button into view after a short delay, and clearing the highlight after 3000ms. Confirm this asymmetry exists before editing.

WHAT THIS IS:

Confirmed live: with the client name resolution bug now fixed separately, asking the Concierge to send a client their portal link from a different page now correctly resolves the client and navigates to their page, but the ring highlight on the portal-link button still never fires. Root cause confirmed by direct comparison of the two places in this file that read a pending Concierge action: the live onConciergeAction listener, which only receives events while the panel is already mounted and processing in real time, correctly handles the portal-magic-link modal. The separate mount-time effect, which reads the pending action left in sessionStorage by executeAction right before a fresh page navigation, only checks for new-engagement. Since navigating to a different client's page is a fresh mount, only the mount-time reader ever runs, the live listener never fires because no live event is emitted during a cross-page navigation, and the highlight logic is simply never reached.

CHANGE INSTRUCTIONS:

In the mount-time effect at lines 83-99, add a new condition alongside the existing new-engagement check, for action.modal === 'portal-magic-link'. Inside it, call sessionStorage.removeItem('jamm_concierge_pending'), then reproduce the exact same three effects the live listener already performs for this modal: set the active tab to overview, set portalLinkHighlight to true, scroll portalLinkRef into view after a short delay, and clear the highlight after 3000ms. Match the live listener's timing values exactly rather than inventing new ones. Do not change the existing new-engagement branch in this effect, do not change the live onConciergeAction listener at all, and do not touch the third pending-action effect further down that handles prefillMessage.

VERIFY AFTER ACT:

grep -n "portal-magic-link" /home/corby/jamm-os/frontend/src/app/\(app\)/clients/\[id\]/page.tsx

Expected: now appears in both the mount-time effect and the live listener, two occurrences total where there was previously one.

npx tsc --noEmit

MANUAL VERIFICATION:

Restart the frontend.

From a page other than this client's own page, for example the Dashboard or another client's page, with Autopilot on, ask the Concierge to send Robert & Carol Tanner their portal link.

Confirm the app navigates to Robert & Carol Tanner's page, the Overview tab is active, and the portal-link button shows a visible ring highlight within about a second of arriving, without needing a manual page reset first.

Separately, while already on a client's own page with the panel open, ask it to send that same client's portal link, confirming the live listener path still works correctly and was not broken by this change.

Report pass or fail for both checks individually.

GIT:

git add -A

git commit -m "add the missing portal-magic-link branch to the mount-time pending action reader on the client detail page, matching the same handling already present in the live onConciergeAction listener, fixing the ring highlight never firing when the Concierge navigates to a client's page from somewhere else, since a fresh page mount only ever reads the pending action from sessionStorage and never receives a live event"

git pull --rebase origin main

git push origin main