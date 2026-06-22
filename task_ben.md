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

# Task: Fix Concierge panel single shared scrollbar trapping the input bar off-screen

USE: claude sonnet

## VERIFY BEFORE ACT

```bash
grep -n "flex-1 overflow-y-auto\|flex-shrink-0" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx
```

Confirm the notifications block uses flex-shrink-0 with no min-height or
max-height constraint, and the message feed uses flex-1 overflow-y-auto with
no min-h-0 or minHeight:0 set anywhere on it or its flex ancestors.

---

## WHAT IS WRONG

Confirmed via live testing: when notification cards stack up (2+ draft
cards), the entire panel content, alert cards and chat messages together,
scrolls as one single region instead of the alerts and chat feed scrolling
independently. The scrollbar is contained to the panel, not the page, but
the input bar at the bottom gets pushed out of view with no way to scroll
it back into reach.

Root cause: the message feed div is flex-1 overflow-y-auto inside a flex
column parent with a fixed height: 100vh, but no element in that flex chain
sets min-height: 0. Flex items default to min-height: auto, meaning a flex
child expands to its content's full natural height instead of being capped
by the parent and scrolling internally. Without min-height: 0 somewhere in
the chain, overflow-y-auto on the message feed never actually activates
within its own bounded box, because the box itself just grows past 100vh
along with everything else, and the closest actual scrollable boundary ends
up being effectively the whole panel.

---

## ACTION

File: `/home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx`

Find the message feed container:

```typescript
<div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3">
```

Add min-h-0 to its className so it reads:

```typescript
<div className="flex-1 min-h-0 overflow-y-auto p-4 flex flex-col gap-3">
```

This is the standard fix for this exact flexbox behavior: min-h-0 overrides
the default min-height: auto on a flex item, letting flex-1 actually shrink
the box to the available space and overflow-y-auto take over scrolling
within that bounded box, independent of the notifications block above it.

Do not change the notifications block's flex-shrink-0. It is correct as is,
it should not shrink, it should just stop being part of the same runaway
growth. Do not change the outer panel container's height:100vh or display
flex settings. Do not touch any other file.

---

## VERIFY AFTER ACT

```bash
grep -n "min-h-0" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx
```

Expected: present on the message feed div.

```bash
cd /home/corby/jamm-os/frontend
npm run build
```

Expected: zero TypeScript errors.

---

## MANUAL VERIFICATION (the actual test)

1. Restart the frontend.
2. Open a client page with 2+ active notification triggers, same scenario as
   before, so 2 draft notification cards stack at the top.
3. Confirm the input bar at the bottom of the panel is visible without any
   scrolling.
4. Confirm there are now two independently scrollable regions: scrolling
   inside the notification cards area (if it overflows) does not move the
   chat message feed, and scrolling the chat message feed does not move the
   notification cards.
5. Regression check: dismiss both notifications and confirm the chat feed
   still scrolls normally with no notifications present.
6. Regression check: with notifications present, type a message and send it,
   confirm the new message appears in the chat feed and the feed
   auto-scrolls to it without affecting the notification cards above.

Report what you observe at step 3 specifically.

---

## GIT

```bash
cd /home/corby/jamm-os
git add -A
git commit -m "fix: Concierge panel message feed now scrolls independently of stacked notification cards instead of one shared overflow region trapping the input bar off-screen, by adding min-h-0 to override default flex item min-height: auto"
git pull --rebase origin main
git push origin main
```

If conflicts on task.md use --theirs. Conflicts on source files use --ours.