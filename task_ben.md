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

# Task: Make expanded notification list scrollable when it exceeds available space

USE: claude sonnet

## VERIFY BEFORE ACT

sed -n '870,900p' /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Confirm the current structure: the outer div is flex-col gap-2 px-4 pt-3 flex-shrink-0, containing a header row div (toggle button + Dismiss all) followed immediately by the notificationsExpanded && notifications.map(...) rendering each card directly as children of the outer div, with no scroll boundary or max-height anywhere in this section.

## WHAT IS WRONG

Confirmed via live testing with 5 active notification cards: when the notification section is expanded, the card list grows taller than the available panel space and clips instead of scrolling. The header row (N Alerts toggle + Dismiss all) stays visible but the card list itself has no scroll boundary, so cards beyond what fits on screen are simply unreachable. The panel's existing min-h-0 fix on the message feed below only constrains that section -- the notification section is flex-shrink-0 with no internal scroll, so it can grow tall enough to push everything below it out of view.

## ACTION

File: /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Wrap the notifications.map(...) output in a scrollable container div placed between the header row and the map itself:

Change:

            {notificationsExpanded && notifications.map((n) => {

To:

            {notificationsExpanded && (
              <div className="flex flex-col gap-2 overflow-y-auto max-h-64">
                {notifications.map((n) => {

And close the new wrapper div after the existing map's closing })} :

                })}
              </div>
            )}

max-h-64 (16rem, 256px) gives enough room for roughly two full draft-card notifications before scrolling activates, keeping the panel usable while preventing the list from consuming the entire panel height. The header row (toggle button + Dismiss all button) sits above this container and is always visible regardless of scroll position. Do not change the outer flex-shrink-0 wrapper, the header row, or any card rendering logic inside the map. Do not touch any other file.

## VERIFY AFTER ACT

grep -n "max-h-64\|overflow-y-auto" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Expected: present on the new wrapper div inside the notifications section.

cd /home/corby/jamm-os/frontend
npm run build

Expected: zero TypeScript errors.

## MANUAL VERIFICATION (the actual test)

1. Restart the frontend.
2. Open the Concierge panel with 4 or more notification cards present (trigger conditions already met in the test environment from earlier testing).
3. Click the N Alerts header to expand the list.
4. Confirm the notification cards now scroll independently within the expanded section, with the N Alerts header and Dismiss all button remaining fixed above the scroll area.
5. Confirm the chat message feed and input bar below are still fully visible and reachable while notifications are expanded.
6. Regression check: with 1-2 notifications (fewer than fill the max-h-64), confirm no unnecessary scrollbar appears and cards render normally without extra padding or clipping.

Report what you observe at steps 4 and 5 specifically.

## GIT

cd /home/corby/jamm-os
git add -A
git commit -m "fix: expanded notification card list now scrolls independently within a max-height container instead of growing unbounded and pushing the chat feed and input bar out of view"
git pull --rebase origin main
git push origin main

If conflicts on task.md use --theirs. Conflicts on source files use --ours.