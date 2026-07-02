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

# Task: Add missing jamm_concierge_pending consumption to Engagements page so the New Engagement chip actually opens the modal

USE: claude sonnet

## VERIFY BEFORE ACT

sed -n '1,40p' "/home/corby/jamm-os/frontend/src/app/(app)/engagements/page.tsx"

Confirm modalOpen (useState(false)) is the existing state variable controlling the New Engagement modal's visibility, already wired to the "+ New Engagement" button via setModalOpen(true), and confirm useEffect is already imported.

sed -n '25,50p' "/home/corby/jamm-os/frontend/src/app/(app)/clients/page.tsx"

Confirm the exact working reference pattern already used on the Clients page: an on-mount useEffect reading jamm_concierge_pending from sessionStorage, checking the action is less than 10 seconds old (via _ts), matching on action.modal, and calling the local modal-open setter.

## WHAT IS WRONG

Confirmed via live testing and code tracing: the Concierge's "New engagement" suggestion chip was just updated to trigger a navigate-and-open action with modal: 'new-engagement', targeting the existing new-engagement modal action already used successfully elsewhere in the app (per the modalLabel map in ConciergePanel.tsx showing "Opened New Engagement drawer"). The write side of this mechanism works correctly -- ConciergePanel.tsx correctly stores the pending action in sessionStorage under jamm_concierge_pending before navigating. However, unlike clients/page.tsx, clients/[id]/page.tsx, settings/page.tsx, and settings/team/page.tsx, which all have an on-mount effect that reads and consumes this pending action to open their respective modals, engagements/page.tsx has no such consumption logic at all. This means clicking "New engagement" correctly navigates to the Engagements page but the modal never opens, since nothing on this page is listening for the pending action. This is a pre-existing gap in the modal action's implementation coverage, not something introduced by tonight's chip fix -- the chip fix correctly pointed at a real mechanism that was simply never fully wired up for this specific page.

## ACTION

File: /home/corby/jamm-os/frontend/src/app/(app)/engagements/page.tsx

Add an on-mount effect matching the exact pattern already used in clients/page.tsx, placed near the other useState declarations at the top of the component:

  useEffect(() => {
    const raw = sessionStorage.getItem('jamm_concierge_pending')
    if (!raw) return
    try {
      const action = JSON.parse(raw)
      if (Date.now() - (action._ts ?? 0) > 10000) {
        sessionStorage.removeItem('jamm_concierge_pending')
        return
      }
      if (action.modal === 'new-engagement') {
        sessionStorage.removeItem('jamm_concierge_pending')
        setModalOpen(true)
      }
    } catch {
      sessionStorage.removeItem('jamm_concierge_pending')
    }
  }, [])

Place this effect after the existing useState declarations, in the same relative position clients/page.tsx uses (immediately after the relevant state variables, before any other effects). useEffect is already imported in this file, confirmed in VERIFY BEFORE ACT.

Do not add prefill handling (unlike the new-client case, the new-engagement modal action currently has no prefill fields defined anywhere in the codebase, so none should be invented here). Do not change modalOpen's existing wiring to the "+ New Engagement" button or the empty-state "New" action. Do not touch any other file.

## VERIFY AFTER ACT

grep -n "jamm_concierge_pending" "/home/corby/jamm-os/frontend/src/app/(app)/engagements/page.tsx"

Expected: present, with the read, the 10-second freshness check, and the modal === 'new-engagement' match all visible.

cd /home/corby/jamm-os/frontend
npm run build

Expected: zero TypeScript errors.

## MANUAL VERIFICATION (the actual test)

1. Restart the frontend.
2. On the Dashboard, ask the Concierge a question that produces a "New engagement" suggestion chip.
3. Click the chip.
4. Confirm you land on the Engagements page AND the New Engagement modal/drawer is now open automatically, not just the plain page.
5. Regression check: click the "+ New Engagement" button directly (not via the chip) and confirm it still opens the modal normally, unaffected by this change.
6. Regression check: navigate to Engagements via a normal method (sidebar, if reachable, or direct navigation) with no pending action in sessionStorage, and confirm the modal does NOT auto-open when there's nothing pending.

Report what you observe at step 4 specifically.

## GIT

cd /home/corby/jamm-os
git add -A
git commit -m "fix: add missing jamm_concierge_pending consumption to Engagements page, so the Concierge's New engagement suggestion chip actually opens the New Engagement modal after navigating, matching the same pattern already implemented on Clients, Client Detail, and Settings pages"
git pull --rebase origin main
git push origin main

If conflicts on task.md use --theirs. Conflicts on source files use --ours.