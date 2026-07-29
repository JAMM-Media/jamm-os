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

TASK: Fix concierge_entry_mode being read from per-browser localStorage instead of the real, server-persisted firm setting, causing a new browser or device to show the wrong entry point

USE: Fable 5

VERIFY BEFORE ACT:

sed -n '68,79p' /home/corby/jamm-os/app/api/users.py

grep -n "firm_type" /home/corby/jamm-os/app/schemas/user.py

grep -n "AuthUser\|firm_type" /home/corby/jamm-os/frontend/src/lib/hooks/useAuth.tsx

grep -n "conciergeEntryMode\|jamm_concierge_entry_mode" /home/corby/jamm-os/frontend/src/components/layout/AppShell.tsx

Confirm GET /users/me already copies firm_type and concierge_active from the current firm onto the user response, following an established pattern of selectively exposing specific firm fields on the user object. Confirm this endpoint is called once per page load via AuthProvider's effect, and that AppShell currently has no access to firm data or this endpoint at all, instead reading conciergeEntryMode purely from localStorage. Confirm this before editing.

WHAT THIS IS:

Confirmed live tonight: setting the Concierge entry mode to Sidebar in Settings correctly persisted to the firm's real settings in the database, confirmed by Settings correctly showing Sidebar selected in a brand new incognito session. But the actual floating button still appeared in that same incognito session, because AppShell reads its rendering decision from localStorage, which is empty on a fresh browser, and defaults to floating regardless of what the firm's real, saved setting is. This is the same class of bug flagged and intentionally deferred earlier tonight when this setting was first built, and was not caught during the later sidebar-versus-floating rename because that task's instructions explicitly preserved the existing localStorage mechanism rather than fixing it. The correct fix follows the exact pattern already proven correct in this codebase for firm_type and concierge_active: GET /users/me already selectively copies specific firm fields onto the user response, and AuthProvider already fetches this once on every page load, so AppShell can get the real, correct value for free through the existing useAuth hook rather than adding a new network call or reading unreliable per-browser storage.

CHANGE INSTRUCTIONS:

Add concierge_entry_mode as an optional string field to UserOut in schemas/user.py, matching the exact style of the existing firm_type field.

In GET /users/me in users.py, add one more line following the exact same pattern as the two existing lines, setting user_out.concierge_entry_mode from current_firm.settings, defaulting to floating if the key is absent from the settings JSON blob or if settings itself is null.

In useAuth.tsx, add concierge_entry_mode as an optional field on the AuthUser interface, matching the style of the existing firm_type field.

In AppShell.tsx, import and call useAuth, and use user.concierge_entry_mode as the primary source of truth for which entry point to render, defaulting to floating if the user object has not loaded yet or the field is absent. Keep the existing localStorage read and the jamm:concierge-entry-mode-changed event listener as a same-session, same-tab responsiveness mechanism so the UI still updates immediately after a user changes the setting in Settings without needing a full reload, but the value from useAuth's user object should be what a fresh page load or a different browser starts from, not localStorage. Do not change Settings page's own logic for saving the setting, this task only changes how AppShell decides which entry point to render.

VERIFY AFTER ACT:

grep -n "concierge_entry_mode" /home/corby/jamm-os/app/schemas/user.py /home/corby/jamm-os/app/api/users.py /home/corby/jamm-os/frontend/src/lib/hooks/useAuth.tsx /home/corby/jamm-os/frontend/src/components/layout/AppShell.tsx

Expected: present in all four files.

python3 -c "from app.main import app; print('OK')"

npx tsc --noEmit

MANUAL VERIFICATION:

Restart both servers.

In your normal browser, confirm the Settings page still shows Sidebar selected and the sidebar entry point still renders correctly.

Open a brand new incognito or private window, log in as the same firm owner. Confirm the sidebar nav item appears correctly on first load, and the floating button does not appear, without needing to visit Settings first or do anything else.

Back in Settings, switch to Floating, confirm it updates immediately in the current tab without a reload, matching the existing same-session behavior.

Open a second, different incognito window, log in fresh, confirm it now correctly shows Floating on first load, matching the most recently saved real setting.

Report pass or fail for all four checks individually, since this is the second time this exact class of bug has been found tonight and deserves real, careful confirmation.

GIT:

git add -A

git commit -m "fix concierge_entry_mode being sourced from per-browser localStorage instead of the real, server-persisted firm setting, causing a new browser or device to always default to floating regardless of what was actually saved, confirmed live tonight via a fresh incognito session showing Sidebar correctly selected in Settings while the floating button still rendered; fixed by threading the real value through GET /users/me the same way firm_type and concierge_active already are, so AppShell reads it via the existing useAuth hook instead of localStorage, keeping localStorage only as a same-tab responsiveness layer after a live change"

git pull --rebase origin main

git push origin main