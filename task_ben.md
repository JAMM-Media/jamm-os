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

TASK: Add a Reset to Default option to Edit Dashboard mode. Clicking it loads the same layout a brand-new user would get (firm default if set, otherwise the system default 9-widget layout) into the current edit session, still requiring Done to actually save, so it stays fully undoable via Cancel like every other edit-mode action.

USE: claude sonnet

ENVIRONMENT SANITY CHECK:

pwd

State plainly that no path in this task resolves against /mnt/c/Users or any Windows-side copy.

VERIFY BEFORE ACT:

grep -n -B 5 -A 40 "def get_layout" app/api/dashboard.py

grep -n -B 5 -A 15 "useConfirm" src/components/dashboard/ConciergeSpotlight.tsx frontend/src/lib/hooks/useConfirm.ts 2>/dev/null

Paste the real output of both. Confirm the exact current resolution logic inside get_layout (firm default then system default), since this needs to be reused, not duplicated, and confirm the real useConfirm hook's signature before using it for the reset confirmation prompt.

WHAT THIS IS:

The resolution logic already exists inside get_layout for a first-time user: check for a saved DashboardLayout row, then a FirmDefaultDashboardLayout row, then fall back to the hardcoded system default. Reset to Default needs that same firm-default-then-system-default resolution, but callable on demand for a user who already has a saved layout, not just on first load. The cleanest way to do this without duplicating the resolution logic is extracting the firm-default-then-system-default portion of get_layout's existing logic into its own small function, then having both get_layout's fallback path and the new reset endpoint call that same function, so there is exactly one place this resolution is defined, not two copies that could drift apart later.

CHANGE INSTRUCTIONS:

In app/api/dashboard.py, extract the firm-default-then-system-default resolution portion of get_layout's existing logic into a standalone function, for example _resolve_default_layout(db, current_firm), returning the widgets list, without changing get_layout's own behavior at all, this is a pure refactor of that one piece.

Add a new endpoint, POST /dashboard/reset, gated require_manager_or_above same as the other layout endpoints, that calls _resolve_default_layout and returns the resulting widgets list. This endpoint does not write to the database at all, it only returns what the default would be, matching the pattern that Done, not this endpoint, is what actually persists anything, consistent with every other edit-mode action.

Add a getDefaultLayout method to frontend/src/lib/api/dashboard.ts calling POST /dashboard/reset.

In the dashboard page, add a "Reset to Default" button, visible only while editMode is true, placed near the existing Edit Dashboard row of controls but visually secondary, a plain text-style button rather than a solid button, since this is a less common, semi-destructive action compared to Done or Cancel. Clicking it opens the existing useConfirm dialog with a clear message explaining this will replace the current arrangement with the default layout, and nothing is saved until Done is clicked afterward. On confirmation, call getDefaultLayout and replace editedWidgets entirely with the returned widgets, staying in edit mode, not auto-saving and not auto-exiting edit mode, so the user can still inspect the result and either click Done to save it or Cancel to discard the whole reset and get back their original arrangement.

VERIFY AFTER ACT:

cd /home/corby/jamm-os/frontend
npm run build

cd /home/corby/jamm-os
python3 -c "from app.main import app; print('app imports cleanly')"

grep -n "_resolve_default_layout\|/dashboard/reset" app/api/dashboard.py

grep -n "Reset to Default\|getDefaultLayout" "frontend/src/app/(app)/dashboard/page.tsx" frontend/src/lib/api/dashboard.ts

git diff --stat

MANUAL VERIFICATION:

Restart the backend and the frontend dev server, both are needed since this touches both. Reload /dashboard, enter Edit Dashboard, confirm the current messy arrangement is still there. Click Reset to Default, confirm the dialog appears, confirm it, and confirm the canvas now shows the clean 9-widget default arrangement, 4 stat cards in a row, Work in Progress, Upcoming Deadlines and Staff Utilization side by side, Overdue Engagements table, Awaiting Signature. Click Cancel instead of Done, confirm the original messy arrangement comes back exactly as it was, proving the reset itself was truly undoable. Then repeat, enter Edit Dashboard, click Reset to Default and confirm again, this time click Done, reload the full page, and confirm the clean default persisted for real. Report back with a screenshot after the final reload.

GIT:

git add -A
git commit -m "add Reset to Default to Edit Dashboard mode, reusing the same firm-default-then-system-default resolution logic already used for first-time layout seeding via a new shared _resolve_default_layout function and a POST /dashboard/reset endpoint that only returns the default without writing anything, keeping Done as the single place any layout change actually persists so a reset stays fully undoable via Cancel like every other edit-mode action. Added after live testing tonight genuinely drifted a real dashboard into a messy state with no way back short of a direct database fix, reversing an earlier decision to defer this out of v1"
git pull --rebase origin main
git push origin main

If task.md conflicts on the rebase, resolve with --theirs. Any other file conflict, stop and report back.