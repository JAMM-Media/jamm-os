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

TASK: Wire the sixth real page of the inline Concierge redesign — an overloaded-staff banner on the Staff page, gated to manager or above

USE: Fable 5

VERIFY BEFORE ACT:

sed -n '187,223p' /home/corby/jamm-os/app/api/concierge/functions.py

sed -n '1,30p' /home/corby/jamm-os/app/api/users.py

sed -n '1,30p' /home/corby/jamm-os/frontend/src/app/\(app\)/staff/page.tsx

cat /home/corby/jamm-os/frontend/src/components/concierge-inline/ContextualBanner.tsx

Confirm get_staff_capacity in functions.py already computes overloaded_count as a real, precise count of active staff whose hours this week reach or exceed 100 percent of a 40 hour standard week. Confirm users.py already imports require_staff_or_above, require_firm_owner, and get_current_firm, and confirm there is no require_manager_or_above import yet in this file, it will need to be added. Confirm the Staff page already redirects staff-role users away entirely before any content renders, confirming this page is already restricted to manager and owner roles at the page level.

WHAT THIS IS:

This is the sixth real, live page of the inline Concierge redesign, following the same proven pattern from Billing, the client detail page, Engagements, Tasks, and Timesheets tonight. This one carries a deliberate access decision: get_staff_capacity returns firm-wide utilization data across every staff member, real hours worked and overload status per person, which is sensitive personnel information. This session already established a real security principle earlier tonight, restricting staff-role Concierge access away from firm-wide financial and personnel data. This new endpoint follows that same principle directly, gated to manager or above rather than the staff-or-above pattern used on every other page tonight, since staff should not be able to query every other staff member's utilization data.

CHANGE INSTRUCTIONS:

Backend: add require_manager_or_above to the existing roles import in users.py. Add a new GET /capacity endpoint in this file, gated with require_manager_or_above, calling get_staff_capacity from concierge/functions.py directly with the current firm's id and the db session, returning its result as-is. Do not duplicate or reimplement the utilization calculation, only call the existing function, so there is exactly one definition of this anywhere in the codebase. Do not modify get_staff_capacity itself.

Frontend: add a new useFetch call to the new GET /users/capacity endpoint on the Staff page, matching the existing style already in this file, and only fire this fetch when the current user's role is manager or firm_owner, matching the access restriction already established on this page, not for the staff role case that redirects away. If the returned overloaded_count is greater than zero, render a ContextualBanner above the existing roster or credentials content, with tone amber, a message stating the real count with correct singular or plural wording, for example X staff member(s) are at or above full capacity this week, and no leading duplicate number, and an action label of Ask Concierge. The onAction callback should call emitConciergeAction twice in sequence, first with type open-panel, then with type prefill-panel-input and prefillMessage set to the literal text Which staff members are overloaded this week, reusing the existing open-panel plus auto-send pattern already established tonight. Do not change the existing Roster or Credentials tab content or their data fetching.

VERIFY AFTER ACT:

grep -n "require_manager_or_above" /home/corby/jamm-os/app/api/users.py

grep -n "@router.get(\"/capacity\"" /home/corby/jamm-os/app/api/users.py

grep -n "overloaded" /home/corby/jamm-os/frontend/src/app/\(app\)/staff/page.tsx

python3 -c "from app.main import app; print('OK')"

npx tsc --noEmit

MANUAL VERIFICATION:

Restart both servers.

Since real staff time entries were mostly cleaned up as test data was removed tonight, check whether any active staff member currently has 40 or more hours logged this week. If not, report this clearly rather than guessing, real test data may need to be inserted the same way it was for Timesheets before this can be visually confirmed.

If a real overloaded staff member exists, confirm the amber banner appears on the Staff page with correct wording, and confirm clicking Ask Concierge opens the panel, sends the question immediately, and produces an accurate response naming the real overloaded staff member.

Log in or switch to the staff-role test account and confirm this page still correctly blocks staff from seeing it at all, unaffected by this change.

Report pass or fail for each check individually, and state plainly whether the banner itself was actually seen live or only confirmed structurally through code, since real data may not currently exist to trigger it.

GIT:

git add -A

git commit -m "wire the sixth real page of the inline Concierge redesign, an amber ContextualBanner on the Staff page showing real overloaded-staff data from a new endpoint that reuses the existing get_staff_capacity function as its single source of truth, deliberately gated to manager or above rather than the staff-or-above pattern used on every other page tonight, since firm-wide staff utilization data is sensitive personnel information and this follows the same staff-data-access principle established earlier tonight"

git pull --rebase origin main

git push origin main