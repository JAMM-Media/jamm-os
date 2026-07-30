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

TASK: Add a firm-level Concierge Suggestions Off/On setting and gate all nine inline redesign pages behind it

USE: Fable 5

VERIFY BEFORE ACT:

sed -n '68,79p' /home/corby/jamm-os/app/api/users.py

grep -n "concierge_entry_mode" /home/corby/jamm-os/app/schemas/user.py /home/corby/jamm-os/frontend/src/lib/hooks/useAuth.tsx

sed -n '895,935p' /home/corby/jamm-os/frontend/src/app/\(app\)/settings/page.tsx

For each of these nine files, find and read the exact conditional line that currently decides whether to render SuggestionCard or ContextualBanner, do not assume its exact wording, read it directly in each file before changing it:

grep -n "SuggestionCard\|ContextualBanner" /home/corby/jamm-os/frontend/src/app/\(app\)/staff/page.tsx /home/corby/jamm-os/frontend/src/app/\(app\)/tasks/page.tsx /home/corby/jamm-os/frontend/src/app/\(app\)/engagements/page.tsx /home/corby/jamm-os/frontend/src/app/\(app\)/calendar/page.tsx /home/corby/jamm-os/frontend/src/app/\(app\)/timesheets/page.tsx /home/corby/jamm-os/frontend/src/app/\(app\)/clients/\[id\]/page.tsx /home/corby/jamm-os/frontend/src/app/\(app\)/clients/page.tsx /home/corby/jamm-os/frontend/src/app/\(app\)/documents/page.tsx /home/corby/jamm-os/frontend/src/app/\(app\)/billing/page.tsx

Confirm concierge_entry_mode's exact existing pattern in all three places, schemas/user.py, users.py's read_users_me, and useAuth.tsx's AuthUser interface, since this new setting follows that identical, already-proven pattern exactly, not a new mechanism.

WHAT THIS IS:

Direct product decision made tonight, after building nine real, live inline suggestion surfaces across the app: a firm owner should be able to turn all of them off entirely, since it is their page and their choice. This is a real, permanent, two-state setting, Off or On, not a slider or a frequency dial. A third, more granular option was discussed and deliberately deferred, since it would require real dismissal-persistence infrastructure that does not exist yet across any of the nine banners, this task only builds the clean two-state version. The setting is named Concierge Suggestions in Settings, with the field labeled Show suggestions on pages, matching the tone and structure of the existing Concierge Entry Point section directly above it. Defaulting to On when the setting has never been explicitly changed, so existing firms keep the behavior they already have unless they deliberately turn it off.

CHANGE INSTRUCTIONS:

Backend: add concierge_suggestions_enabled as an optional boolean field to UserOut in schemas/user.py, matching the exact style of the existing concierge_entry_mode field. In GET /users/me in users.py, add one more line following the exact same pattern as the existing concierge_entry_mode line, setting user_out.concierge_suggestions_enabled from current_firm.settings, defaulting to true if the key is absent from the settings JSON blob or if settings itself is null. No new endpoint is needed, this reuses the existing PATCH /users/firm/settings merge-safe endpoint for writing, the same one already used for concierge_entry_mode.

Frontend, useAuth.tsx: add concierge_suggestions_enabled as an optional boolean field on the AuthUser interface, matching the style of the existing concierge_entry_mode field.

Frontend, Settings page: add a new section titled Concierge Suggestions, placed directly below the existing Concierge Entry Point section, with a field labeled Show suggestions on pages and two real radio-style circular controls labeled Off and On, following the exact same visual and interaction pattern already used for the Entry style controls immediately above it. Include a short description line, for example something like Off hides all Concierge suggestion cards and banners across the app. On shows them when something real is worth noticing. Selecting either option immediately calls the existing PATCH /users/firm/settings endpoint with concierge_suggestions_enabled true or false, matching the exact call style already used for concierge_entry_mode. Read the current value from the firm's existing settings object on page load to show the correct option selected, defaulting to On if the key is absent.

Frontend, all nine pages: in each of the nine files listed above, find the exact conditional currently gating whether SuggestionCard or ContextualBanner renders, and add an additional check requiring user?.concierge_suggestions_enabled to not be explicitly false, meaning it should render when the value is true, undefined, or not yet loaded, and should not render only when it is explicitly false. Use the exact same user object from useAuth already available or easily added to each of these files. Do not change any of the real data fetching, trigger thresholds, or business logic already in these nine files, this task only adds one additional gating condition to each existing render check.

VERIFY AFTER ACT:

grep -n "concierge_suggestions_enabled" /home/corby/jamm-os/app/schemas/user.py /home/corby/jamm-os/app/api/users.py /home/corby/jamm-os/frontend/src/lib/hooks/useAuth.tsx /home/corby/jamm-os/frontend/src/app/\(app\)/settings/page.tsx

Expected: present in all four.

grep -n "concierge_suggestions_enabled" /home/corby/jamm-os/frontend/src/app/\(app\)/staff/page.tsx /home/corby/jamm-os/frontend/src/app/\(app\)/tasks/page.tsx /home/corby/jamm-os/frontend/src/app/\(app\)/engagements/page.tsx /home/corby/jamm-os/frontend/src/app/\(app\)/calendar/page.tsx /home/corby/jamm-os/frontend/src/app/\(app\)/timesheets/page.tsx /home/corby/jamm-os/frontend/src/app/\(app\)/clients/\[id\]/page.tsx /home/corby/jamm-os/frontend/src/app/\(app\)/clients/page.tsx /home/corby/jamm-os/frontend/src/app/\(app\)/documents/page.tsx /home/corby/jamm-os/frontend/src/app/\(app\)/billing/page.tsx

Expected: present in all nine, confirming none were missed.

python3 -c "from app.main import app; print('OK')"

npx tsc --noEmit

MANUAL VERIFICATION:

Restart both servers.

On Settings, confirm the new Concierge Suggestions section appears below Concierge Entry Point, with On selected by default.

Select Off. Visit at least three of the nine pages that currently have real trigger conditions true, for example Billing with a real overdue invoice, Engagements with a real stalled engagement, and the client detail page for a client old enough to trigger the portal invite card. Confirm none of them show any suggestion card or banner, even though their underlying real conditions are still true.

Select On again. Revisit the same three pages, confirm the suggestions reappear correctly with the same real data as before.

Reload the page entirely after selecting Off, confirm the choice persisted as a real firm setting, not just local UI state.

Report pass or fail for all four checks individually.

GIT:

git add -A

git commit -m "add a firm-level Concierge Suggestions Off or On setting, letting a firm owner turn off all nine inline suggestion cards and banners built across the app tonight, following the identical already-proven pattern used for the Concierge Entry Point setting, threaded through GET /users/me and read via useAuth rather than localStorage so it is correct on first load from any browser or device, defaulting to On so existing firms keep current behavior unless they explicitly opt out"

git pull --rebase origin main

git push origin main