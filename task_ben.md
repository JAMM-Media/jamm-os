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

# Task: Fix incorrect staff role values in Team invite instructions

USE: claude sonnet

## VERIFY BEFORE ACT

grep -n "assign their role (firm_owner, manager, or staff)" /home/corby/jamm-os/app/api/concierge/prompts.py

Confirm the exact current line and its line number before editing.

## WHAT IS WRONG

Confirmed via direct production verification: the Concierge's existing instructions for inviting staff say to "assign their role (firm_owner, manager, or staff)." This does not match the real Invite Team Member form, which has a Role dropdown with exactly three options: Partner, Staff, Manager. The internal database enum value for the firm owner's own row is firm_owner, but that is never an option a user selects from this dropdown when inviting someone, since the firm owner's own account is created at signup, not invited. Telling a user to "assign firm_owner" as a role choice during a staff invite describes a value that does not appear anywhere in the actual UI they are looking at.

## ACTION

File: /home/corby/jamm-os/app/api/concierge/prompts.py

Replace:

Navigate to Settings > Team. Add each staff member by email and assign their role (firm_owner, manager, or staff). Staff receive an email invitation with a magic-link to set their password.

with:

Navigate to Settings > Team. Select Invite Team Member. Enter the new staff member's full name, email address, and a temporary password, then assign their role from the dropdown: Partner, Staff, or Manager. They can change the temporary password after first login.

Do not change any other line in this section. Do not touch any other file.

## VERIFY AFTER ACT

grep -n "Partner, Staff, or Manager" /home/corby/jamm-os/app/api/concierge/prompts.py

Expected: present.

python3 -c "from app.api.concierge.route import router; print('OK')"

Expected: OK, no import errors.

## MANUAL VERIFICATION

1. Restart the backend.
2. Ask the Concierge how to invite a new staff member.
3. Confirm the response describes the real form fields (full name, email, temporary password, role dropdown with Partner/Staff/Manager) rather than the old firm_owner/manager/staff wording.

Report the exact response text at step 3.

## GIT

cd /home/corby/jamm-os
git add -A
git commit -m "fix: Team invite instructions now describe the real Invite Team Member form fields and role options (Partner, Staff, Manager) instead of internal database enum values that never appear in the UI"
git pull --rebase origin main
git push origin main

If conflicts on task.md use --theirs. Conflicts on source files use --ours.