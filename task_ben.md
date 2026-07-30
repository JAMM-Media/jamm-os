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

TASK: Align get_deadline_calendar with the richer, already-established deadline logic in deadline_watch, then wire the ninth real page of the inline Concierge redesign onto the Calendar page

USE: Fable 5

VERIFY BEFORE ACT:

sed -n '106,150p' /home/corby/jamm-os/app/api/engagements.py

sed -n '581,617p' /home/corby/jamm-os/app/api/concierge/functions.py

grep -rn "get_deadline_calendar" /home/corby/jamm-os/app/ --include="*.py"

sed -n '1,30p' /home/corby/jamm-os/frontend/src/app/\(app\)/calendar/page.tsx

cat /home/corby/jamm-os/frontend/src/components/concierge-inline/ContextualBanner.tsx

Confirm get_deadline_calendar is only ever called from one place in the entire codebase, the tool dispatch in concierge/route.py, meaning its logic can be safely changed without affecting any other caller. Confirm deadline_watch's real, richer logic: it uses extended_deadline when set, falling back to filing_deadline, excludes engagements with status completed or archived, and requires is_active to be true, none of which get_deadline_calendar currently does. Confirm this real discrepancy exists before changing anything.

WHAT THIS IS:

Two definitions of upcoming deadline currently exist in this codebase. The real one, deadline_watch, already powers the Dashboard's Tax Deadline Watch section, correctly uses the extended deadline when one has been granted, and correctly excludes completed, archived, or inactive engagements. The Concierge's own tool, get_deadline_calendar, uses a simpler, less accurate rule, plain filing_deadline only, no status or active exclusion. This was found while considering whether to add a ninth inline redesign page to the Calendar page tonight, and the decision was made to fix the real inconsistency first, so the Concierge always answers deadline questions using the same real logic the product itself already uses, rather than building a new page on top of a known-inaccurate tool.

CHANGE INSTRUCTIONS:

In functions.py, update get_deadline_calendar so its per-engagement filtering and effective deadline calculation exactly matches deadline_watch: use extended_deadline when set, otherwise filing_deadline, exclude engagements with status completed or archived, and require is_active to be true. Keep get_deadline_calendar's own function signature, its firm_id and db and days_ahead parameters, and its existing return shape, including deadline_count, exactly as they are, only the underlying business logic changes. Do not touch deadline_watch itself, it is already correct and is the source of truth being matched.

Backend: add a new GET /deadline-summary endpoint in engagements.py, gated with require_staff_or_above matching the existing style in this file, calling the now-corrected get_deadline_calendar directly with the current firm's id, the db session, and a 14 day window, returning its result as-is. Do not duplicate the deadline logic in this new endpoint, only call the function.

Frontend: add a new useFetch call to the new GET /engagements/deadline-summary endpoint on the Calendar page, matching the existing data fetching style already in this file. If the returned deadline_count is greater than zero, render a ContextualBanner near the top of the page, above the calendar grid, with tone amber, a message stating the real count with correct singular or plural wording, for example X filing deadline(s) in the next 14 days, and no leading duplicate number, and an action label of Ask Concierge. The onAction callback should call emitConciergeAction twice in sequence, first with type open-panel, then with type prefill-panel-input and prefillMessage set to a clear, real question such as What deadlines are coming up in the next 14 days, reusing the existing open-panel plus auto-send pattern already established tonight. Do not change the existing calendar grid, its event rendering, or any other logic already on this page.

VERIFY AFTER ACT:

grep -n "extended_deadline\|is_active" /home/corby/jamm-os/app/api/concierge/functions.py | grep -A 2 -B 2 "584\|deadline_calendar"

python3 -c "
import sys
sys.path.insert(0, '/home/corby/jamm-os')
from app.api.concierge.functions import get_deadline_calendar
print('function updated, real check requires live data')
"

grep -n "@router.get(\"/deadline-summary\"" /home/corby/jamm-os/app/api/engagements.py

grep -n "deadline_count\|deadline-summary" /home/corby/jamm-os/frontend/src/app/\(app\)/calendar/page.tsx

python3 -c "from app.main import app; print('OK')"

npx tsc --noEmit

MANUAL VERIFICATION:

Restart both servers.

Check whether any real engagements currently have a filing or extended deadline within the next 14 days, and whether that number matches what the Dashboard's own Tax Deadline Watch section shows for the same real data, confirming the two are now actually consistent with each other, not just structurally similar.

If real deadlines exist, confirm the amber banner appears on the Calendar page with correct wording, and confirm clicking Ask Concierge opens the panel, sends the question immediately, and produces an accurate response that agrees with what the Dashboard shows.

Confirm the existing calendar grid and its events still render exactly as before, unaffected by this change.

Report pass or fail for each check individually, and explicitly confirm whether the Concierge's answer and the Dashboard's own number now agree, since that agreement is the actual point of this task, not just the new banner existing.

GIT:

git add -A

git commit -m "align get_deadline_calendar with the richer, already-correct deadline logic already powering the Dashboard's Tax Deadline Watch, extended deadline fallback, excluding completed, archived, or inactive engagements, fixing a real discrepancy where the Concierge and the product itself could have disagreed on which deadlines are upcoming, then wire the ninth real page of the inline Concierge redesign, an amber ContextualBanner on the Calendar page using this now-corrected, single source of truth"

git pull --rebase origin main

git push origin main