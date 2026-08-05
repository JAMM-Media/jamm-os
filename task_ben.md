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

TASK: Build the backend foundation for the customizable dashboard: a widget registry, two new tables for per-user and per-firm-default layouts, a migration, and five new endpoints returning real data for the 9 launch-catalog widgets that map 1:1 to the current fixed Dashboard. This batch does not touch the frontend.

USE: claude fable-5

VERIFY BEFORE ACT:

grep -n "app.include_router(dashboard_router" /home/corby/jamm-os/app/main.py

grep -n "class Base" /home/corby/jamm-os/app/db/base_class.py

grep -n -A 30 "def get_dashboard_metrics" /home/corby/jamm-os/app/api/dashboard.py

grep -n -A 5 "def get_wip\|def.*wip" /home/corby/jamm-os/app/api/reports.py

.venv/bin/alembic heads

Confirm dashboard_router is mounted with prefix="/dashboard" in main.py, since the new endpoints go into the existing router in app/api/dashboard.py, not a new file or a new include_router call. Confirm alembic heads shows exactly one head, edf14bcf2539. If it shows more than one head, stop and report back, do not write a migration against a branched history. Confirm the real function name and signature backing the frontend's reportsApi.getWip() call, this is needed for the work_in_progress widget and must not be guessed.

WHAT THIS IS:

The current Dashboard computes all 7 of its sections, MRR, outstanding AR, WIP, overdue engagements, upcoming deadlines, staff utilization, unsigned documents, inline inside one function, get_dashboard_metrics. The customizable dashboard needs each of those as an independently callable piece, since a widget can be added, removed, or refreshed on its own. Rather than writing new query logic per widget, which would duplicate and risk drifting from the real, already-tested calculations, this task extracts each section into its own function and has both the existing get_dashboard_metrics and the new per-widget endpoint call the same functions. This must be behavior-preserving: the existing /dashboard/metrics endpoint should return byte-identical results after the refactor, since other code may still depend on it and this batch does not touch the frontend that calls it.

Two new tables are needed because a layout is per-user, but a firm owner can also set a default layout that seeds new managers on first login, and those are two different things with two different owners. Both store a JSONB array of widget instances rather than one row per widget, since a layout is read and written as a whole unit, not queried by individual widget.

CHANGE INSTRUCTIONS:

Create app/models/dashboard_layout.py with two model classes, DashboardLayout and FirmDefaultDashboardLayout, following the exact conventions already used in app/models/engagement.py: import Base from app.db.base_class, use Mapped and mapped_column, uuid.uuid4 default on id, firm_id as a ForeignKey to firms.id with ondelete="CASCADE" and index=True, and created_at and updated_at using datetime.now(timezone.utc) for both default and onupdate.

DashboardLayout needs id, firm_id, a user_id column that is a ForeignKey to users.id with ondelete="CASCADE", unique=True, and index=True since this is one row per user, a widgets column typed JSONB with default=list holding the array of widget instance objects, and the standard created_at and updated_at.

FirmDefaultDashboardLayout needs id, a firm_id column that is a ForeignKey to firms.id with ondelete="CASCADE" and unique=True since this is one row per firm, the same widgets JSONB column, and the standard timestamps.

A widget instance object inside the widgets array has this shape: instance_id as a uuid string, type_key, grid_x, grid_y, size, minimized as a bool, and config as an object.

Check app/models/firm.py and app/models/user.py for whether relationship() is already used for every other child table on those models. If that convention is already consistently applied, add the matching relationship back-references. If it is not consistently applied, skip it and rely on the foreign key alone rather than introducing a new convention partway through the file.

Create app/core/dashboard_widgets.py as a code-level registry, not a database table, defining the 9 launch-catalog widgets. Each entry needs type_key, display_name, category, allowed_sizes as a list drawn from small, medium, large, config_schema as an empty list since none of these 9 are configurable yet, and role_requirement set to manager_or_above for all 9, matching the existing endpoint-level gate. The 9 entries: revenue_this_month in category overview with allowed_sizes small only, outstanding_ar in overview with small only, unbilled_wip_stat in overview with small only, overdue_engagements_count in overview with small only, work_in_progress in billing with medium and large, upcoming_deadlines in calendar with medium and large, staff_utilization in staff with medium only, overdue_engagements_table in engagements with medium and large, awaiting_signature in documents with medium and large. Note that unbilled_wip_stat and work_in_progress are deliberately two separate widgets, the current Dashboard shows both a small stat total and a separate detailed top-engagements list, and those stay two distinct catalog entries rather than being collapsed into one.

In app/api/dashboard.py, extract each of the 7 sections currently computed inline inside get_dashboard_metrics into its own function taking db and current_firm and returning just that section's data, named _get_mrr_section, _get_outstanding_ar_section, _get_wip_section, _get_overdue_engagements_section, _get_upcoming_deadlines_section, _get_staff_utilization_section, _get_unsigned_documents_section. get_dashboard_metrics should then call all 7 and assemble DashboardMetricsOut exactly as it does today. Do not change any query logic, filters, or calculations while extracting, only move code into named functions.

For the work_in_progress widget specifically, its real source is the reports function confirmed in VERIFY BEFORE ACT, not _get_wip_section, since _get_wip_section backs the small unbilled_wip_stat card, a simpler total, while work_in_progress is the detailed widget showing top engagements. Import and call the real reports function directly for this widget rather than duplicating its logic.

Add five new endpoints to the existing router in app/api/dashboard.py. GET /layout and PUT /layout and GET /widget-catalog and GET /widgets/{type_key}/data are gated require_manager_or_above, matching the existing gate on this router. PUT /firm-default-layout is gated require_firm_owner instead, both dependencies already exist in app/dependencies/roles.py and should be imported, not rewritten.

GET /layout resolves in this order: look up DashboardLayout by user_id, if found return its widgets. If not found, look up FirmDefaultDashboardLayout by firm_id, if found create a new DashboardLayout row for this user seeded with those widgets, commit, and return them. If neither exists, seed from the system default, the 9 launch-catalog widgets positioned to reproduce the current Dashboard's visual order, the 4 small stat cards on row 0 at grid_x 0 through 3, work_in_progress medium on row 1, upcoming_deadlines and staff_utilization side by side on row 2, overdue_engagements_table large on row 3, awaiting_signature large on row 4, then create the DashboardLayout row, commit, and return it.

PUT /layout accepts the full widgets array in the request body and upserts the current user's DashboardLayout row, returning the saved layout.

GET /widget-catalog returns the registry from dashboard_widgets.py filtered to entries whose role_requirement is satisfied by the current user's role. For this batch every entry requires manager_or_above and the whole router already requires that, so every caller sees all 9, but the filtering logic itself needs to be real and correct now, not stubbed, since batch 4 adds entries with stricter requirements that depend on this working.

GET /widgets/{type_key}/data looks up type_key in the registry and returns 404 if not found, otherwise calls the matching extracted section function or the reports WIP function for work_in_progress, scoped by get_current_firm exactly like get_dashboard_metrics does today. No config parameters are needed for this batch, none of the 9 launch widgets are configurable.

PUT /firm-default-layout accepts a widgets array and upserts the FirmDefaultDashboardLayout row for the current firm.

Write the migration by hand rather than with autogenerate, following the exact structure of migrations/versions/edf14bcf2539_add_irs_authorization_warnings_drop_irs_.py, the sa.Uuid() column type, ondelete='CASCADE' foreign key constraints, and index creation via op.f(). Set down_revision to edf14bcf2539. Create both tables from above, including the unique constraint on user_id for dashboard_layouts and on firm_id for firm_default_dashboard_layouts.

VERIFY AFTER ACT:

grep -n "class DashboardLayout\|class FirmDefaultDashboardLayout" /home/corby/jamm-os/app/models/dashboard_layout.py

grep -n "def _get_mrr_section\|def _get_outstanding_ar_section\|def _get_wip_section\|def _get_overdue_engagements_section\|def _get_upcoming_deadlines_section\|def _get_staff_utilization_section\|def _get_unsigned_documents_section" /home/corby/jamm-os/app/api/dashboard.py

grep -n "@router.get(\"/layout\")\|@router.put(\"/layout\")\|@router.get(\"/widget-catalog\")\|@router.get(\"/widgets/{type_key}/data\")\|@router.put(\"/firm-default-layout\")" /home/corby/jamm-os/app/api/dashboard.py

.venv/bin/alembic heads

python3 -c "
import sys
sys.path.insert(0, '/home/corby/jamm-os')
from app.models.dashboard_layout import DashboardLayout, FirmDefaultDashboardLayout
from app.core.dashboard_widgets import WIDGET_REGISTRY
print('models and registry import cleanly, registry has', len(WIDGET_REGISTRY), 'entries')
"

python3 -c "from app.main import app; print('app imports cleanly with new router changes')"

alembic heads must show exactly one head, the new migration's revision id, not the old edf14bcf2539. Run .venv/bin/alembic upgrade head and confirm it applies with no errors. The registry import check must print 9 entries, not a different number.

With the backend running, call GET /dashboard/metrics as the Riverside test firm owner and confirm the response is identical in every field and value to what it returned before this change, this is the proof the extraction in get_dashboard_metrics was behavior-preserving and nothing was lost or altered in moving the logic into separate functions.

MANUAL VERIFICATION:

Log in as owner@riverside-demo.com / Demo2026x.

Call GET /dashboard/layout, either through the /docs page or curl. The first call should return the system-default-seeded layout with all 9 widgets present. Call it again and confirm the second response is identical and came from the now-persisted row rather than re-seeding, you can confirm this by checking the dashboard_layouts table directly in psql and seeing exactly one row for this user.

Call GET /dashboard/widget-catalog and confirm all 9 launch widgets are present in the response.

Call GET /dashboard/widgets/staff_utilization/data and confirm the numbers returned match exactly what the live Dashboard page currently shows for Staff Utilization.

Load the existing /dashboard page in the browser as normal and confirm it looks and behaves exactly as it does today. This batch does not touch the frontend, so nothing should look different yet, if anything looks different that is a real regression and should be reported, not assumed to be expected.

Report back pass or fail on each of the four checks above, and paste the real GET /dashboard/layout response body from the first call.

GIT:

git add -A

git commit -m "add customizable dashboard backend foundation: dashboard_layouts and firm_default_dashboard_layouts tables, widget registry for the 9 launch-catalog widgets, layout resolution and widget-catalog and widget-data endpoints, extracted per-section query functions from get_dashboard_metrics as a behavior-preserving refactor so both the existing endpoint and the new per-widget endpoint share one real source of truth per section"

git pull --rebase origin main

git push origin main

If task.md conflicts on the rebase, resolve with --theirs per standing rule. Any other file conflict, stop and report back rather than resolving automatically.