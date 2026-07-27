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

TASK: Make the client-slug navigation branch skip re-navigation and fire the live listener directly when already on the target client's page

USE: claude sonnet

VERIFY BEFORE ACT:

sed -n '795,860p' /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Confirm the non-UUID client-slug branch currently always calls router.push(resolvedRoute), stores a pending action in sessionStorage, and returns, with no check anywhere in that branch for whether pathname already matches the resolved client route. Confirm the alreadyOnRoute check that exists later in the function, for the non-client-slug modal case, is structurally unreachable from this branch since this branch always returns first. Confirm this before editing.

WHAT THIS IS:

Confirmed live via the browser Network tab, checking the raw CONCIERGE_ACTION JSON across three consecutive identical requests: the model consistently and correctly emits the same modal value, portal-magic-link, every time. The bug is not in the model's output. The bug is that the client-slug resolution branch in executeAction has no concept of "already on this client's page." Every time this branch runs, regardless of current location, it resolves the client's id, calls router.push to that client's route, and stores the action as pending in sessionStorage for the next mount to pick up, then returns immediately. When already on that exact client's page, router.push to the same pathname is a no-op in Next.js, no remount occurs, the mount-time pending-action reader never re-runs since it only runs once per real mount, and the live onConciergeAction listener is never invoked either since emitConciergeAction was never called on this code path. The pending action is written to sessionStorage and never read by anything, and the highlight silently never fires. This exact same class of already-on-route handling already exists later in this function for the non-client-slug modal case, using pathname.startsWith(normalizedRoute) to decide between emitConciergeAction directly versus storing a pending action for later, but the client-slug branch was never given the equivalent check.

CHANGE INSTRUCTIONS:

Inside the non-UUID client-slug branch, after resolvedRoute is computed and before the formDirty check and router.push call, add a check for whether the browser is already on that resolved client's route, using the same style already established later in this function, pathname starting with the client's resolved path ignoring any query string. If already on that route, skip the formDirty check, skip router.push, skip writing jamm_concierge_pending to sessionStorage, and instead call emitConciergeAction(action) directly, then set the status message using the same modalLabel lookup pattern already used later in this function for the modal case, falling back to a generic opened-modal message if the action's modal value is not in that lookup. If not already on that route, preserve all existing behavior in this branch exactly as it is now. Do not change the later, already-correct alreadyOnRoute block used for non-client-slug modal actions, and do not change the UUID branch of this same client-slug check.

VERIFY AFTER ACT:

grep -n "alreadyOnRoute\|alreadyOnClientRoute" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Expected: a new already-on-route style check now appears inside the client-slug branch, in addition to the existing one further down.

npx tsc --noEmit

MANUAL VERIFICATION:

Restart the frontend.

While already on Robert & Carol Tanner's page with the panel open, ask the Concierge to send that client's portal link. Confirm the ring highlight fires immediately, without the page navigating away and back.

Ask the exact same question again immediately after. Confirm the highlight fires again.

Ask a third time while the highlight from the second request is still visibly active. Confirm it restarts cleanly.

Separately, from the Dashboard, ask the Concierge to send Robert & Carol Tanner their portal link, confirming the cross-page navigation case, which was already working, still works correctly and was not broken by this change.

Report pass or fail for all four checks individually, noting actual observed highlight duration.

GIT:

git add -A

git commit -m "fix the client-slug navigation branch in executeAction never checking whether the browser is already on the target client's page, confirmed via the raw network response that the model consistently emits correct CONCIERGE_ACTION JSON on every request while the frontend's router.push to an identical pathname produced a no-op remount, silently stranding the pending action in sessionStorage and preventing the portal-link ring highlight from ever firing on repeated same-page requests"

git pull --rebase origin main

git push origin main