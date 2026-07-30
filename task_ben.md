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

TASK: Wire the fifth real page of the inline Concierge redesign — an unbilled-hours banner on the Timesheets page

USE: Fable 5

VERIFY BEFORE ACT:

sed -n '1040,1088p' /home/corby/jamm-os/app/api/concierge/functions.py

sed -n '1,55p' /home/corby/jamm-os/app/api/time_entries.py

sed -n '1,45p' /home/corby/jamm-os/frontend/src/app/\(app\)/timesheets/page.tsx

cat /home/corby/jamm-os/frontend/src/components/concierge-inline/ContextualBanner.tsx

Confirm get_time_tracking_detail in functions.py already computes unbilled_billable_hours_this_month_all_engagements as a real, precise aggregate, real billable hours not yet billed, dated this month. Confirm time_entries.py has no existing endpoint exposing just this aggregate, and confirm its existing endpoints are gated with require_staff_or_above, matching the pattern already used on every other page tonight. Confirm the Timesheets page's real current structure before adding anything.

WHAT THIS IS:

This is the fifth real, live page of the inline Concierge redesign, following the same proven pattern from Billing, the client detail page, Engagements, and Tasks tonight. Unlike those four, this is the first page in the series where the underlying real data was confirmed completely empty in this environment, zero time entries existed for this firm at all, so a real test row was inserted directly by hand tonight specifically to verify this page live, the same way test data has been inserted for other verifications tonight. This is also the first page in the series using a chat question, how many unbilled hours do I have this month, that was not specifically hardened earlier tonight with the tool_choice or OPTIONS marker treatment the way overdue invoices and stalled engagements were, so live testing here deserves real scrutiny, not an assumption that it will behave identically well.

CHANGE INSTRUCTIONS:

Backend: add a new GET /unbilled-summary endpoint in time_entries.py, gated with require_staff_or_above matching the existing style in this file, calling get_time_tracking_detail from concierge/functions.py directly with the current firm's id and the db session, returning its result as-is. Do not duplicate or reimplement the unbilled hours calculation, only call the existing function, so there is exactly one definition of this number anywhere in the codebase. Do not modify get_time_tracking_detail itself.

Frontend: add a new useFetch call to the new GET /time-entries/unbilled-summary endpoint on the Timesheets page, matching the existing style already in this file. If the returned unbilled_billable_hours_this_month_all_engagements value is greater than zero, render a ContextualBanner above the existing tab content, with tone amber, a message stating the real hours value rounded to one decimal place with correct wording, for example X unbilled billable hours this month across all engagements, and no leading duplicate number, and an action label of Ask Concierge. The onAction callback should call emitConciergeAction twice in sequence, first with type open-panel, then with type prefill-panel-input and prefillMessage set to the literal text How many unbilled hours do I have this month, reusing the existing open-panel plus auto-send pattern already established tonight. Do not change any of the existing tab components or their data fetching.

VERIFY AFTER ACT:

grep -n "@router.get(\"/unbilled-summary\"" /home/corby/jamm-os/app/api/time_entries.py

grep -n "unbilled" /home/corby/jamm-os/frontend/src/app/\(app\)/timesheets/page.tsx

python3 -c "from app.main import app; print('OK')"

npx tsc --noEmit

MANUAL VERIFICATION:

Restart both servers.

Visit the Timesheets page. A real test time entry of 6.5 unbilled billable hours was inserted by hand tonight specifically for this check. Confirm the amber banner appears, showing 6.5 unbilled billable hours this month across all engagements, count and message reading as one sentence, not duplicated.

Click Ask Concierge on the banner. Confirm the panel opens and the question sends immediately. Since this exact question was not specifically hardened tonight, read the actual response carefully rather than assuming it is correct, and report the real response text back exactly as shown, do not summarize or paraphrase it.

Confirm the existing Timesheets tabs and their data still work exactly as before, unaffected by this change.

Report pass or fail for each check individually, and flag anything about the chat response that seems off, since this is the first ungoverned question in tonight's series.

GIT:

git add -A

git commit -m "wire the fifth real page of the inline Concierge redesign, an amber ContextualBanner on the Timesheets page showing real unbilled billable hours from a new endpoint that reuses the existing get_time_tracking_detail function as its single source of truth, tested against a real hand-inserted time entry since this firm had zero time tracking data seeded, and flagged as the first page in tonight's series using a chat question that was not specifically hardened with the tool_choice or OPTIONS marker treatment"

git pull --rebase origin main

git push origin main