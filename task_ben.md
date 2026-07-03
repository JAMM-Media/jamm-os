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

# Task: Phase 2 -- Migrate remaining 19 pages into the (app) route group for full Concierge conversation persistence

USE: claude fable-5

## VERIFY BEFORE ACT

cat "/home/corby/jamm-os/frontend/src/app/(app)/layout.tsx"

Confirm the route group layout created in Phase 1 wraps children in AppShell.

Confirm exact current <AppShell> counts per file (already verified, use as ground truth -- if any count differs from this list when you check, stop and report rather than proceeding):

staff/page.tsx: 2
tasks/page.tsx: 2
tasks/[id]/page.tsx: 3
settings/page.tsx: 1
settings/team/page.tsx: 2
settings/my-integrations/page.tsx: 1
settings/integrations/page.tsx: 1
settings/billing/page.tsx: 1
calendar/page.tsx: 1
(dashboard)/firm-chat/page.tsx: 1
(dashboard)/timesheets/page.tsx: 1
(dashboard)/inbox/page.tsx: 1
(dashboard)/templates/page.tsx: 1
documents/page.tsx: 2
documents/[id]/page.tsx: 3
notifications/page.tsx: 1
billing/page.tsx: 2
billing/[id]/page.tsx: 3
billing/wip/page.tsx: 1

Total: 19 files, 29 AppShell instances.

## WHAT IS WRONG

Phase 1 (already completed) moved dashboard, engagements, and clients into a shared (app) route group layout, fixing Concierge conversation persistence across navigation for those pages. This is Phase 2: migrate the remaining 19 pages using the identical pattern, so persistence works across the entire authenticated app, not just those three areas.

Phase 1 left one gap that was found and fixed separately: engagements/[id]/page.tsx was physically moved via its parent folder's git mv but its own AppShell tags were not stripped, since it was not explicitly listed in that task's file list, causing a double-wrapped AppShell (rendering two sidebars and two Concierge panels) until caught and fixed afterward. This task exists specifically to prevent that mistake from recurring at 19-file scale: every single file listed above, including every nested [id] or sub-route file, must be individually verified both before moving (confirming the AppShell count matches what is listed above) and after unwrapping (confirming the count is exactly 0), with no file skipped or assumed identical to a sibling file just because it is in the same folder.

## ACTION

Step 1: Move all remaining page folders into the (app) route group using git mv, preserving history. The (dashboard) route group currently has no layout.tsx of its own and will be dissolved into (app) for consistency, since maintaining two separate authenticated route groups serves no purpose.

git mv frontend/src/app/staff frontend/src/app/(app)/staff
git mv frontend/src/app/tasks frontend/src/app/(app)/tasks
git mv frontend/src/app/settings frontend/src/app/(app)/settings
git mv frontend/src/app/calendar frontend/src/app/(app)/calendar
git mv "frontend/src/app/(dashboard)/firm-chat" "frontend/src/app/(app)/firm-chat"
git mv "frontend/src/app/(dashboard)/timesheets" "frontend/src/app/(app)/timesheets"
git mv "frontend/src/app/(dashboard)/inbox" "frontend/src/app/(app)/inbox"
git mv "frontend/src/app/(dashboard)/templates" "frontend/src/app/(app)/templates"
git mv frontend/src/app/documents frontend/src/app/(app)/documents
git mv frontend/src/app/notifications frontend/src/app/(app)/notifications
git mv frontend/src/app/billing frontend/src/app/(app)/billing

After all moves, confirm the now-empty (dashboard) route group folder is removed (git mv of its last child should leave it empty; delete the empty (dashboard) folder if it remains).

After each individual git mv, list the destination directory's contents before proceeding to the next move, to confirm every nested file (including any [id] subfolders, and settings' team/my-integrations/integrations/billing subfolders) moved correctly.

Step 2: For every one of the 19 files, remove every <AppShell> opening tag and matching </AppShell> closing tag, preserving all content between them exactly as-is, and remove the AppShell import line. Process one file at a time. Before moving to the next file, run grep -c "<AppShell" on the file just edited and confirm it now reads exactly 0. Do not proceed to the next file until this is confirmed for the current one. If any file's JSX structure requires a Fragment (<>...</>) instead of simply deleting the tags, because multiple sibling elements existed under a single AppShell wrapper (as was required for clients/[id]/page.tsx and engagements/[id]/page.tsx in prior work), apply the same Fragment pattern here as needed, verified by a successful build with zero TypeScript errors for that specific change.

Pay particular attention to the three files with the highest instance counts (tasks/[id]/page.tsx, documents/[id]/page.tsx, billing/[id]/page.tsx, each with 3), since these detail-page patterns proved most likely to need Fragment wrapping in prior work on clients/[id] and engagements/[id].

Do not modify AppShell.tsx or (app)/layout.tsx. Do not modify ConciergePanel.tsx. Do not modify any file's actual page content, only the AppShell wrapper tags and the now-unused import.

## VERIFY AFTER ACT

For every one of the 19 files, confirm and report individually (not just a summary count) both the <AppShell> count is 0 and the AppShell import is absent:

grep -c "<AppShell" "/home/corby/jamm-os/frontend/src/app/(app)/staff/page.tsx"
grep -c "<AppShell" "/home/corby/jamm-os/frontend/src/app/(app)/tasks/page.tsx"
grep -c "<AppShell" "/home/corby/jamm-os/frontend/src/app/(app)/tasks/[id]/page.tsx"
grep -c "<AppShell" "/home/corby/jamm-os/frontend/src/app/(app)/settings/page.tsx"
grep -c "<AppShell" "/home/corby/jamm-os/frontend/src/app/(app)/settings/team/page.tsx"
grep -c "<AppShell" "/home/corby/jamm-os/frontend/src/app/(app)/settings/my-integrations/page.tsx"
grep -c "<AppShell" "/home/corby/jamm-os/frontend/src/app/(app)/settings/integrations/page.tsx"
grep -c "<AppShell" "/home/corby/jamm-os/frontend/src/app/(app)/settings/billing/page.tsx"
grep -c "<AppShell" "/home/corby/jamm-os/frontend/src/app/(app)/calendar/page.tsx"
grep -c "<AppShell" "/home/corby/jamm-os/frontend/src/app/(app)/firm-chat/page.tsx"
grep -c "<AppShell" "/home/corby/jamm-os/frontend/src/app/(app)/timesheets/page.tsx"
grep -c "<AppShell" "/home/corby/jamm-os/frontend/src/app/(app)/inbox/page.tsx"
grep -c "<AppShell" "/home/corby/jamm-os/frontend/src/app/(app)/templates/page.tsx"
grep -c "<AppShell" "/home/corby/jamm-os/frontend/src/app/(app)/documents/page.tsx"
grep -c "<AppShell" "/home/corby/jamm-os/frontend/src/app/(app)/documents/[id]/page.tsx"
grep -c "<AppShell" "/home/corby/jamm-os/frontend/src/app/(app)/notifications/page.tsx"
grep -c "<AppShell" "/home/corby/jamm-os/frontend/src/app/(app)/billing/page.tsx"
grep -c "<AppShell" "/home/corby/jamm-os/frontend/src/app/(app)/billing/[id]/page.tsx"
grep -c "<AppShell" "/home/corby/jamm-os/frontend/src/app/(app)/billing/wip/page.tsx"

Expected: 0 for every single one, no exceptions.

find "/home/corby/jamm-os/frontend/src/app/(dashboard)" -type f 2>/dev/null

Expected: no output or "No such file or directory" -- confirming the old, now-empty route group was fully dissolved.

cd /home/corby/jamm-os/frontend
rm -rf .next
npm run build

Expected: zero TypeScript errors, and every original route (/staff, /tasks, /tasks/[id], /settings, /settings/team, /settings/my-integrations, /settings/integrations, /settings/billing, /calendar, /firm-chat, /timesheets, /inbox, /templates, /documents, /documents/[id], /notifications, /billing, /billing/[id], /billing/wip) still resolves correctly, since route groups are transparent to the URL.

## MANUAL VERIFICATION (the actual test)

1. Restart the frontend with a clean build.
2. Log in, go to Dashboard, open the Concierge panel, ask a real question and get an answer.
3. Navigate via sidebar or chip through at least 6 of the newly migrated pages in sequence (e.g. Staff, Tasks, Settings, Calendar, Documents, Billing), without ever closing the panel.
4. Confirm the original conversation from step 2 is still fully visible after every single one of those navigations, not reset at any point.
5. Spot-check the three highest-risk files individually: open a specific task's detail page, a specific document's detail page, and a specific invoice's detail page. Confirm each renders with exactly one sidebar and one Concierge panel (not doubled), and confirm the conversation still persists on each.
6. Confirm Settings' internal tab-switching (Account, Firm Settings, Portal, Email, Data) still works normally, unaffected by this change, since Settings has its own internal activeTab state separate from the route-level pages like settings/team.

Report what you observe at steps 4 and 5 specifically, since those are the actual proof this phase worked across the full remaining page set.

## GIT

cd /home/corby/jamm-os
git add -A
git commit -m "fix: Phase 2 -- migrate remaining 19 pages (staff, tasks, settings and its sub-routes, calendar, firm-chat, timesheets, inbox, templates, documents, notifications, billing and its sub-routes) into the shared (app) route group layout, completing the Concierge conversation persistence fix across the entire authenticated app. Dissolved the now-unused (dashboard) route group. Every file's AppShell wrapper tags individually verified removed to prevent the double-wrapping gap found and fixed separately in engagements/[id]/page.tsx after Phase 1."
git pull --rebase origin main
git push origin main

If conflicts on task.md use --theirs. Conflicts on source files use --ours.