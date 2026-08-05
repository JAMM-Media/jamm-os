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

TASK: Replace the fixed-row Dashboard layout with a react-grid-layout canvas that renders the 9 launch-catalog widgets from the real GET /dashboard/layout endpoint, in view-only mode, no drag, no resize, no edit mode yet. This batch proves the grid library integration works with real data and real widget positions before any interaction is added on top in the next batch.

USE: claude fable-5

VERIFY BEFORE ACT:

cd /home/corby/jamm-os/frontend
npm view react-grid-layout peerDependencies version

grep -n -A 8 "def _get_mrr_section" /home/corby/jamm-os/app/api/dashboard.py
grep -n -A 8 "def _get_outstanding_ar_section" /home/corby/jamm-os/app/api/dashboard.py
grep -n -A 12 "def _get_overdue_engagements_section" /home/corby/jamm-os/app/api/dashboard.py
grep -n -A 8 "def _get_unsigned_documents_section" /home/corby/jamm-os/app/api/dashboard.py
grep -n "return {" /home/corby/jamm-os/app/api/dashboard.py

Confirm react-grid-layout's peer dependency range allows React 19 (it should show react >= 16.3.0 or similar open range). If it requires an exact older React major, stop and report back before installing anything.

For each of the four grep -A blocks, look at the actual return statement of that function, not just the query. The expected shapes, based on the original DashboardMetricsOut schema in app/schemas/dashboard.py, are: _get_mrr_section returns a dict with keys mrr and mrr_invoice_count. _get_outstanding_ar_section returns a dict with keys outstanding_ar, outstanding_ar_count, and oldest_overdue_days. _get_overdue_engagements_section returns a dict with keys overdue_engagement_count and overdue_engagements, where overdue_engagements is a list of objects each shaped like OverdueEngagementItem in the schema file. _get_unsigned_documents_section returns a dict with keys unsigned_document_count and unsigned_documents, a list shaped like UnsignedDocumentItem. If any of these four functions returns different key names than expected, stop and report back the real shape before writing any frontend code against it, do not silently adapt to a guessed shape.

WHAT THIS IS:

The current /dashboard page computes everything from one bulk call to GET /dashboard/metrics and lays out 8 sections in fixed JSX rows. The customizable dashboard needs each widget to be independently positioned and independently fetched, since a widget can eventually be added, removed, or resized on its own without affecting the others. This batch switches the page from that fixed layout to a real grid library, react-grid-layout, driven by the real saved layout from GET /dashboard/layout, with each widget instance fetching its own data from GET /dashboard/widgets/{type_key}/data rather than one shared bulk response.

This is deliberately scoped to view-only. No add, remove, resize, drag, or minimize in this batch, those are batch 3. The reason to build this in isolation first is that react-grid-layout is a new dependency this codebase has never used, and wiring a new library to real positions and real data is the part most likely to reveal a real problem. Better to find that now, with a small and reversible batch, than after edit mode is layered on top of it.

Every widget's visual rendering should reuse the exact existing presentational components already in frontend/src/app/(app)/dashboard/page.tsx: MetricCard for the four stat widgets, WIPWidget unchanged for work_in_progress, UpcomingDeadlinesList for upcoming_deadlines, StaffUtilizationPanel for staff_utilization, OverdueEngagementsTable for both overdue_engagements_count and overdue_engagements_table, and UnsignedDocumentsTable for awaiting_signature. None of these need to be rewritten, only re-fed with per-widget data instead of the one bulk metrics response, and placed inside grid items instead of fixed divs. Do not add a second layer of card chrome, border, or header around these components, they already render their own complete visual container, wrapping them in another bordered box would double the border and look wrong.

overdue_engagements_count is the small stat card showing just a number, and overdue_engagements_table is the full table below it, both call the same backend function and both already exist as separate pieces of UI today (the MetricCard labeled Overdue Engagements, and the separate OverdueEngagementsTable section), they just now become two separate widget instances instead of two hardcoded sections.

CHANGE INSTRUCTIONS:

Install react-grid-layout as a real dependency, not a dev dependency, in frontend/package.json. Import its stylesheet, react-grid-layout/css/styles.css, and react-resizable's stylesheet, react-resizable/css/styles.css, as global imports inside frontend/src/app/layout.tsx alongside the existing globals.css import, since Next's App Router only allows global stylesheet imports in the root layout.

Add two new methods to frontend/src/lib/api/dashboard.ts: getLayout, which calls GET /dashboard/layout and returns the widgets array, and getWidgetData, which takes a type_key string and calls GET /dashboard/widgets/{type_key}/data. Type the widgets array using a new DashboardWidgetInstance interface with fields instance_id, type_key, grid_x, grid_y, size, minimized, and config, matching the real shape confirmed in the prior batch's manual verification.

Add a size-to-grid-span mapping as a plain constant, not fetched from the backend: small maps to a width of 1 column, medium to 2 columns, large to 4 columns. This is not a guess, it matches the real seeded positions already confirmed live: the four small stat cards sit side by side at grid_x 0 through 3 in a 4 column grid, and the two medium widgets, upcoming_deadlines and staff_utilization, sit side by side at grid_x 0 and grid_x 1, meaning each medium widget is 2 columns wide, meaning the grid itself is 4 columns total. Use a row height of 80 pixels and a margin of 16 pixels between items as a starting point, with height in grid rows of 2 for small, 5 for medium, and 7 for large, but note in your summary that these row-height numbers are a first visual pass, not a fixed measurement, and Ben should expect to adjust them after actually looking at the page.

In frontend/src/app/(app)/dashboard/page.tsx, replace the fixed JSX rows, the stat card grid, the WIP widget, the upcoming deadlines and staff utilization row, the overdue engagements table, and the awaiting signature table, with a react-grid-layout GridLayout component (not the responsive variant, since this batch is desktop-only view-only) configured with cols set to 4, rowHeight set to 80, and margin set to [16, 16], with isDraggable and isResizable both set to false. Keep the page header and the ConciergeSpotlight component exactly where they are now, above the grid, unchanged, ConciergeSpotlight stays fixed and is not part of the customizable canvas.

Fetch the layout with useQuery calling the new dashboardApi.getLayout, keyed as dashboard-layout. Build the GridLayout's layout prop from the returned widgets array, mapping each widget's instance_id to i, grid_x to x, grid_y to y, and its size through the size-to-grid-span constant to w and h.

For each widget instance, render a small wrapper component that fetches that instance's own data via useQuery calling dashboardApi.getWidgetData with the widget's type_key, keyed as ['dashboard-widget-data', type_key, instance_id], with the same 60 second staleTime already used for the old bulk metrics query. While loading, reuse the existing skeleton components already defined in this file, MetricCardSkeleton, UpcomingDeadlinesSkeleton, StaffUtilizationSkeleton, matched to whichever widget type is loading. On error, show a small inline message consistent with the existing WIPWidget error state pattern in this same file, do not invent a new error UI pattern.

Map each type_key to its existing component: revenue_this_month, outstanding_ar, unbilled_wip_stat, and overdue_engagements_count each render a MetricCard with the label and value pulled from that widget's own fetched data. work_in_progress renders the existing WIPWidget component completely unchanged, still calling reportsApi.getWip() internally exactly as it does today, not consuming this widget's own /dashboard/widgets/work_in_progress/data endpoint. upcoming_deadlines renders UpcomingDeadlinesList with items from the fetched data's upcoming_deadlines field. staff_utilization renders StaffUtilizationPanel with items from the fetched data's staff_utilization field. overdue_engagements_table renders OverdueEngagementsTable with items from the fetched data's overdue_engagements field, keeping its existing onComplete and Mark Complete behavior fully working exactly as it does today, this is real production functionality, not part of what's being deferred to the edit-mode batch. awaiting_signature renders UnsignedDocumentsTable with items from the fetched data's unsigned_documents field, keeping its existing Send Reminder and Create Follow-Up Task buttons fully working.

Remove the now-unused DashboardMetrics bulk useQuery call and the dismissedIds state that lived at the top level of the page, since overdue engagement dismissal now lives inside the overdue_engagements_table widget wrapper's own local state instead of the page level.

VERIFY AFTER ACT:

cd /home/corby/jamm-os/frontend
npm run build

grep -n "react-grid-layout" package.json
grep -n "getLayout\|getWidgetData" src/lib/api/dashboard.ts
grep -n "GridLayout" "src/app/(app)/dashboard/page.tsx"
grep -n "isDraggable={false}\|isResizable={false}" "src/app/(app)/dashboard/page.tsx"

The build must complete with no TypeScript errors and no missing-import errors. If it fails, do not work around the failure by loosening types or adding any, fix the real cause and report what it was.

MANUAL VERIFICATION:

Start the frontend dev server and log in as owner@riverside-demo.com / Demo2026x.

Load /dashboard and confirm all 9 widgets appear in the same visual arrangement as before this change, four small stat cards in a row, work in progress below them, upcoming deadlines and staff utilization side by side, overdue engagements table, then awaiting signature. Confirm the actual numbers shown match what you'd expect from the Riverside test data, not blank or zero everywhere.

Click Mark Complete on an overdue engagement if one exists, and confirm it still works and the row disappears, same as it does today.

Confirm nothing is draggable or resizable yet, this batch is intentionally view-only.

Check the browser console for any errors on page load, react-grid-layout is a new dependency and a silent console warning here would be worth catching now rather than after edit mode is built on top of it.

Report back what the row heights actually look like, since the 80 pixel row height and the 2/5/7 row-span numbers were a first estimate, not a measurement, and may need adjusting before batch 3.

GIT:

git add -A
git commit -m "wire the dashboard to react-grid-layout in view-only mode, rendering the 9 launch-catalog widgets from the real GET /dashboard/layout endpoint with each widget instance fetching its own data independently, replacing the fixed-row layout and the single bulk metrics call, existing presentational components and in-widget actions like Mark Complete and Send Reminder are reused unchanged"
git pull --rebase origin main
git push origin main

If task.md conflicts on the rebase, resolve with --theirs per standing rule. Any other file conflict, stop and report back rather than resolving automatically.