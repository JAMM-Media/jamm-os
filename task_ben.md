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

# ENVIRONMENT SANITY CHECK — MANDATORY BEFORE ANY OTHER STEP
This section exists because Claude Code twice reported stale route-conflict files (frontend/src/app/settings/, frontend/src/app/calendar/, frontend/src/app/(dashboard)/) as real, current, build-blocking evidence and asked for permission to delete them. Both times, those files did not exist in the real repo at /home/corby/jamm-os. They existed only on the separate Windows-side checkout at /mnt/c/Users/corby/jamm-os, a pre-rename leftover copy that is for viewing only and is never the source of truth. Some tool call had actually resolved against that path instead of the real WSL repo, and reported what it found there as if it were current.

Before running any other command in this task:
1. Run: pwd — the output must be exactly /home/corby/jamm-os or a path underneath it. If it is not, stop and cd /home/corby/jamm-os before doing anything else.
2. State explicitly in the report, as its own line, that no command in this task read, listed, or resolved any path under /mnt/c/Users or any other Windows-side location. This is not optional boilerplate, it is a real claim that must be true.
3. If at any point a command needs to check whether something exists "on disk," that means the real WSL filesystem under /home/corby/jamm-os, never the Windows copy, even implicitly, even as a fallback.

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

# REPORTING DISCIPLINE — MANDATORY FOR EVERY TASK
This section exists because a past session confidently claimed specific files were stale untracked leftovers safe to delete, citing a real commit hash correctly, then drew a false conclusion from it. The files did not exist on disk at all. The commit was real. The conclusion was not. That is the failure mode this section guards against: not sloppy guessing, but a plausible-sounding narrative that outran the actual evidence.

- Quote literal command output verbatim in every summary. Never paraphrase output, never assert a conclusion in place of showing the output it came from. If a claim cannot be backed by pasted, real output in the same message, it does not go in the summary as fact.
- If evidence is ambiguous, incomplete, contradictory, or simply absent, say so explicitly and stop. Do not fill a gap in the evidence with a story that sounds coherent. An honest "I don't have enough evidence to conclude this" is always the correct output when that is the true state.
- Never take any action, including deletions, fixes, or refactors, beyond what CHANGE INSTRUCTIONS explicitly names, even if something discovered mid-task seems to obviously justify it. Surface it as a finding in the report and wait for a real instruction. Diagnosis and action are separate steps, not one motion.
- Before claiming any file doesn't belong, is stale, is dead code, or should be deleted, confirm both that it exists on disk (ls -la) and its real git tracking status (git status --short and git ls-files) in the same message as the claim itself, not as a follow-up only produced if challenged.

---

# Section 3 - The task

TASK: Build a config prompt for the two widgets that require a client_id (client_health_snapshot, single_client_quick_view), so they become addable through the gallery. Currently these two are excluded from the gallery entirely since no config UI exists yet.

USE: claude sonnet

ENVIRONMENT SANITY CHECK:

pwd

State plainly that no path in this task resolves against /mnt/c/Users or any Windows-side copy.

VERIFY BEFORE ACT:

grep -n -B 5 -A 60 "function AddWidgetModal" "src/app/(app)/dashboard/page.tsx"

grep -n "config_schema.length === 0" "src/app/(app)/dashboard/page.tsx"

Paste the real output of both. Confirm the exact current gallery filtering logic (from the prior task that added the config_schema.length === 0 disabled-state check) and the real shape of a catalog entry's config_schema field for client_health_snapshot and single_client_quick_view, specifically the field key name expected (client_id) and its type value.

WHAT THIS IS:

client_health_snapshot and single_client_quick_view both have a config_schema with one required field for client_id, confirmed in batch 4a. The gallery currently either hides these two entirely or would add them with an empty config object, which would be wrong since the backend requires a real client_id and returns a 400 without one. Right now the app already has a working, real pattern for this exact kind of picker: NewTaskModal fetches clients via clientsApi.list(0, 100), maps items to {value: c.id, label: c.name}, and feeds that into the existing SelectInput component. This task reuses that exact pattern rather than inventing a new client-picker component.

CHANGE INSTRUCTIONS:

In the Add Widget gallery, when a widget with a non-empty config_schema is clicked (currently this is only these 2 widgets, but write this generically keyed off config_schema having entries with type client_picker, not hardcoded to these 2 type_keys by name, so any future widget with the same config field type is automatically handled the same way), instead of adding the widget immediately, open a small second modal prompting for the required field, using the real SelectInput and clientsApi.list(0, 100) pattern from NewTaskModal for a client_id field specifically. On confirming the prompt, append the new widget instance to editedWidgets with config set to {client_id: <the selected value>}, using the same instance_id and positioning logic already used for the no-config gallery entries. Cancelling the prompt returns to the gallery without adding anything.

These two widgets should now actually appear in the gallery, remove whatever exclusion or hiding was previously applied to them, if the current filtering logic already naturally includes them once the config_schema.length === 0 check passes them through to the always-addable branch, confirm that's the case rather than assuming, based on the real VERIFY BEFORE ACT output.

VERIFY AFTER ACT:

cd /home/corby/jamm-os/frontend
npm run build

grep -n "client_picker\|clientsApi" "src/app/(app)/dashboard/page.tsx"

git diff --stat "src/app/(app)/dashboard/page.tsx"

MANUAL VERIFICATION:

Restart the frontend dev server only. Reload /dashboard, enter Edit Dashboard, open Add Widget, confirm Client Health Snapshot and Single Client Quick View now appear in the gallery. Click one, confirm a client picker prompt appears with real client names, not empty or broken. Select a real client, confirm it adds to the canvas and renders that specific client's real data, not an error or someone else's data. Add the same widget again with a different client selected, confirm both instances exist independently showing different clients. Click Done, reload, confirm both persisted with the correct client data still showing for each. Report back with a screenshot.

GIT:

git add -A
git commit -m "add a client picker config prompt for client_health_snapshot and single_client_quick_view, reusing the existing clientsApi.list and SelectInput pattern already used in NewTaskModal rather than building a new picker component, wired generically off config_schema field type so any future widget needing the same picker is handled the same way, these two widgets now appear and are fully addable in the Add Widget gallery"
git pull --rebase origin main
git push origin main
git log --oneline -3

Paste the real output of git log --oneline -3 showing the new commit hash present next to origin/main. Do not report this as done based on the push command running, confirm the real log output showing origin/main at the new hash.