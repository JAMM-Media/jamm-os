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

TASK: Give staff scoped Concierge access to their own tasks and engagements only, replacing the blanket block

USE: Fable 5

VERIFY BEFORE ACT:
grep -n "def concierge_chat" -A 20 /home/corby/jamm-os/app/api/concierge/route.py
grep -n "_CONCIERGE_TOOLS\s*=" -A 5 /home/corby/jamm-os/app/api/concierge/route.py
grep -n "def get_task_status" -A 40 /home/corby/jamm-os/app/api/concierge/functions.py
grep -n "assigned_to" /home/corby/jamm-os/app/models/task.py

Confirm the current blanket staff block in concierge_chat, the existing _CONCIERGE_TOOLS list structure, the existing get_task_status pattern to match style against, and the real Task.assigned_to field before writing anything. Read the full tool-use loop in generate_with_tools before making any change to which tools get passed into it, this is a security-relevant change and must be scoped precisely.

WHAT THIS IS:

Staff currently get a full 403 block from the Concierge entirely, a safe but overly broad temporary fix applied earlier tonight given the firm size this product targets, 4 to 40 employees, and the real risk of junior staff seeing firm-wide financial and personnel data. A full block is not the right permanent answer, since a staff member asking about their own assigned work is a completely different, low-risk case from them asking about firm-wide accounts receivable or another employee's workload. Engagement has no per-engagement assignment field at all, confirmed earlier tonight, only individual Task rows have a real assigned_to field, so a staff member's own engagements must be derived from their own tasks, not a direct engagement-level assignment.

CHANGE INSTRUCTIONS:

In functions.py, add a new tool function, get_my_tasks, accepting firm_id, user_id, and db. It should return, matching the existing get_task_status pattern and docstring style, every incomplete task where assigned_to equals the given user_id specifically, not firm wide, including the client name, engagement name, due date, and status for each, plus the distinct set of engagement names those tasks belong to as a simple list, giving a staff member a real answer to what am I working on and what engagements am I involved in, scoped entirely to their own assignments.

In route.py, remove the blanket staff block from concierge_chat entirely, keeping the existing client_portal_user block exactly as is. Instead, when current_user.role is staff, restrict which tools are actually available in the tool-use loop to only get_my_tasks, none of the firm-wide tools such as get_overdue_invoices, get_staff_capacity, get_firm_settings, or any other tool that returns data beyond one person's own assignments. Do this by constructing a separate, smaller tool list used only for the staff role, rather than filtering the full list dynamically in a way that could be error prone, an explicit, separate, minimal list is safer and easier to audit than a filter applied to the full one.

Add or adjust the relevant operational keyword and topic keyword entries so questions like what am I working on or what are my tasks correctly route to get_my_tasks for a staff user.

Ensure the system prompt context passed to a staff user's conversation makes clear the assistant currently only has visibility into that staff member's own assigned tasks and engagements, not firm-wide data, so the model does not imply broader knowledge it does not have access to in this scoped mode.

Do not expose get_my_tasks or the staff-scoped tool list to owner or manager roles, they continue to use the full existing tool set exactly as it already works. Do not attempt to scope any tool other than tasks in this task, firm-wide financial, staff capacity, settings, and every other tool remain fully inaccessible to staff, this is a deliberate, narrow first version, not full role based access.

VERIFY AFTER ACT:

grep -n "get_my_tasks" /home/corby/jamm-os/app/api/concierge/functions.py /home/corby/jamm-os/app/api/concierge/route.py

Expected: present in both, and confirm in route.py that the staff-specific tool list genuinely only contains get_my_tasks, nothing else, by reading the actual list, not assuming.

python3 -c "
from app.db.session import SessionLocal
from app.api.concierge.functions import get_my_tasks
db = SessionLocal()
result = get_my_tasks('185314c9-e702-4eab-8600-249848022206', 'REPLACE_WITH_REAL_STAFF_USER_ID', db)
print(result)
db.close()
"

Use the real id of the test staff account already created tonight, teststaff@riverside-demo.com, look it up directly if the id is not already known, do not guess it.

python3 -c "from app.main import app; print('OK')"

MANUAL VERIFICATION:

Restart backend. Log in as the test staff account. Ask what am I working on or a similar phrasing, confirm a real, scoped answer about that specific staff member's own tasks only, not firm-wide data. Separately, ask something firm-wide, such as which clients have overdue invoices right now, as that same staff account, confirm this is still correctly blocked or answered honestly as out of scope, not answered with real firm-wide data.

Log back in as the firm owner, confirm their access is completely unaffected, full tool set still works exactly as before.

Report pass or fail individually for the staff scoped question, the staff firm-wide question still being blocked, and the owner regression check.

GIT:
git add -A
git commit -m "give staff scoped Concierge access to their own assigned tasks and engagements only, replacing the earlier blanket block, since a staff member asking about their own work is a fundamentally different and lower risk case than asking about firm-wide financial or personnel data, using a separate explicit minimal tool list for the staff role rather than filtering the full tool set, deliberately narrow as a first version rather than full role based access under time pressure"
git pull --rebase origin main
git push origin main