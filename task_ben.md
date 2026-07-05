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

# Task: Add unchecked-QC-items warning to bulk "Change Status" action on Engagements list

USE: claude sonnet

## VERIFY BEFORE ACT

sed -n '82,93p' /home/corby/jamm-os/app/crud/qc_checklist.py

Confirm the existing list_items function's query pattern: filtering QcChecklistItem by firm_id and a single engagement_id.

sed -n '110,133p' "/home/corby/jamm-os/frontend/src/app/(app)/engagements/page.tsx"

Confirm the current handleBulkStatus function: it immediately optimistically updates local state, then calls engagementsApi.bulkUpdate(ids, { status: newStatus }) with no check of any kind beforehand.

grep -n "useConfirm\|ConfirmDialog" "/home/corby/jamm-os/frontend/src/app/(app)/engagements/page.tsx"

Confirm whether useConfirm is already imported and wired into this page (it may not be, since this page has not used the confirm modal pattern yet).

## WHAT IS WRONG

The single-engagement Edit Engagement modal correctly warns before marking an engagement Completed if it has unchecked QC checklist items. The bulk "Change Status" action on the Engagements list page (handleBulkStatus) has no equivalent check at all -- a user can select multiple engagements and mark them all Completed via a single bulk API call with zero visibility into whether any of them have unchecked QC items. This is a real safety inconsistency between two paths that perform the same underlying action. No existing backend endpoint can report unchecked-item counts across a set of engagement IDs at once; today's data model only supports checking one engagement at a time via QcChecklistTab.

## ACTION

Step 1: Backend. In /home/corby/jamm-os/app/crud/qc_checklist.py, add a new function near list_items:

def get_unchecked_counts(db: Session, firm_id, engagement_ids: list):
    if not engagement_ids:
        return {}
    rows = db.execute(
        select(QcChecklistItem.engagement_id, QcChecklistItem.is_checked)
        .where(
            QcChecklistItem.firm_id == firm_id,
            QcChecklistItem.engagement_id.in_(engagement_ids),
        )
    ).all()
    counts: dict = {}
    for engagement_id, is_checked in rows:
        if not is_checked:
            counts[engagement_id] = counts.get(engagement_id, 0) + 1
    return counts

Step 2: In /home/corby/jamm-os/app/api/qc_checklists.py, add a new route near the other item endpoints (place it before the /items/{item_id} parameterized routes, following the same literal-segment-before-parameterized-route ordering rule already established elsewhere in this codebase):

from fastapi import Query

@router.get("/unchecked-counts")
def get_unchecked_counts(
    engagement_ids: str = Query(...),
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_staff_or_above),
):
    ids = [UUID(x.strip()) for x in engagement_ids.split(",") if x.strip()]
    counts = crud.get_unchecked_counts(db, current_firm.id, ids)
    return {str(k): v for k, v in counts.items()}

engagement_ids is accepted as a comma-separated query string (e.g. ?engagement_ids=id1,id2,id3) rather than a JSON body, matching this being a GET request. Add the Query import to the existing fastapi import line at the top of the file rather than adding a separate import line.

Step 3: Frontend API client. Check /home/corby/jamm-os/frontend/src/lib/api/ for the existing qc-checklist API module (likely qcChecklistApi.ts or similar -- find it if it exists, or note its absence) and add a function to call the new endpoint:

  getUncheckedCounts: async (engagementIds: string[]): Promise<Record<string, number>> => {
    if (engagementIds.length === 0) return {}
    const { data } = await api.get(`/qc-checklists/unchecked-counts?engagement_ids=${engagementIds.join(',')}`)
    return data
  },

If no existing qc-checklist API module exists in the frontend, add this function directly as a small local helper inside engagements/page.tsx instead, calling api.get directly with the same URL pattern -- do not create a new API module file just for this one function if the codebase does not already have one for QC checklists.

Step 4: Wire it into handleBulkStatus in engagements/page.tsx. Import useConfirm near the other imports, call the hook near the other state declarations, and render {ConfirmDialog} somewhere in this page's JSX return (near the top level, following the same pattern used in ConciergePanel.tsx).

Modify handleBulkStatus to check for unchecked items before proceeding, only when the new status is "completed":

  async function handleBulkStatus(newStatus: string) {
    setStatusDropOpen(false)
    const ids = Array.from(selectedIds)
    if (newStatus === 'completed') {
      const counts = await getUncheckedCounts(ids) // or qcChecklistApi.getUncheckedCounts(ids), matching whichever was added in Step 3
      const affectedCount = Object.values(counts).filter((c) => c > 0).length
      if (affectedCount > 0) {
        const confirmed = await confirm(
          `${affectedCount} of the ${ids.length} selected engagements have unchecked QC checklist items. Mark all as complete anyway?`
        )
        if (!confirmed) return
      }
    }
    setBulkLoading(true)
    setLocalEngagements((les) =>
      les.map((e) => selectedIds.has(e.id) ? { ...e, status: newStatus } : e)
    )
    setStatusOverrides((prev) => {
      const next = { ...prev }
      ids.forEach((id) => { next[id] = newStatus })
      return next
    })
    try {
      await engagementsApi.bulkUpdate(ids, { status: newStatus })
      setSelectedIds(new Set())
      toast.success(`Updated ${ids.length} engagement${ids.length !== 1 ? 's' : ''}`)
    } catch {
      toast.error('Bulk update failed')
    } finally {
      setBulkLoading(false)
    }
  }

Note the confirm check now happens before setBulkLoading(true) and before the optimistic local state update, so cancelling the confirm leaves everything completely untouched, not partially updated.

Do not change handlePushDeadline or any other bulk action. Do not add the unchecked-items check for any status other than "completed".

## VERIFY AFTER ACT

grep -n "def get_unchecked_counts" /home/corby/jamm-os/app/crud/qc_checklist.py /home/corby/jamm-os/app/api/qc_checklists.py

Expected: present in both files.

python3 -c "from app.main import app; print('OK')"

Expected: OK, no import errors.

grep -n "getUncheckedCounts\|useConfirm" "/home/corby/jamm-os/frontend/src/app/(app)/engagements/page.tsx"

Expected: both present.

cd /home/corby/jamm-os/frontend
npm run build

Expected: zero TypeScript errors.

## MANUAL VERIFICATION (the actual test)

1. Restart both backend and frontend.
2. On the Engagements list, select 2 or more engagements where at least one has an unchecked QC checklist item (add one via an engagement's detail page first if none currently have any), choose Completed from Change Status.
3. Confirm the new branded modal appears with wording like "X of the Y selected engagements have unchecked QC checklist items. Mark all as complete anyway?"
4. Cancel it, confirm no engagement's status changed.
5. Repeat and confirm this time, confirm all selected engagements correctly update to Completed.
6. Select engagements where none have unchecked items, mark Completed, confirm no modal appears and the change happens immediately as before.
7. Select engagements and change to a non-completed status (e.g. Active), confirm no QC check happens at all regardless of unchecked items.

Report what you observe at steps 3, 5, and 7.

## GIT

cd /home/corby/jamm-os
git add -A
git commit -m "feat: bulk Change Status action on the Engagements list now warns before marking multiple engagements Completed if any of them have unchecked QC checklist items, matching the same safety check already present in the single-engagement Edit Engagement modal. Added a new backend endpoint to report unchecked-item counts across a set of engagement IDs at once, since no such batch lookup existed before."
git pull --rebase origin main
git push origin main

If conflicts on task.md use --theirs. Conflicts on source files use --ours.