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

TASK: Make the floating persistent entry button draggable to anywhere on the main screen, with a persisted personal position and safe boundary clamping

USE: Fable 5

VERIFY BEFORE ACT:

sed -n '105,120p' /home/corby/jamm-os/frontend/src/components/layout/AppShell.tsx

cat /home/corby/jamm-os/frontend/src/components/concierge-inline/PersistentEntryButton.tsx

grep -n "w-12\|w-\[220px\]" /home/corby/jamm-os/frontend/src/components/layout/Sidebar.tsx

Confirm the button's wrapping div currently uses a fixed bottom-6 right-6 position with no drag capability, confirm PersistentEntryButton's own onClick prop is what currently opens the panel, and confirm the main navigation sidebar is 48px wide when collapsed and 220px wide when expanded, before making any change.

WHAT THIS IS:

Direct product decision made tonight, after seeing the floating button block part of the Calendar page's Upcoming panel. The button should become draggable anywhere on the main content area, like a movable widget, so a person can put it wherever it does not get in the way on any given page. This must not allow the button to be dragged onto the main left navigation sidebar, and must not allow it to be dragged into the Concierge panel's own space on the right, which only matters while the panel is open, at which point this button is already hidden. This is a personal, per-browser preference, not a firm-wide setting, since different people may want it in different places depending on their own screen and habits.

CHANGE INSTRUCTIONS:

In AppShell.tsx, replace the static fixed bottom-6 right-6 wrapper div with a draggable version. Add a new piece of state holding either a real pixel position, an object with x and y numbers, or null meaning use the original default bottom-right corner position. Initialize this state to null on first render to avoid any server and client mismatch, then read a stored position from localStorage inside a useEffect after mount, the same safe pattern already used elsewhere in this file for other browser-only state.

Implement dragging using pointer events, not the native HTML5 drag and drop API, attached to the wrapping div. On pointer down, record the starting pointer position and the button's current position. On pointer move while the pointer is down, update the button's position to follow the pointer, clamped so the button can never go further left than 220 plus 12 pixels from the left edge, never closer than 12 pixels to the top, right, or bottom edges of the viewport, accounting for the button's own real rendered width and height so it never gets clipped off screen. On pointer up, if the total distance moved since pointer down is small, a few pixels or less, treat this as a click and call the button's existing onClick behavior to open the panel. If the distance moved is larger than that, treat it as a completed drag, do not open the panel, and save the final position to localStorage under a new key so it persists across visits in this browser.

When a stored position exists, render the wrapping div using that absolute pixel position instead of the original bottom-6 right-6 classes. When no stored position exists yet, render exactly as it does today, unchanged, so nobody's current experience changes until they actually drag it once.

Do not modify PersistentEntryButton.tsx itself, all drag logic and position state should live in the wrapping div inside AppShell.tsx. Do not change the conciergeEntryMode === 'floating' and !conciergeOpen condition that already correctly decides whether this button renders at all.

VERIFY AFTER ACT:

grep -n "onPointerDown\|onPointerMove\|onPointerUp\|localStorage.*button.*position\|jamm_concierge_button_position" /home/corby/jamm-os/frontend/src/components/layout/AppShell.tsx

npx tsc --noEmit

MANUAL VERIFICATION:

Restart the frontend.

Confirm the button still appears in its normal default bottom-right position on first load, unchanged from before.

Click it normally without dragging, confirm the panel still opens correctly, confirming click behavior was not broken by adding drag support.

Drag it to the middle of the screen, release, confirm it stays exactly where dropped and does not snap back.

Reload the page entirely, confirm it remains in the same dragged position, confirming it is a real, persisted preference, not just temporary drag state.

Attempt to drag it far to the left, onto or past where the main navigation sidebar sits, confirm it stops at the boundary and cannot overlap the sidebar.

Attempt to drag it off any edge of the screen entirely, confirm it stays fully visible and clamped within the viewport in all directions.

Visit the Calendar page specifically, confirm it can now be moved away from blocking the Upcoming panel, the real problem that prompted this tonight.

Report pass or fail for each of these six checks individually.

GIT:

git add -A

git commit -m "make the floating persistent entry button draggable anywhere on the main screen, addressing it blocking the Calendar page's Upcoming panel tonight, implemented with pointer events and a click-versus-drag distance threshold, clamped so it can never be dragged onto the main navigation sidebar or off any edge of the viewport, with the final position persisted per browser as a personal preference rather than a firm-wide setting"

git pull --rebase origin main

git push origin main