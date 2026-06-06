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

TASK 3 OF 3: Fill in missing write_audit_log calls

Pre-task:
VERIFY BEFORE ACT:
grep -rn "write_audit_log" /home/corby/jamm-os/app/api/clients.py 2>/dev/null | head -5
grep -rn "write_audit_log" /home/corby/jamm-os/app/api/invoices.py 2>/dev/null | head -5
grep -rn "write_audit_log" /home/corby/jamm-os/app/api/irs_authorizations.py 2>/dev/null | head -5
Paste all three before touching anything.

For each file that shows zero results, add write_audit_log calls
on the significant actions following the same pattern already used
in engagements.py and users.py.

File: app/api/clients.py
Actions to log:
- client created: action='client.created', entity_type='client', entity_id=new_client.id
- client updated: action='client.updated', entity_type='client', entity_id=client.id
- client deleted: action='client.deleted', entity_type='client', entity_id=client_id

File: app/api/invoices.py (if it exists)
Actions to log:
- invoice created: action='invoice.created', entity_type='invoice', entity_id=invoice.id
- invoice sent: action='invoice.sent', entity_type='invoice', entity_id=invoice.id
- invoice marked paid: action='invoice.paid', entity_type='invoice', entity_id=invoice.id

File: app/api/irs_authorizations.py (if it exists)
Actions to log:
- IRS auth created: action='irs_auth.created', entity_type='irs_authorization', entity_id=auth.id
- IRS auth sent: action='irs_auth.sent', entity_type='irs_authorization', entity_id=auth.id

For each file, follow this pattern exactly:
1. Add import at top: from app.services.audit_service import write_audit_log
2. After the successful DB operation, call write_audit_log with the correct params
3. Never let a failed audit log write surface as a user error -- audit_service is already fire-and-forget safe

VERIFY AFTER ACT:
grep -rn "write_audit_log" /home/corby/jamm-os/app/api/clients.py | head -5
grep -rn "write_audit_log" /home/corby/jamm-os/app/api/invoices.py 2>/dev/null | head -5
grep -rn "write_audit_log" /home/corby/jamm-os/app/api/irs_authorizations.py 2>/dev/null | head -5
Confirm results appear for each file that was modified.
python3 -c "from app.main import app; print('OK')"
Must pass before stopping.
Restart the backend.

Browser tests:
Test 1 -- Audit Log tab visible:
Navigate to Settings. Confirm Audit Log tab appears.
Click it. Confirm the table loads with entries.

Test 2 -- Entries are real:
Confirm at least some entries appear -- logins, document events, etc.
Read a few rows and confirm they make sense.

Test 3 -- Filter works:
Type "login" in the action filter and click Filter.
Confirm only login-related entries appear.

Test 4 -- Entity type filter:
Select Document from the entity type dropdown.
Confirm only document entries appear.

Test 5 -- Staff cannot see it:
This requires a staff-level login to test. Skip if no staff account available.TASK: Fix audit log router prefix -- main.py

VERIFY BEFORE ACT:
grep -n "audit_log" /home/corby/jamm-os/app/main.py
Paste output before touching anything.

Find exactly:
app.include_router(audit_log_router, prefix="/api/v1")

Replace with:
app.include_router(audit_log_router)

VERIFY AFTER ACT:
grep -n "audit_log" /home/corby/jamm-os/app/main.py
Confirm prefix="/api/v1" is gone.
python3 -c "from app.api.audit_log import router; print('OK')"
Restart the backend.

Browser test:
Navigate to Settings > Audit Log.
Confirm login entries appear in the table.