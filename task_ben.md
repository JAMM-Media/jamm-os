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

# Task: Fix Go to Tasks chip navigation, and complete the calendar chip fix end-to-end (frontend label + backend classifier)

USE: claude sonnet

## VERIFY BEFORE ACT

grep -n "const routes: Record<string, string>" -A 10 /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Confirm 'Go to Tasks' is absent from this routes map, while it exists as a valid label in TOPIC_CHIPS for the tasks topic, meaning the chip renders but does nothing on click.

grep -n "const TOPIC_CHIPS" -A 15 /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Confirm there is no calendar entry anywhere in this map.

sed -n '194,263p' /home/corby/jamm-os/app/api/concierge/route.py

Confirm _TOPIC_KEYWORDS has no "calendar" key and no calendar-related keywords in any other topic's set, meaning the backend classifier can never produce a "calendar" topic value regardless of what the frontend expects.

## WHAT IS WRONG

Three related gaps, all stemming from the same underlying issue: the suggestion-chip system spans two layers (a backend keyword classifier in route.py that decides the topic, and a frontend map in ConciergePanel.tsx that turns a topic into a chip label and then a route) with no shared source of truth between them, so entries can exist on one side without the other.

1. Confirmed via live testing: 'Go to Tasks' exists as a chip label in TOPIC_CHIPS and the backend correctly tags tasks questions [TOPIC:tasks], but the routes map inside handleSuggestion has no 'Go to Tasks' entry, so clicking the chip does nothing.

2. There is no calendar entry in TOPIC_CHIPS, so even if the backend could produce [TOPIC:calendar], no chip would show.

3. There is no calendar keyword set in the backend's _TOPIC_KEYWORDS at all, so _classify_topic can never return "calendar" in the first place -- any calendar-related question always falls through to "general". This means fixing only the frontend (issue 2) would be incomplete on its own, since the backend would never actually produce the topic value needed to trigger it.

All three must be fixed together for the calendar chip to work end to end; fixing only some of them leaves an unreachable, dead code path.

## ACTION

File 1: /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Fix A -- add the missing route for the existing Go to Tasks chip. Change:

      'Go to Documents': '/documents',
      'Go to Dashboard': '/dashboard',
      'Import clients': '/clients',

To:

      'Go to Documents': '/documents',
      'Go to Dashboard': '/dashboard',
      'Go to Tasks': '/tasks',
      'Go to Calendar': '/calendar',
      'Import clients': '/clients',

Fix B -- add a calendar entry to TOPIC_CHIPS:

          tasks: ['Go to Tasks'],
          calendar: ['Go to Calendar'],

Place the calendar line directly after tasks in the same map. Do not change any other topic or route mapping in this file.

File 2: /home/corby/jamm-os/app/api/concierge/route.py

Fix C -- add a calendar keyword set to _TOPIC_KEYWORDS, matching the exact formatting style of the existing entries, placed near "automations" and "irs_authorizations":

    "calendar": {
        "calendar", "schedule", "scheduled", "appointment", "appointments",
        "meeting", "meetings", "deadline calendar view", "calendar event",
        "calendar view", "upcoming events", "holiday", "holidays",
    },

Do not change any other topic's keyword set or _classify_topic itself. Do not touch any other file in either location.

## VERIFY AFTER ACT

grep -n "'Go to Tasks': '/tasks'\|'Go to Calendar': '/calendar'" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Expected: both present.

grep -n "calendar: \['Go to Calendar'\]" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Expected: present.

grep -n "\"calendar\":" /home/corby/jamm-os/app/api/concierge/route.py

Expected: present as a new key in _TOPIC_KEYWORDS.

cd /home/corby/jamm-os/frontend
npm run build

Expected: zero TypeScript errors.

python3 -c "from app.api.concierge.route import router; print('OK')"

Expected: OK, no import errors.

## MANUAL VERIFICATION (the actual test -- restart BOTH backend and frontend before testing, since this task spans both)

1. Restart the backend and the frontend, both with clean builds.
2. Ask "where are my tasks?" -- confirm the Go to Tasks chip appears and clicking it now navigates to the Tasks page correctly.
3. Ask "where is my calendar?" or "do I have any meetings scheduled?" -- open DevTools Console and confirm the [CONCIERGE RAW] output shows [TOPIC:calendar], not [TOPIC:general].
4. Confirm the Go to Calendar chip appears below that response.
5. Click it and confirm it navigates to the Calendar page correctly.
6. Regression check: click 2-3 other existing chips (Go to Clients, Go to Billing) and confirm they still work normally.

Report what you observe at steps 2, 3, and 5.

## GIT

cd /home/corby/jamm-os
git add -A
git commit -m "fix: Go to Tasks chip now navigates correctly (was missing from the frontend routes map despite the chip label existing), and calendar topic support is now complete end to end -- added the missing calendar keyword set to the backend classifier so it can actually produce a calendar topic value, plus the corresponding frontend chip label and route that were added but previously unreachable without this backend counterpart"
git pull --rebase origin main
git push origin main

If conflicts on task.md use --theirs. Conflicts on source files use --ours.