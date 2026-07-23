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

TASK: Restrict Concierge chat access to owner and manager roles only, matching the existing morning briefing restriction

USE: claude sonnet

VERIFY BEFORE ACT:
grep -n "def concierge_chat" -A 20 /home/corby/jamm-os/app/api/concierge/route.py
grep -n "current_user.role in" /home/corby/jamm-os/app/api/concierge/route.py

Confirm the current concierge_chat endpoint has no role restriction beyond blocking client_portal_user, and confirm the exact pattern already used for the morning briefing restriction, current_user.role in ("staff", "client_portal_user"), before writing anything.

WHAT THIS IS:

The firm this product actually serves is now closer to 4 to 40 employees, not the smaller range originally assumed. At that size, a junior staff member having identical Concierge access to the firm owner, including firm-wide accounts receivable, every client's overdue invoices, and every other staff member's individual workload, is a real exposure, not a theoretical one. The morning briefing endpoint already restricts access to owner and manager only, confirmed via current_user.role in ("staff", "client_portal_user") returning a 403. The main chat endpoint has no equivalent restriction at all. This is a deliberate decision to close the gap with the same safe default already established elsewhere in this codebase, not a guess at a new pattern.

CHANGE INSTRUCTIONS:

Add the same role check already used for the morning briefing endpoints to the main concierge_chat endpoint, immediately after the existing client_portal_user check: if current_user.role in ("staff", "client_portal_user"), return a 403 with a clear detail message, something like Concierge access is currently limited to firm owners and managers. Do not silently reuse the exact same generic Access denied text already used elsewhere without a clearer message here, since a staff member hitting this for the first time deserves to understand why, not just see a bare denial.

Do not touch any other endpoint. Do not attempt to build granular per-tool scoping in this task, that is a real, separate feature requiring careful design, this task only closes the immediate full-access exposure with the same safe, already-precedented restriction.

VERIFY AFTER ACT:

grep -n "current_user.role in" /home/corby/jamm-os/app/api/concierge/route.py

Expected: the new check now present in concierge_chat, alongside the existing ones in the briefing endpoints.

python3 -c "from app.main import app; print('OK')"

MANUAL VERIFICATION:

Restart backend. If a staff login exists, log in as staff and confirm the Concierge chat now correctly returns access denied rather than answering normally. If no staff login currently exists to test with, confirm this at minimum by direct verification of the role check logic and note that live staff-account testing is still needed as a follow-up, do not skip reporting this gap.

Confirm the firm owner's own access is completely unaffected, ask a normal question as the owner and confirm it still works exactly as it always has.

Report pass or fail for the owner regression check, and report clearly whether staff access was actually tested live or only verified by code inspection.

GIT:
git add -A
git commit -m "restrict Concierge chat access to owner and manager roles only, matching the existing morning briefing restriction, since the firm size this product now targets, 4 to 40 employees, makes full firm-wide financial and staff data access for junior staff a real exposure rather than a theoretical one, closing the gap with an already-precedented safe default rather than building full granular scoping under time pressure"
git pull --rebase origin main
git push origin main