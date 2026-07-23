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

TASK: Fix two real tool crashes, get_deadline_calendar referencing a nonexistent Engagement field, and get_automation_health referencing the wrong AutomationRule field name

USE: claude sonnet

VERIFY BEFORE ACT:
grep -n "def get_deadline_calendar" -A 40 /home/corby/jamm-os/app/api/concierge/functions.py
grep -n "def get_automation_health" -A 30 /home/corby/jamm-os/app/api/concierge/functions.py

Confirm both match what is described below before editing.

WHAT IS WRONG, PART ONE:

get_deadline_calendar joins User via Engagement.assigned_to, a field that does not exist anywhere on the Engagement model, confirmed by reading the full model directly. Engagement has no per-engagement staff assignment concept at all, only individual Task rows have their own assignee. This join fails every time this tool is called, confirmed live via the exact error type object Engagement has no attribute assigned_to.

CHANGE INSTRUCTIONS, PART ONE:

Remove the outer join to User and remove assigned_staff from the select statement and from the assigned_to key in the returned dict entirely. Do not attempt to derive an assignee from Task, that would require a real design decision about which task's assignee represents an engagement's assignee when multiple tasks with different assignees exist, which is out of scope for this fix. This tool should simply stop claiming a per-engagement assignee exists, since it genuinely does not in this data model.

WHAT IS WRONG, PART TWO:

get_automation_health references AutomationRule.is_active, which does not exist on the model. The real field, confirmed by reading the model directly, is is_enabled. This tool fails every time it is called, confirmed live via the exact error type object AutomationRule has no attribute is_active.

CHANGE INSTRUCTIONS, PART TWO:

Change every reference to AutomationRule.is_active to AutomationRule.is_enabled throughout this function.

VERIFY AFTER ACT:

python3 -c "
from app.db.session import SessionLocal
from app.api.concierge.functions import get_deadline_calendar, get_automation_health
db = SessionLocal()
r1 = get_deadline_calendar('185314c9-e702-4eab-8600-249848022206', db)
print('deadline calendar:', r1)
r2 = get_automation_health('185314c9-e702-4eab-8600-249848022206', db)
print('automation health:', r2)
db.close()
"

Expected: both print real dicts with no traceback, no error.

python3 -c "from app.main import app; print('OK')"

MANUAL VERIFICATION:

Restart backend, keep terminal visible. Ask what's on the calendar for this month, confirm a real answer with no data error message and no Tool execution failed line in the log. Ask which automations are currently enabled, confirm the same.

Report pass or fail for both, and paste the real Python output from the verification script above, not a summary.

GIT:
git add -A
git commit -m "fix get_deadline_calendar referencing a nonexistent Engagement.assigned_to field, since engagement level staff assignment does not exist in this data model, removing the field rather than approximating one from task level assignment, and fix get_automation_health referencing the wrong field name is_active instead of the real is_enabled, both confirmed live as real recurring tool crashes found during a deep audit"
git pull --rebase origin main
git push origin main