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

TASK: Wire the eighth and final real page in tonight's Phase 3 scaling pass — a communication-gap banner on the Clients list page

USE: Fable 5

VERIFY BEFORE ACT:

sed -n '239,293p' /home/corby/jamm-os/app/api/concierge/functions.py

sed -n '1,50p' /home/corby/jamm-os/app/api/clients.py

sed -n '1,25p' /home/corby/jamm-os/frontend/src/app/\(app\)/clients/page.tsx

cat /home/corby/jamm-os/frontend/src/components/concierge-inline/ContextualBanner.tsx

Confirm get_client_communication_gap in functions.py already computes gap_count as a real, precise count of active or in_review clients with no outbound event, document request sent, invoice sent, message sent, portal magic link sent, or engagement created, in the last 21 days. Confirm clients.py has GET / and GET /{client_id} both gated with require_staff_or_above, and confirm exactly where GET /{client_id} is declared, since the new route must be placed before it or FastAPI will incorrectly match it as a client id path parameter, the same ordering issue already handled correctly on Engagements and Tasks tonight.

WHAT THIS IS:

This is the eighth and final real, live page in tonight's Phase 3 scaling pass of the inline Concierge redesign, following the identical proven pattern from Billing, the client detail page, Engagements, Tasks, Timesheets, Staff, and Documents. get_client_communication_gap already exists and already correctly computes which active clients have gone quiet, this task exposes that same real, tested number on the Clients list page itself.

CHANGE INSTRUCTIONS:

Backend: add a new GET /communication-gap-summary endpoint in clients.py, placed before the GET /{client_id} route, gated with require_staff_or_above matching the existing style in this file, calling get_client_communication_gap from concierge/functions.py directly with the current firm's id and the db session, returning its result as-is. Do not duplicate or reimplement the gap business rule, only call the existing function, so there is exactly one definition of what counts as a communication gap anywhere in the codebase. Do not modify get_client_communication_gap itself.

Frontend: add a new useFetch call to the new GET /clients/communication-gap-summary endpoint on the Clients list page, matching the existing style of other useFetch calls already in this file. If the returned gap_count is greater than zero, render a ContextualBanner above the existing client list or table, with tone amber, a message stating the real count with correct singular or plural wording, for example X active client(s) have not been contacted in over 3 weeks, and no leading duplicate number, and an action label of Ask Concierge. The onAction callback should call emitConciergeAction twice in sequence, first with type open-panel, then with type prefill-panel-input and prefillMessage set to a clear, real question such as Which clients haven't I contacted recently, reusing the existing open-panel plus auto-send pattern already established tonight. Do not change the existing client table or card views, their data fetching, or any filtering logic already on this page.

VERIFY AFTER ACT:

grep -n "@router.get(\"/communication-gap-summary\"" /home/corby/jamm-os/app/api/clients.py

grep -n "communication-gap-summary" /home/corby/jamm-os/app/api/clients.py

Confirm the new route appears before the line containing GET /{client_id} in this file, not after.

grep -n "gap_count\|communication" /home/corby/jamm-os/frontend/src/app/\(app\)/clients/page.tsx

python3 -c "from app.main import app; print('OK')"

npx tsc --noEmit

MANUAL VERIFICATION:

Restart both servers.

Check whether any real active or in_review clients currently have no outbound event in the last 21 days. If not, report this plainly, real test data may need to be inserted or a real client's engagement status adjusted the same way test data was created for the other pages tonight.

If real gaps exist, confirm the amber banner appears on the Clients list page with correct wording, and confirm clicking Ask Concierge opens the panel, sends the question immediately, and produces an accurate response.

Confirm the existing client table and card views still work exactly as before, unaffected by this change.

Report pass or fail for each check individually, and state plainly whether the banner was seen live or only confirmed structurally.

GIT:

git add -A

git commit -m "wire the eighth and final real page in tonight's Phase 3 scaling pass, an amber ContextualBanner on the Clients list page showing real client communication gap data from a new endpoint that reuses the existing get_client_communication_gap function as its single source of truth, placed before the existing GET client_id route to avoid a path matching conflict, completing the same proven pattern applied to seven other pages tonight"

git pull --rebase origin main

git push origin main