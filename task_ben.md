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

# Task: Fix Concierge message prefill not appearing when already on the target client's page

USE: claude sonnet

## VERIFY BEFORE ACT

```bash
grep -n "interface ConciergeAction" -A 15 /home/corby/jamm-os/frontend/src/lib/events/conciergeEvents.ts
```

Confirm the exact shape of the ConciergeAction type before adding a new action
shape to it.

```bash
grep -n "Open to send" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx
```

Confirm there are exactly two call sites (notification draft card, per-message
draft card) and note their line numbers.

```bash
grep -n "onConciergeAction" -A 18 /home/corby/jamm-os/frontend/src/app/clients/\[id\]/page.tsx
```

Confirm the existing listener structure that already branches on action.modal
for new-engagement and portal-magic-link.

---

## WHAT IS WRONG

When the user clicks "Open to send" on a draft while already viewing that
exact client's page, the draft never appears in the Messages compose box,
even though the URL correctly updates to ?tab=messages and the tab correctly
activates.

Root cause: both "Open to send" handlers in ConciergePanel.tsx always write
to sessionStorage under the key jamm_concierge_pending and then call
router.push to the same client's route with ?tab=messages. The page.tsx
effect that reads jamm_concierge_pending and calls setMessageCompose has a
dependency array of [clientId]. Since the user is already on that client's
page, clientId does not change, the component does not remount, and that
effect never re-runs to pick up the value that was just written. The draft
is written to sessionStorage one render too late to be read.

This is the identical underlying disease as the tab-sync bug already fixed
in commit f05c249, just living in a different effect with a different
symptom. The codebase already has the correct pattern for this exact
situation: the modal-action branch in executeAction() checks
pathname.startsWith(normalizedRoute) (the alreadyOnRoute check) and calls
emitConciergeAction() directly instead of sessionStorage when no navigation
is actually required. The two "Open to send" handlers skip that check
entirely and always go through sessionStorage, even in the same-page case.

---

## ACTION

File: `/home/corby/jamm-os/frontend/src/lib/events/conciergeEvents.ts`

Extend the ConciergeAction type to allow an optional prefillMessage field and
a type value of 'prefill-message', matching whatever pattern the existing
type definition uses for its other optional fields (prefill, modal, route).
Do not change any existing field.

File: `/home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx`

In both "Open to send" handlers (the notification draft card and the
per-message draft card), after computing targetClientId and getting
confirmation from window.confirm, branch on whether the user is already on
that client's page before deciding how to deliver the draft:

```typescript
const alreadyOnClientPage = pathname.startsWith(`/clients/${targetClientId}`)
if (alreadyOnClientPage) {
  emitConciergeAction({ type: 'prefill-message', prefillMessage: currentContent })
} else {
  sessionStorage.setItem(
    'jamm_concierge_pending',
    JSON.stringify({
      clientId: targetClientId,
      prefillMessage: currentContent,
      _ts: Date.now(),
    }),
  )
}
router.push(`/clients/${targetClientId}?tab=messages`)
```

Adjust variable names (draft vs currentContent) to match each call site
exactly as it already reads. Do not change the confirm dialog text, the
dismissNotification call, or any other logic in either handler.

File: `/home/corby/jamm-os/frontend/src/app/clients/[id]/page.tsx`

In the existing onConciergeAction listener (the one already handling
new-engagement and portal-magic-link), add a branch:

```typescript
if (action.type === 'prefill-message' && action.prefillMessage) {
  setActiveTab('messages')
  setMessageCompose(action.prefillMessage)
}
```

Do not touch the existing branches in this listener. Do not touch the
sessionStorage-based useEffect that handles the cross-page case, it remains
correct and necessary for navigation to a different client.

---

## VERIFY AFTER ACT

```bash
grep -n "prefill-message" /home/corby/jamm-os/frontend/src/lib/events/conciergeEvents.ts
grep -n "prefill-message" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx
grep -n "prefill-message" /home/corby/jamm-os/frontend/src/app/clients/\[id\]/page.tsx
```

Expected: at least one occurrence in each file.

```bash
cd /home/corby/jamm-os/frontend
npm run build
```

Expected: zero TypeScript errors.

---

## MANUAL VERIFICATION (the actual test)

1. Open a specific client's page directly (already on that client, not
   navigating from the Clients list).
2. Trigger a CLIENT_EMAIL draft for that same client and click "Open to
   send," then OK on the confirm dialog.
3. Confirm the Messages tab activates AND the compose box is pre-filled with
   the draft text. This is the part that was broken.
4. Regression check: from a different client's page, or from the firm-wide
   Clients list with no client in context, trigger a draft for a specific
   client and click "Open to send." Confirm it still navigates correctly
   and the compose box is still pre-filled after the page loads (this is the
   cross-page case using the existing sessionStorage path, must still work).
5. Regression check: confirm clicking between Overview, Engagements,
   Documents tabs manually still works exactly as before.

Report what you observe at step 3 specifically.

---

## GIT

```bash
cd /home/corby/jamm-os
git add -A
git commit -m "fix: Concierge draft prefill now reaches the Messages compose box when already on the target client's page, via live event instead of a sessionStorage read that never re-fires without a remount"
git pull --rebase origin main
git push origin main
```

If conflicts on task.md use --theirs. Conflicts on source files use --ours.