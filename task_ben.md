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

# ENVIRONMENT SANITY CHECK — MANDATORY BEFORE ANY OTHER STEP
This section exists because Claude Code twice reported stale route-conflict files (frontend/src/app/settings/, frontend/src/app/calendar/, frontend/src/app/(dashboard)/) as real, current, build-blocking evidence and asked for permission to delete them. Both times, those files did not exist in the real repo at /home/corby/jamm-os. They existed only on the separate Windows-side checkout at /mnt/c/Users/corby/jamm-os, a pre-rename leftover copy that is for viewing only and is never the source of truth. Some tool call had actually resolved against that path instead of the real WSL repo, and reported what it found there as if it were current.

Before running any other command in this task:
1. Run: pwd — the output must be exactly /home/corby/jamm-os or a path underneath it. If it is not, stop and cd /home/corby/jamm-os before doing anything else.
2. State explicitly in the report, as its own line, that no command in this task read, listed, or resolved any path under /mnt/c/Users or any other Windows-side location. This is not optional boilerplate, it is a real claim that must be true.
3. If at any point a command needs to check whether something exists "on disk," that means the real WSL filesystem under /home/corby/jamm-os, never the Windows copy, even implicitly, even as a fallback.

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

# REPORTING DISCIPLINE — MANDATORY FOR EVERY TASK
This section exists because a past session confidently claimed specific files were stale untracked leftovers safe to delete, citing a real commit hash correctly, then drew a false conclusion from it. The files did not exist on disk at all. The commit was real. The conclusion was not. That is the failure mode this section guards against: not sloppy guessing, but a plausible-sounding narrative that outran the actual evidence.

- Quote literal command output verbatim in every summary. Never paraphrase output, never assert a conclusion in place of showing the output it came from. If a claim cannot be backed by pasted, real output in the same message, it does not go in the summary as fact.
- If evidence is ambiguous, incomplete, contradictory, or simply absent, say so explicitly and stop. Do not fill a gap in the evidence with a story that sounds coherent. An honest "I don't have enough evidence to conclude this" is always the correct output when that is the true state.
- Never take any action, including deletions, fixes, or refactors, beyond what CHANGE INSTRUCTIONS explicitly names, even if something discovered mid-task seems to obviously justify it. Surface it as a finding in the report and wait for a real instruction. Diagnosis and action are separate steps, not one motion.
- Before claiming any file doesn't belong, is stale, is dead code, or should be deleted, confirm both that it exists on disk (ls -la) and its real git tracking status (git status --short and git ls-files) in the same message as the claim itself, not as a follow-up only produced if challenged.

---

# Section 3 - The task

TASK: Add the 7 remaining widget types to the registry and wire GET /dashboard/widgets/{type_key}/data to accept and use per-instance config for the widgets that need it (client_id for the two client-specific widgets, assignee and status filters for My Tasks). This batch is backend only, no frontend gallery yet, that is batch 4b.

USE: claude fable-5

ENVIRONMENT SANITY CHECK:

pwd

State plainly that no path in this task resolves against /mnt/c/Users or any Windows-side copy.

VERIFY BEFORE ACT:

grep -n -A 30 "def get_task_status" app/api/concierge/functions.py

grep -n -A 20 "def compute_client_health" app/services/client_health_service.py

grep -n -A 10 "def get_client_full_snapshot" app/api/concierge/functions.py

grep -n -A 10 "def get_outstanding_document_requests\|def get_time_tracking_detail\|def get_recent_firm_chat_activity" app/api/concierge/functions.py

Paste the real output of all four. Confirm the exact current signature of get_task_status, compute_client_health, and get_client_full_snapshot, since these three are the ones that need real parameters added or passed through, not just registered.

WHAT THIS IS:

Batch 1 built the registry, layout endpoints, and data endpoint for the 9 launch-catalog widgets, all firm-wide with no per-instance configuration. This batch adds the 7 remaining widgets from the spec's fuller catalog: My Tasks, Client Health Snapshot, Client Communication Gap, Outstanding Document Requests, Unbilled Hours, Single Client Quick View, and Recent Firm Chat Activity. Three of these are configurable: Client Health Snapshot and Single Client Quick View both need a client_id, since they show one specific client's data, not firm-wide data, and My Tasks needs an optional assignee filter and an optional status filter.

get_task_status currently has no filter parameters at all, it returns every incomplete task firm-wide. Adding assignee_id and status_filter as new optional parameters to this function is parameterizing existing, already-tested logic, not inventing new business logic, the underlying query and its correctness are unchanged, only which rows get returned changes based on what's passed in. This is different from the client_id case, where compute_client_health and get_client_full_snapshot already require a client_id as a real parameter, since they were built as per-client tools for the Concierge, so those two just need their existing required parameter passed through from the widget's config, no new logic there at all.

The data endpoint itself needs to accept config as query parameters and only apply them to the three widgets that use them, every other widget type ignores any config passed to it, matching a firm-wide fixed view exactly as before.

CHANGE INSTRUCTIONS:

In app/core/dashboard_widgets.py, add 7 new entries to the registry. my_tasks in category tasks, allowed_sizes medium and large, config_schema with an assignee_id field (type staff_picker, not required, meaning unset shows all staff's tasks) and a status_filter field (type select, not required), role_requirement manager_or_above. client_health_snapshot in category clients, allowed_sizes small and medium, config_schema with a required client_id field (type client_picker), role_requirement manager_or_above. client_communication_gap in category clients, allowed_sizes medium and large, no config_schema, role_requirement manager_or_above. outstanding_document_requests in category documents, allowed_sizes medium and large, no config_schema, role_requirement manager_or_above. unbilled_hours in category billing, allowed_sizes medium and large, no config_schema, role_requirement manager_or_above. single_client_quick_view in category clients, allowed_sizes small and medium, config_schema with a required client_id field, role_requirement manager_or_above. recent_firm_chat_activity in category overview, allowed_sizes medium and large, no config_schema, role_requirement manager_or_above.

Add assignee_id and status_filter as new optional parameters to get_task_status in app/api/concierge/functions.py, defaulting to None, meaning no filtering, so any existing caller of this function that does not pass them gets identical behavior to today. When assignee_id is provided, filter the task rows to that user. When status_filter is provided, filter to that status. Do not change the query's existing joins or the shape of what it returns beyond this filtering, this is not a rewrite.

In the GET /dashboard/widgets/{type_key}/data endpoint in app/api/dashboard.py, accept an optional config query parameter as a JSON-encoded string, or individual optional query parameters for client_id, assignee_id, and status_filter, whichever is simpler given the existing endpoint's real current parameter style, check how other endpoints in this file already accept optional filters before choosing. For my_tasks, pass assignee_id and status_filter through to get_task_status if provided. For client_health_snapshot, require client_id, return a 400 with a clear message if it's missing, and call compute_client_health with it. For single_client_quick_view, require client_id the same way and call get_client_full_snapshot with it. For every other type_key, including all 9 from batch 1 and the 4 new non-configurable ones in this batch, ignore any config parameters entirely, they are not used.

Extend the _WIDGET_DISPATCH mapping to include all 7 new type_keys pointing at their real functions, get_client_communication_gap for client_communication_gap, get_outstanding_document_requests for outstanding_document_requests, get_time_tracking_detail for unbilled_hours, get_recent_firm_chat_activity for recent_firm_chat_activity, compute_client_health for client_health_snapshot, get_client_full_snapshot for single_client_quick_view, get_task_status for my_tasks.

VERIFY AFTER ACT:

grep -n "my_tasks\|client_health_snapshot\|client_communication_gap\|outstanding_document_requests\|unbilled_hours\|single_client_quick_view\|recent_firm_chat_activity" app/core/dashboard_widgets.py

python3 -c "
import sys
sys.path.insert(0, '/home/corby/jamm-os')
from app.core.dashboard_widgets import WIDGET_REGISTRY
print('registry has', len(WIDGET_REGISTRY), 'entries')
"

This must print 16, the original 9 plus these 7.

cd /home/corby/jamm-os
python3 -c "from app.main import app; print('app imports cleanly')"

MANUAL VERIFICATION:

Restart the backend. Using a real token as owner@riverside-demo.com, call GET /dashboard/widget-catalog and confirm all 16 widgets are present. Call GET /dashboard/widgets/client_health_snapshot/data with no client_id and confirm it returns a real 400 error, not a 500 or a silent empty response. Call it again with a real client_id from the Riverside test data and confirm it returns real health data for that specific client. Call GET /dashboard/widgets/my_tasks/data with no config and confirm it returns tasks firm-wide same as before this change, then call it again with an assignee_id for one real staff member and confirm the results are actually filtered to that person.

GIT:

git add -A
git commit -m "add the 7 remaining launch-catalog widgets to the registry and wire per-instance config through the widget data endpoint: client_health_snapshot and single_client_quick_view require a client_id and reuse the existing per-client Concierge functions unchanged, my_tasks gained new optional assignee_id and status_filter parameters on get_task_status, parameterizing existing logic rather than inventing new business logic, every other widget type ignores config entirely and remains firm-wide"
git pull --rebase origin main
git push origin main

If task.md conflicts on the rebase, resolve with --theirs. Any other file conflict, stop and report back.