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

TASK: Add a "Save as Firm Default" action to Edit Dashboard mode, visible only to firm owners, that persists the current in-session arrangement as the firm-wide default new managers get seeded with. The backend endpoint (PUT /dashboard/firm-default-layout, gated require_firm_owner) already exists and has never been wired to any frontend action.

USE: claude sonnet

ENVIRONMENT SANITY CHECK:

pwd

State plainly that no path in this task resolves against /mnt/c/Users or any Windows-side copy.

VERIFY BEFORE ACT:

grep -n -B 3 -A 15 "@router.put(\"/firm-default-layout\")" app/api/dashboard.py

grep -n "useAuth" "src/app/(app)/dashboard/page.tsx"

grep -n -B 2 -A 10 "Reset to Default\|handleResetToDefault" "src/app/(app)/dashboard/page.tsx"

Paste the real output of all three. Confirm the exact real request body shape PUT /firm-default-layout expects, confirm whether useAuth is already imported in the dashboard page or needs adding, and confirm the real Reset to Default implementation from earlier tonight so this new action follows the same established pattern rather than inventing a new one.

WHAT THIS IS:

This action is meaningfully different from Done, which saves the current user's own personal layout, and from Reset to Default, which loads a default into the edit session without persisting anything on its own. Save as Firm Default writes directly to the firm-wide default via a dedicated endpoint, separate from the user's own DashboardLayout row entirely. Unlike Reset to Default and every other edit-mode action, this one is not something Cancel can undo once clicked, since it is a direct write to a shared firm record the moment it is clicked, not a change to the local edit session, this needs its own explicit confirmation dialog making that plain, using the same useConfirm pattern already used for Reset to Default's confirmation.

This action does not exit edit mode or affect the current user's own personal Done/Cancel flow at all. Someone can click Save as Firm Default and then still separately click Done or Cancel for their own personal layout exactly as before, these are two independent things happening to two independent records.

CHANGE INSTRUCTIONS:

Add a putFirmDefaultLayout method to frontend/src/lib/api/dashboard.ts calling PUT /dashboard/firm-default-layout with the real confirmed request body shape.

In the dashboard page, get the current user's role from useAuth (import it if not already present). Add a "Save as Firm Default" button in the edit-mode toolbar, visible only when the current user's role is firm_owner, styled as a secondary/lighter action similar to Reset to Default rather than a primary button, since this is an infrequent administrative action, not a routine one.

Clicking it opens a confirm dialog using the existing useConfirm pattern, with a message plainly stating this immediately sets the firm-wide default for new managers and cannot be undone with Cancel the way other edit-mode changes can. On confirmation, call putFirmDefaultLayout with the current editedWidgets array (the in-session arrangement, whatever the owner has currently arranged, whether or not they've clicked Done for their own personal layout yet), show a toast or equivalent success confirmation using whatever success-notification pattern already exists elsewhere in this file or the app (check for an existing toast/sonner usage before adding a new one), and remain in edit mode afterward exactly as before, not exiting or resetting anything else.

VERIFY AFTER ACT:

cd /home/corby/jamm-os/frontend
npm run build

grep -n "Save as Firm Default\|putFirmDefaultLayout\|firm_owner" "src/app/(app)/dashboard/page.tsx"

git diff --stat

MANUAL VERIFICATION:

Restart the frontend dev server only, no backend changes were made. Reload /dashboard as owner@riverside-demo.com, enter Edit Dashboard, confirm Save as Firm Default is visible. Log in instead as a manager-role test account if one exists, enter Edit Dashboard, confirm the button does not appear at all for a non-owner. Back as the owner, arrange the dashboard into something recognizable, click Save as Firm Default, confirm the dialog appears with clear undo-warning language, confirm it, confirm a success indicator appears and edit mode stays active. Verify the real result by calling GET /dashboard/reset directly (via curl or /docs) and confirming the returned widgets now match what was just saved, not the old system default. Report back with a screenshot and the real API response.

GIT:

git add -A
git commit -m "add Save as Firm Default to Edit Dashboard mode, visible only to firm owners, wiring the PUT /dashboard/firm-default-layout endpoint that has existed since batch 1 but was never connected to any frontend action. This is a direct, immediate write to the shared firm-wide default, not undoable via Cancel like every other edit-mode action, so it uses its own explicit confirmation dialog stating that plainly. Independent of the current user's own personal Done/Cancel flow, both can be used separately in the same edit session"
git pull --rebase origin main
git push origin main
git log --oneline -3

Paste the real output of git log --oneline -3 showing the new commit hash present next to origin/main. Do not report this as done based on the push command running, confirm the real log output showing origin/main at the new hash.