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

TASK: Wire the third real page of the inline Concierge redesign — a stalled-engagements banner on the Engagements page

USE: Fable 5

VERIFY BEFORE ACT:

sed -n '36,68p' /home/corby/jamm-os/app/api/concierge/functions.py

grep -n "@router.get\|require_staff_or_above" /home/corby/jamm-os/app/api/engagements.py | head -10

sed -n '1,25p' /home/corby/jamm-os/frontend/src/app/\(app\)/engagements/page.tsx

cat /home/corby/jamm-os/frontend/src/components/concierge-inline/ContextualBanner.tsx

Confirm get_stalled_engagements in functions.py is the single real source of truth for the stalled business rule (updated_at older than 14 days, status not completed or archived). Confirm engagements.py has no existing stalled-specific route and its read endpoints are gated with require_staff_or_above, matching the same pattern already used for invoices.py. Confirm the engagements page currently has no awareness of a stalled-specific endpoint. Confirm ContextualBanner's current real shape, including its already-fixed count-to-message spacing, before using it.

WHAT THIS IS:

This is the third real, live page of the inline Concierge redesign, following the same pattern already proven twice tonight on Billing and the client detail page. Stalled engagements is a strong fit because the underlying data and the chat question that answers it, how many stalled engagements do I have, were both specifically hardened earlier tonight, the OPTIONS marker safety net was extended to this exact tool after it was found live to lack the same reliable clickable client name buttons already working for overdue invoices. This task reuses that already-proven, already-reliable question rather than inventing new behavior.

CHANGE INSTRUCTIONS:

Backend: add a new GET /stalled endpoint in engagements.py, gated with require_staff_or_above matching the existing style in this file, calling get_stalled_engagements from concierge/functions.py directly with the current firm's id and the db session, returning its result as-is. Do not duplicate or reimplement the stalled business rule, only call the existing function, so there is exactly one definition of what counts as stalled anywhere in the codebase. Do not modify get_stalled_engagements itself.

Frontend: add a new useFetch call to the new GET /engagements/stalled endpoint on the Engagements page, matching the existing style of other useFetch calls already in this file. If the returned stalled count is greater than zero, render a ContextualBanner above the existing engagement list or table, with tone amber, a message stating the real count with correct singular or plural wording and no leading duplicate number, matching the fix already applied to the Billing banner, and an action label of Ask Concierge. The onAction callback should call emitConciergeAction twice in sequence, first with type open-panel, then with type prefill-panel-input and prefillMessage set to the exact literal text How many stalled engagements do I have, so this reuses the existing tool_choice-forced, already-hardened path and the already-implemented auto-send behavior rather than inventing new behavior. Do not change the existing engagement table or card views, their data fetching, or any filtering logic already on this page.

VERIFY AFTER ACT:

grep -n "@router.get(\"/stalled\"" /home/corby/jamm-os/app/api/engagements.py

grep -n "stalled" /home/corby/jamm-os/frontend/src/app/\(app\)/engagements/page.tsx

python3 -c "from app.main import app; print('OK')"

npx tsc --noEmit

MANUAL VERIFICATION:

Restart both servers.

Visit the Engagements page with at least one real stalled engagement present. Confirm the amber banner appears above the list, showing the real count and correct wording, with the count and message reading as one sentence, not duplicated.

Click Ask Concierge on the banner. Confirm the panel opens and the stalled engagements question sends immediately, with a real response showing clickable client name buttons, matching the already-verified reliable behavior from earlier tonight.

Confirm the existing engagement table and card views still work exactly as before, unaffected by this change.

Report pass or fail for each check individually.

GIT:

git add -A

git commit -m "wire the third real page of the inline Concierge redesign, an amber ContextualBanner on the Engagements page showing real stalled engagement data from a new endpoint that reuses the existing get_stalled_engagements function as its single source of truth, with the banner's action reusing the exact chat question already hardened earlier tonight with the OPTIONS marker safety net, and the auto-send behavior already established for the Billing banner"

git pull --rebase origin main

git push origin main