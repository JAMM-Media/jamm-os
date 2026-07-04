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

# Task: Fix React render-phase state update violation in QcChecklistTab causing unchecked-item count to never propagate correctly

USE: claude sonnet

## VERIFY BEFORE ACT

grep -n "onUncheckedCountChange\|onUncheckedCountChangeRef" /home/corby/jamm-os/frontend/src/components/engagements/QcChecklistTab.tsx

Confirm all 4 current call sites: line ~55 (inside fetchItems, called correctly in a normal async function body after setItems), and lines ~87, ~119, ~136 (each incorrectly called inside a setItems updater function -- toggle-check, add item, and delete respectively).

## WHAT IS WRONG

Confirmed via live testing: a React console error, "Cannot update a component (EngagementDetailPage) while rendering a different component (QcChecklistTab)," appears when adding a QC checklist item. Root cause: onUncheckedCountChangeRef.current?.() is called synchronously inside three separate setItems updater functions (toggle-check, add item, delete item). React does not allow triggering an update to a different component's state (which this callback does, since it reports the count up to the parent EngagementDetailPage) from inside another component's state updater function during the same render pass. This is a React rules-of-hooks violation.

The practical consequence, confirmed via live testing: after adding a new unchecked QC item and then attempting to mark the engagement as Completed, no warning about unchecked items appeared at all, even though an unchecked item genuinely existed. This strongly suggests the parent's uncheckedQcCount value was not correctly updated due to this violation, causing the downstream confirm-before-completing check in EditEngagementModal to incorrectly see zero unchecked items.

## ACTION

File: /home/corby/jamm-os/frontend/src/components/engagements/QcChecklistTab.tsx

Remove the manual onUncheckedCountChangeRef.current?.() call from all four locations:

1. Inside fetchItems, remove the line onUncheckedCountChangeRef.current?.(all.filter((i) => !i.is_checked).length) that currently follows setItems(all).

2. Inside the toggle-check setItems updater (~line 87), remove the line onUncheckedCountChangeRef.current?.(next.filter((i) => !i.is_checked).length) from inside the updater, keeping return next.

3. Inside the add-item setItems updater (~line 119), remove the same pattern, keeping return next.

4. Inside the delete-item setItems updater (~line 136), remove the same pattern, keeping return next.

Add a single useEffect that watches items and reports the count whenever it changes, placed near the other hooks at the top of the component (after the onUncheckedCountChangeRef setup):

  useEffect(() => {
    onUncheckedCountChangeRef.current?.(items.filter((i) => !i.is_checked).length)
  }, [items])

This correctly fires after every render where items has changed, regardless of which operation (fetch, toggle, add, delete) caused the change, replacing all four manual call sites with one consolidated, correctly-timed effect.

Do not change any other logic in this file -- the actual item CRUD operations, loading states, and error handling must remain exactly as they are, only the count-reporting mechanism changes.

## VERIFY AFTER ACT

grep -n "onUncheckedCountChangeRef.current?." /home/corby/jamm-os/frontend/src/components/engagements/QcChecklistTab.tsx

Expected: exactly one occurrence now, inside the new useEffect.

grep -n "useEffect(() => {" /home/corby/jamm-os/frontend/src/components/engagements/QcChecklistTab.tsx

Expected: the new effect present among any existing effects in the file.

cd /home/corby/jamm-os/frontend
npm run build

Expected: zero TypeScript errors.

## MANUAL VERIFICATION (the actual test)

1. Restart the frontend with a clean build.
2. Open any engagement, go to its QC Checklist tab, add a new checklist item, leave it unchecked.
3. Confirm no React console error appears this time (the "Cannot update a component while rendering a different component" error should be gone).
4. Open Edit Engagement, change status to Completed, save. Confirm the branded confirm modal now correctly appears warning about the unchecked item, matching the intended behavior from the earlier task.
5. Confirm clicking Cancel on that warning correctly cancels the status change, and confirming it correctly proceeds.
6. Regression check: check off the item, confirm the warning no longer appears when marking complete with zero unchecked items.

Report what you observe at steps 3 and 4 specifically.

## GIT

cd /home/corby/jamm-os
git add -A
git commit -m "fix: QcChecklistTab was calling its onUncheckedCountChange callback synchronously inside setItems updater functions (toggle, add, delete), violating React's rule against updating a different component's state during another component's render. Replaced all four manual call sites with a single useEffect watching items, which correctly and consistently reports the unchecked count after every change. This also fixes a real downstream bug where the unchecked-QC-items warning never appeared when marking an engagement complete, since the parent's count was never correctly updated."
git pull --rebase origin main
git push origin main

If conflicts on task.md use --theirs. Conflicts on source files use --ours.