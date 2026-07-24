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

TASK: Fix get_client_full_snapshot leaving overdue status as model-computed math instead of a precomputed fact

USE: claude sonnet

VERIFY BEFORE ACT:
grep -n "def get_client_full_snapshot" -A 70 /home/corby/jamm-os/app/api/concierge/functions.py
grep -n "def get_overdue_invoices" -A 30 /home/corby/jamm-os/app/api/concierge/functions.py

Confirm the current invoice section of get_client_full_snapshot returns only raw status and due_date with no computed overdue fields, and confirm the exact pattern get_overdue_invoices already uses correctly for computing is_overdue and days_overdue, since the fix should match that established pattern, not invent a new one.

WHAT IS WRONG:

Confirmed live and confirmed against the real database: Marcus and Diana Webb's invoice INV-001 has a genuinely real due_date of 2026-06-24 and status sent, both correctly returned by get_client_full_snapshot with no data error at all. The bug is that this tool returns only the raw due_date and status with no precomputed indication of whether the invoice is actually overdue, leaving the model to determine this itself by comparing the due date against the current date. The model got this wrong, stating the invoice was not yet overdue despite it being genuinely about a month past due, confirmed correct and consistent by get_overdue_invoices elsewhere in the same session. This is the same underlying lesson already learned once tonight with tool_choice forcing, applied here to date arithmetic instead of tool selection, the model cannot be trusted to reliably compute something the backend can compute deterministically and hand over as a settled fact.

CHANGE INSTRUCTIONS:

In the invoice section of get_client_full_snapshot, add the same is_overdue and days_overdue computation already used correctly in get_overdue_invoices, computed in Python against today's real date, not left for the model to infer. Add these as explicit fields on each invoice in the returned list, alongside the existing number, status, and due date fields already there.

Do not change get_overdue_invoices itself, it is already correct. Do not change any other part of get_client_full_snapshot, only the invoice section needs this addition.

VERIFY AFTER ACT:

python3 -c "
from app.db.session import SessionLocal
from app.api.concierge.functions import get_client_full_snapshot
from app.models.client import Client

db = SessionLocal()
client = db.query(Client).filter(Client.name.ilike('%Webb%')).first()
result = get_client_full_snapshot('185314c9-e702-4eab-8600-249848022206', client.id, db)
for inv in result['invoices']:
    print(inv)
db.close()
"

Expected: the INV-001 entry now includes is_overdue true and a real days_overdue number, not just raw status and due date. Paste this real output.

python3 -c "from app.main import app; print('OK')"

MANUAL VERIFICATION:

Restart backend. Ask what's Marcus and Diana Webb's outstanding balance from last year's engagement again, the exact question that surfaced this. Confirm the response now correctly states the invoice is overdue, not not yet overdue, consistent with what get_overdue_invoices already correctly says elsewhere.

Ask about a different client with a genuinely current, not-yet-due invoice if the test data supports it, to confirm the fix correctly reports not overdue in that case too, not just always saying overdue regardless of the real date.

Report pass or fail for both.

GIT:
git add -A
git commit -m "add precomputed is_overdue and days_overdue fields to get_client_full_snapshot's invoice data, since the model was left to determine overdue status itself by comparing a raw due date against the current date and got the math wrong, incorrectly calling a genuinely 29 day overdue invoice not yet overdue, confirmed live and confirmed the underlying due date data itself was correct, this was a reasoning gap not a data error, same underlying lesson as tool_choice forcing applied to date arithmetic instead of tool selection"
git pull --rebase origin main
git push origin main