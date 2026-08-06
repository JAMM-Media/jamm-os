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

TASK: Fix the system-default dashboard layout seed. staff_utilization is seeded at grid_x 1 with size medium (width 2 columns), but upcoming_deadlines is also at grid_x 0 with size medium (width 2 columns), so they overlap in column 1, which is why react-grid-layout's collision handling pushes staff_utilization onto its own row instead of sitting beside upcoming_deadlines as intended.

USE: claude sonnet

VERIFY BEFORE ACT:

grep -n -B 3 -A 30 "system default" app/api/dashboard.py

Confirm the exact line where staff_utilization's grid_x is set to 1 in the system-default seed inside get_layout.

WHAT THIS IS:

Medium widgets are 2 grid columns wide in this 4-column grid. Two medium widgets sitting side by side need x positions 2 apart, not 1 apart, the same way two 2-inch tiles laid side by side start 2 inches apart, not 1. The seed currently places upcoming_deadlines at x 0 and staff_utilization at x 1, which means they overlap in column 1, not that they're adjacent. This was wrong in the original task instruction, not something introduced during implementation.

CHANGE INSTRUCTIONS:

In the system-default seed inside get_layout in app/api/dashboard.py, change staff_utilization's grid_x from 1 to 2, so upcoming_deadlines occupies columns 0-1 and staff_utilization occupies columns 2-3, correctly adjacent with no overlap.

The Riverside test firm owner already has a saved DashboardLayout row from earlier testing, seeded with the old buggy value, and GET /layout only seeds when no row exists, so fixing the source code alone will not fix what that user already sees. Delete the existing row for owner@riverside-demo.com from the dashboard_layouts table so the next GET /layout call re-seeds it with the corrected position, rather than leaving stale bad data in place.

VERIFY AFTER ACT:

grep -n "grid_x.*2" app/api/dashboard.py

Confirm the Riverside owner's old dashboard_layouts row was actually deleted, not just that the source code changed.

MANUAL VERIFICATION:

Restart the backend. Call GET /dashboard/layout as owner@riverside-demo.com again and confirm staff_utilization now shows grid_x 2, not 1. Then load /dashboard in the browser and confirm Upcoming Deadlines and Staff Utilization now render side by side in one row, not stacked, and confirm Work in Progress above them still renders correctly since it wasn't affected by this bug. Report back a screenshot or a plain description of what the row now looks like.

GIT:

git add -A
git commit -m "fix system-default dashboard layout seed: staff_utilization was placed at grid_x 1 with medium width, overlapping upcoming_deadlines at grid_x 0 also medium width, causing collision-driven stacking instead of the intended side by side row, corrected to grid_x 2 and cleared the one stale seeded row already created during testing"
git pull --rebase origin main
git push origin main

If task.md conflicts on the rebase, resolve with --theirs. Any other file conflict, stop and report back.