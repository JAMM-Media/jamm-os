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

TASK: Make the Concierge panel and the client Notes panel mutually exclusive, fixing a real overlap where both share the same fixed right-edge position and z-index

USE: claude sonnet

VERIFY BEFORE ACT:

cat /home/corby/jamm-os/frontend/src/lib/events/conciergeEvents.ts

sed -n '60,70p' /home/corby/jamm-os/frontend/src/app/\(app\)/clients/\[id\]/page.tsx

sed -n '1050,1060p' /home/corby/jamm-os/frontend/src/app/\(app\)/clients/\[id\]/page.tsx

sed -n '108,120p' /home/corby/jamm-os/frontend/src/components/layout/AppShell.tsx

grep -n "position\|right\|zIndex" /home/corby/jamm-os/frontend/src/components/notes/NotesPanel.tsx | head -10

Confirm NotesPanel uses position fixed, right 0, width 360, and z-index 40, the exact same right-edge anchor and z-index as ConciergePanel, confirmed as a real, live, reported overlap tonight where opening both hides the notes panel behind or beneath the Concierge panel. Confirm notesOpen state lives entirely locally in the client detail page, and conciergeOpen state lives entirely locally in AppShell, with zero existing coordination between them. Confirm the existing emitConciergeAction and onConciergeAction pattern in conciergeEvents.ts as the established, working style for cross-component signaling already used extensively tonight.

WHAT THIS IS:

A real, live-reported bug tonight: the Concierge panel and the client detail page's Notes panel are two independent, fixed-position, right-anchored panels sharing the same screen space and the same z-index, with no awareness of each other. Opening one while the other is already open causes whichever mounts on top to fully hide the other. The decision made was to make them mutually exclusive rather than attempting to offset one by the other's width, since a width-based offset would only work correctly above a certain window size and risks reintroducing the same class of viewport-dependent layout bug already found and fixed once tonight with the draggable entry button. The rule: whichever panel the user explicitly opens should close the other one automatically.

CHANGE INSTRUCTIONS:

In conciergeEvents.ts, add a new event name constant, a new exported function emitPanelExclusive that accepts a panel argument of type 'concierge' or 'notes' and dispatches a new custom window event carrying that value, and a matching exported onPanelExclusive listener function, following the exact same style, structure, and naming convention already used for emitConciergeAction and onConciergeAction in this same file.

In AppShell.tsx, inside handleConciergeOpen, call emitPanelExclusive('concierge') alongside the existing setConciergeOpen(true) call, so every path that opens the Concierge panel, the floating button, the sidebar nav item, and any open-panel action, is covered by this one function. Add a new effect, using onPanelExclusive, that closes the Concierge panel, calling the same logic already used in handleConciergeClose, whenever it receives an event where the panel value is 'notes'.

In the client detail page, inside the NotesTab's onClick handler, which currently only calls setNotesOpen(true), also call emitPanelExclusive('notes') alongside it. Add a new effect, using onPanelExclusive, that calls setNotesOpen(false) whenever it receives an event where the panel value is 'concierge'.

Do not change NotesPanel's or ConciergePanel's own internal positioning, width, or z-index, and do not change any other existing behavior of either panel, this task only adds the mutual-exclusivity coordination between them.

VERIFY AFTER ACT:

grep -n "emitPanelExclusive\|onPanelExclusive" /home/corby/jamm-os/frontend/src/lib/events/conciergeEvents.ts /home/corby/jamm-os/frontend/src/components/layout/AppShell.tsx /home/corby/jamm-os/frontend/src/app/\(app\)/clients/\[id\]/page.tsx

Expected: the new functions defined once in conciergeEvents.ts, and both emit and listen usage present in both AppShell.tsx and the client detail page.

npx tsc --noEmit

MANUAL VERIFICATION:

Restart the frontend.

On a client detail page, open the Concierge panel first, using the floating button or sidebar entry point, confirm it opens normally. Then click the Notes tab's trigger. Confirm the Concierge panel closes automatically and the Notes panel opens and is fully visible, not hidden.

Reverse the order: open Notes first, confirm it opens normally, then open the Concierge panel. Confirm the Notes panel closes automatically and the Concierge panel opens and is fully visible.

Confirm opening and closing either panel on its own, with the other never having been opened, still works exactly as it did before this change, with no unexpected closing or interference.

Report pass or fail for each of these three checks individually.

GIT:

git add -A

git commit -m "make the Concierge panel and the client detail page's Notes panel mutually exclusive, fixing a real, live-reported overlap tonight where both are independently fixed-position, right-anchored, and share the same z-index, causing whichever opens second to fully hide the other; added a small, focused emitPanelExclusive and onPanelExclusive event pair following the exact same established cross-component signaling pattern already used throughout tonight, chosen over a width-based offset to avoid reintroducing the same viewport-dependent layout risk already found and fixed once tonight with the draggable entry button"

git pull --rebase origin main

git push origin main