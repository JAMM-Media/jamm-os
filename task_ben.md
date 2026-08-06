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

TASK: Build the backend for personal dashboard templates: a new table, and endpoints to list, create, and delete a user's own saved templates. This is backend only, no mini-grid UI yet, that is a follow-up task.

USE: claude sonnet

ENVIRONMENT SANITY CHECK:

pwd

State plainly that no path in this task resolves against /mnt/c/Users or any Windows-side copy.

VERIFY BEFORE ACT:

grep -n -B 3 -A 20 "class DashboardLayout" app/models/dashboard_layout.py

.venv/bin/alembic heads

Paste the real output. Confirm the exact real conventions already used for DashboardLayout (Base import, Mapped/mapped_column style, JSONB widgets column, timestamp pattern) since dashboard_templates follows the identical pattern, just with a name column added and no uniqueness constraint on user_id, since one user can have many templates, unlike dashboard_layouts which is one row per user. Confirm alembic heads shows exactly one head. If more than one, stop and report back, do not write a migration against branched history.

WHAT THIS IS:

A dashboard template is a named, saved widgets arrangement personal to the user who created it, following Ben's own decision that templates are personal, not firm-shared, since Dashboard access is already manager-or-above only with no broader population to share to. The widgets column holds the exact same shape already used everywhere else in this feature (instance_id, type_key, grid_x, grid_y, size, minimized, config), no new object shape. A user can have any number of templates, this is not a one-row-per-user table like DashboardLayout.

CHANGE INSTRUCTIONS:

Add a new model class, DashboardTemplate, to app/models/dashboard_layout.py, following the exact conventions already used for DashboardLayout in that same file: id, user_id as a ForeignKey to users.id with ondelete="CASCADE" and index=True but NOT unique since one user has many templates, name as a String column, widgets as JSONB with default=list, and the standard created_at and updated_at pattern.

Add three endpoints to the existing router in app/api/dashboard.py, all gated require_manager_or_above:
GET /dashboard/templates — returns all of the current user's templates, ordered by created_at descending, most recent first.
POST /dashboard/templates — accepts {name, widgets}, creates a new DashboardTemplate row for the current user, returns the created template including its real id.
DELETE /dashboard/templates/{template_id} — deletes a template, but only if it belongs to the current user, return a 404 if the template_id does not exist or does not belong to the requesting user, do not leak whether a template_id exists for someone else by returning a different error for that case, both cases return the same 404.

Write the migration by hand following the same exact structure as the batch 1 migration, sa.Uuid() column type, ondelete='CASCADE', index creation via op.f().

VERIFY AFTER ACT:

grep -n "class DashboardTemplate" app/models/dashboard_layout.py

grep -n "@router.get(\"/templates\")\|@router.post(\"/templates\")\|@router.delete(\"/templates/{template_id}\")" app/api/dashboard.py

.venv/bin/alembic heads

python3 -c "
import sys
sys.path.insert(0, '/home/corby/jamm-os')
from app.models.dashboard_layout import DashboardTemplate
print('model imports cleanly')
"

cd /home/corby/jamm-os
python3 -c "from app.main import app; print('app imports cleanly')"

alembic heads must show exactly one head, the new migration's revision id. Run .venv/bin/alembic upgrade head and confirm it applies with no errors.

MANUAL VERIFICATION:

Restart the backend. Using a real token as owner@riverside-demo.com, call POST /dashboard/templates with a real name and a small real widgets array (can reuse the current arrangement from GET /dashboard/layout), confirm it returns a real created template with a real id. Call GET /dashboard/templates, confirm the new template appears in the list. Call DELETE /dashboard/templates/{that id}, confirm it succeeds, call GET /dashboard/templates again, confirm it's gone. Try DELETE on a random nonexistent uuid, confirm a real 404, not a 500 or silent success. Report back the real responses from each of these calls.

GIT:

git add -A
git commit -m "add the backend for personal dashboard templates: a new dashboard_templates table, one row per saved template rather than one per user, and GET/POST/DELETE endpoints scoped to the current user's own templates, following the exact widgets JSONB shape and model conventions already established for dashboard_layouts. This is backend only, the mini-grid template planning UI is a separate follow-up task, made feasible by confirming react-grid-layout's real exported createScaledStrategy positionStrategy keeps drag and resize coordinate math correct at reduced scale"
git pull --rebase origin main
git push origin main
git log --oneline -3

Paste the real output of git log --oneline -3 showing the new commit hash present next to origin/main. Do not report this as done based on the push command running, confirm the real log output showing origin/main at the new hash.