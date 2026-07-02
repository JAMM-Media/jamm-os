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

# Task: Fix double-wrapped AppShell on engagements/[id]/page.tsx, a leftover gap from Phase 1

USE: claude sonnet

## VERIFY BEFORE ACT

grep -n "<AppShell\|</AppShell>\|import.*AppShell" "/home/corby/jamm-os/frontend/src/app/(app)/engagements/[id]/page.tsx"

Confirm exactly 3 <AppShell> / </AppShell> pairs at lines 115/121, 127/131, and 136/529, plus the import at line 8.

## WHAT IS WRONG

Confirmed via direct verification: engagements/[id]/page.tsx was physically moved into the (app) route group during Phase 1 (git mv moved the entire engagements folder including its [id] subfolder), but Phase 1's task only explicitly listed engagements/page.tsx for unwrapping, not engagements/[id]/page.tsx. As a result, this file still has its own AppShell wrapper tags, meaning it currently renders AppShell twice on every load: once from the new (app)/layout.tsx (which now correctly wraps every page in the group), and again from its own leftover wrapper tags. This likely produces a duplicate sidebar and duplicate Concierge panel on this specific page, though the exact visual symptom was not directly observed since this page was not part of Phase 1's manual test coverage.

## ACTION

File: /home/corby/jamm-os/frontend/src/app/(app)/engagements/[id]/page.tsx

Remove all 3 <AppShell> opening tags and their 3 matching </AppShell> closing tags (at the line pairs confirmed in VERIFY BEFORE ACT), preserving everything between them exactly as-is -- the loading state, not-found state, and main content must remain completely unchanged, only the wrapper tags removed. Remove the AppShell import on line 8.

Do not touch any other file in this task.

## VERIFY AFTER ACT

grep -c "<AppShell" "/home/corby/jamm-os/frontend/src/app/(app)/engagements/[id]/page.tsx"

Expected: 0.

grep -n "import.*AppShell" "/home/corby/jamm-os/frontend/src/app/(app)/engagements/[id]/page.tsx"

Expected: no matches.

cd /home/corby/jamm-os/frontend
rm -rf .next
npm run build

Expected: zero TypeScript errors, /engagements/[id] still resolves as a valid route.

## MANUAL VERIFICATION

1. Restart the frontend with a clean build.
2. Navigate to any individual engagement's detail page (e.g. click into "2025 S-Corp Tax Return" from the Engagements list).
3. Confirm only one sidebar and one Concierge panel render, not two.
4. Confirm the page's actual content (Overview, Tasks, QC Checklist, Documents tabs) renders correctly and completely unchanged.
5. Confirm conversation persistence still works: ask a question on the Engagements list, click into a specific engagement's detail page, confirm the conversation is still there (this page is inside the (app) group, so persistence should hold here too, same as clients/[id] already does).

Report what you observe at steps 3 and 5.

## GIT

cd /home/corby/jamm-os
git add -A
git commit -m "fix: remove leftover AppShell wrapper tags from engagements/[id]/page.tsx -- a gap from Phase 1 where the file was physically moved into the (app) route group but never had its own now-redundant AppShell tags stripped, causing it to render AppShell twice (once from the new shared layout, once from its own leftover wrapper)"
git pull --rebase origin main
git push origin main

If conflicts on task.md use --theirs. Conflicts on source files use --ours.