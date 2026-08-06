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

TASK: Build real frontend rendering for the 7 widget types added to the backend in batch 4a (my_tasks, client_health_snapshot, client_communication_gap, outstanding_document_requests, unbilled_hours, single_client_quick_view, recent_firm_chat_activity). These are currently addable through the gallery and save correctly, but render as literal "Unknown widget: X" text since no frontend component exists for them, the widget-to-component lookup only covers the original 9 launch-catalog types.

USE: claude fable-5

ENVIRONMENT SANITY CHECK:

pwd

State plainly that no path in this task resolves against /mnt/c/Users or any Windows-side copy.

VERIFY BEFORE ACT:

grep -n -B 3 -A 15 "Unknown widget" "src/app/(app)/dashboard/page.tsx"

grep -n -A 15 "def get_task_status\|def compute_client_health\|def get_client_communication_gap\|def get_outstanding_document_requests\|def get_time_tracking_detail\|def get_client_full_snapshot\|def get_recent_firm_chat_activity" /home/corby/jamm-os/app/api/concierge/functions.py /home/corby/jamm-os/app/services/client_health_service.py

curl -s -X POST http://localhost:8000/auth/token -H "Content-Type: application/json" -d '{"username": "owner@riverside-demo.com", "password": "Demo2026x"}'

Paste all real output. For the curl, use the returned token to also call each of these 7 live and paste the real JSON response shape for each:
GET /dashboard/widgets/my_tasks/data
GET /dashboard/widgets/client_communication_gap/data
GET /dashboard/widgets/outstanding_document_requests/data
GET /dashboard/widgets/unbilled_hours/data
GET /dashboard/widgets/recent_firm_chat_activity/data
For client_health_snapshot and single_client_quick_view, use client_id=bd01c05c-451f-4704-b5f8-ca69f989fb38 as a real known test client.

Do not write any component against a guessed or assumed response shape, only against what these real calls actually return.

WHAT THIS IS:

The widget-to-component lookup in the dashboard page currently only has cases for the 9 launch-catalog widgets, falling through to a literal "Unknown widget" message for anything else, which is exactly what's happening for these 7. Each of these widgets already has real, working backend data, confirmed live in this task's own verification step, this is purely a missing frontend rendering problem, not a data problem. Follow the same pattern already established for the 9 existing widgets: a small presentational component per widget type, using the same design tokens (bg-surface-card, rounded-[8px], border-surface-border, skeleton-while-loading convention) already used throughout this file, with an empty state for when there's genuinely nothing to show, matching whatever empty-state phrasing convention is already used on that data's real source page if one exists (documents page, timesheets page, firm chat page), not invented fresh.

CHANGE INSTRUCTIONS:

Add 7 new presentational components to the dashboard page, one per widget type, each rendering the real fields confirmed in VERIFY BEFORE ACT for that endpoint. Keep each one visually consistent with the existing 9, header with the widget's display name, content area below, empty state styled the same as UpcomingDeadlinesList or OverdueEngagementsTable's existing empty states (green checkmark-style success copy for a genuinely empty/good state).

For client_health_snapshot and single_client_quick_view specifically, these two require a client_id from config and are not yet addable through the gallery, since the client-picker UI is a separate not-yet-built task, batch 4c. Build their rendering components now anyway so they're ready, but it's expected they won't be reachable through the UI yet, note this plainly in the report rather than trying to work around it.

Add all 7 new type_keys to the existing widget-to-component lookup, replacing the current fallback to "Unknown widget" for these specific keys with their real new components.

VERIFY AFTER ACT:

cd /home/corby/jamm-os/frontend
npm run build

grep -n "Unknown widget" "src/app/(app)/dashboard/page.tsx"

This should now only match the fallback case itself for genuinely unrecognized type_keys, not any of these 7 by name.

git diff --stat "src/app/(app)/dashboard/page.tsx"

MANUAL VERIFICATION:

Restart the frontend dev server only. Reload /dashboard, enter Edit Dashboard, open Add Widget, add my_tasks and recent_firm_chat_activity (or any 2-3 of the 5 gallery-reachable new widgets), confirm they now render real content, not "Unknown widget" text. Click Done, reload, confirm they persisted with real content still showing. Report back with a screenshot.

GIT:

git add -A
git commit -m "add real frontend rendering for the 7 batch 4a widget types (my_tasks, client_health_snapshot, client_communication_gap, outstanding_document_requests, unbilled_hours, single_client_quick_view, recent_firm_chat_activity), replacing the Unknown widget fallback these previously hit since only the original 9 launch-catalog widgets had components. client_health_snapshot and single_client_quick_view components are built but not yet reachable through the gallery, pending the client-picker UI in batch 4c"
git pull --rebase origin main
git push origin main
git log --oneline -3

Paste the real output of git log --oneline -3 showing the new commit hash present next to origin/main. Do not report this as done based on the push command running, confirm the real log output showing origin/main at the new hash.