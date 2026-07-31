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

TASK: Fix the persistent entry button escaping the viewport permanently when a saved position from a wider window is loaded in a narrower one

USE: claude sonnet

VERIFY BEFORE ACT:

sed -n '95,125p' /home/corby/jamm-os/frontend/src/components/layout/AppShell.tsx

Confirm the mount-time effect that reads jamm_concierge_button_position from localStorage calls setBtnPos directly with the raw parsed value, with no call to clampBtnPos, while clampBtnPos itself is only ever called during active pointer move and pointer up handlers. Confirm this means a position saved on a wider viewport can be loaded and rendered unclamped on a narrower one, placing the button fully off screen with no in-app way to recover it, since a real, live browser audit tonight found the button completely inaccessible for exactly this reason.

WHAT THIS IS:

A real, severe bug found tonight by a live browser audit: the floating Concierge entry button's position, once dragged and saved, is loaded back from localStorage exactly as saved, with no revalidation against the current window size. If the browser window is ever smaller than it was when the position was saved, for example a different monitor, a resized window, or an automated testing viewport, the button can render fully outside the visible area, and since its own click handler is what opens the panel, there is no way to recover it without directly editing browser storage. This defeats the entire point of a persistent, always-available entry point.

CHANGE INSTRUCTIONS:

In the mount-time effect that reads the stored position from localStorage, after successfully parsing it, pass the parsed x and y through clampBtnPos before calling setBtnPos, using the button's real rendered width and height the same way the drag handlers already do, not a guessed or hardcoded size. If the button's real dimensions are not yet knowable at the exact moment this effect runs, use a brief, safe fallback width and height for this one clamp call, clearly commented as a reasonable estimate for the button's typical size, and note in a comment that this is intentionally conservative to guarantee the button is never rendered off screen even before its exact size is measured. Do not change clampBtnPos itself, and do not change the drag handlers, this is purely about applying the same existing clamp logic to the initial load path, which currently skips it entirely.

VERIFY AFTER ACT:

grep -n "clampBtnPos" /home/corby/jamm-os/frontend/src/components/layout/AppShell.tsx

Expected: now called in three places, the mount-time load effect, pointer move, and pointer up, where it was previously only called in the latter two.

npx tsc --noEmit

MANUAL VERIFICATION:

Restart the frontend.

In the browser console, manually set an out-of-bounds test position to reproduce the exact bug: localStorage.setItem('jamm_concierge_button_position', JSON.stringify({x: 5000, y: 5000})), then reload the page. Confirm the button now appears clamped to a valid, visible position within the current viewport, not off screen, confirming the fix actually resolves the exact failure mode found in tonight's audit.

Confirm the button can still be dragged normally afterward, and that a normal, valid saved position still loads and renders exactly where it was left, unaffected by this change.

Report pass or fail for both checks individually.

GIT:

git add -A

git commit -m "fix the persistent entry button becoming permanently inaccessible when a saved position from a wider viewport is loaded in a narrower one, confirmed as a real, severe bug by a live browser audit tonight that found the button rendered fully off screen with no in-app way to recover it, since the mount-time load path read the stored position directly with no clamp applied, unlike the drag handlers which always clamp correctly"

git pull --rebase origin main

git push origin main