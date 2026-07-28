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

TASK: Fix the internal "Concierge question log" link rendering outside the Settings page's main content column, causing it to appear as a stray third flex column on the right side of the screen

USE: claude sonnet

VERIFY BEFORE ACT:

sed -n '670,680p' /home/corby/jamm-os/frontend/src/app/\(app\)/settings/page.tsx

sed -n '1300,1332p' /home/corby/jamm-os/frontend/src/app/\(app\)/settings/page.tsx

Confirm the main content column opens at line 677 with className "flex-1 overflow-y-auto p-6 flex flex-col gap-6", closes at line 1317 with a bare closing div, and that the isFirmOwner block containing the Concierge question log link at lines 1318-1327 currently sits after that closing div, making it a sibling of the content column inside the outer flex h-full row rather than a child of the content column. Confirm this before editing.

WHAT THIS IS:

Confirmed live and diagnosed directly from the rendered DOM tonight: the internal Concierge question log link was appearing far on the right side of the Settings page, with the actual settings content squeezed narrow on the left. Root cause confirmed by tracing the actual DOM structure: this is not a missing width or styling issue, an earlier attempted fix adding max-w-lg to this element's wrapper made no visible difference, correctly ruling that out. The real cause is a JSX nesting bug: the main content column's closing div appears one place too early, stranding the isFirmOwner block containing this link as a third sibling in the outer horizontal flex row alongside the settings navigation sidebar and the main content column, instead of being the last item inside the main content column's own vertical stack. Since the outer row is a horizontal flex container, this stray third item claims its own column of horizontal space, visually squeezing the real content column and stranding the link far to the right.

CHANGE INSTRUCTIONS:

Move the entire isFirmOwner block, from the opening {isFirmOwner && ( through its closing )}, currently located immediately after the main content column's closing div, to instead sit immediately before that same closing div, as the last child inside the main content column, directly after the Migration tab line. Do not change the content of the block itself, its className, or the link's href or text. Do not change any other tab or section in this file, this is purely a structural relocation of one existing block to fix its nesting.

VERIFY AFTER ACT:

grep -n "flex-1 overflow-y-auto p-6 flex flex-col gap-6" -A 1 /home/corby/jamm-os/frontend/src/app/\(app\)/settings/page.tsx

grep -n "Concierge question log" -B 12 /home/corby/jamm-os/frontend/src/app/\(app\)/settings/page.tsx

Confirm the isFirmOwner block containing the link now appears before the content column's closing div, not after it, by reading the surrounding lines directly.

npx tsc --noEmit

MANUAL VERIFICATION:

Restart the frontend.

Reload the Settings page as a firm owner. Confirm the settings content, Profile card, Concierge Entry Point section, Email Settings, etc, now occupies the full expected width of the main content column, not squeezed narrow.

Confirm the Concierge question log link now appears directly below the last visible settings section, in the same left-aligned column as everything else, not stranded on the right side of the screen.

Confirm the link still navigates correctly to /concierge-log when clicked.

Report pass or fail for all three checks individually.

GIT:

git add -A

git commit -m "fix the internal Concierge question log link rendering as a stray third column in the Settings page's outer horizontal flex layout, root cause confirmed by tracing the live DOM tree: the main content column's closing div appeared one place too early in the JSX, stranding this block as a sibling of the content column instead of its last child, correcting an earlier incorrect assumption that this was a missing width class rather than a nesting bug"

git pull --rebase origin main

git push origin main