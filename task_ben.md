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

TASK: Fix the three highest-priority skeleton gaps identified in tonight's full audit's B classification — clients/[id], engagements/[id], and tasks/[id]. All three currently skeleton only their page header (breadcrumb/title/meta) while the actual body content — tabs, lists, panels — pops in blank once data resolves. This produces a jarring half-loaded feel since the header looks ready before the body is.

USE: claude sonnet

ENVIRONMENT SANITY CHECK:

pwd

State plainly that no path in this task resolves against /mnt/c/Users or any Windows-side copy.

VERIFY BEFORE ACT:

cat "src/app/(app)/dashboard/page.tsx" | grep -n "Skeleton" -A 8

Reference standard: named, content-shaped skeleton components using surface-border/dark-border tokens and animate-pulse, matching real content layout.

Then view each of the three target files in full:

cat "src/app/(app)/clients/[id]/page.tsx"
cat "src/app/(app)/engagements/[id]/page.tsx"
cat "src/app/(app)/tasks/[id]/page.tsx"

Confirm each currently has a small header-only skeleton (2-4 animate-pulse divs for breadcrumb/title/meta) and that the tab/body content below renders nothing or pops in abruptly once its own data resolves. Identify the real tab structure and body layout for each page (what tabs exist, what each tab's content looks like once loaded) before writing any skeleton, since the skeleton must match real content, not be invented.

If any file's structure doesn't match this description, stop and report the actual content instead of proceeding on that file.

CHANGE INSTRUCTIONS:

For each of the three files, extend the existing header skeleton to also cover the body/tab content area during the loading state:

1. clients/[id]/page.tsx — build a skeleton for the default/first tab's real content shape (read the file to determine what actually renders — likely contact info fields, associated engagements list, or similar). Named descriptively (e.g. ClientDetailBodySkeleton).

2. engagements/[id]/page.tsx — build a skeleton for the default/first tab's real content shape (likely task list, document requests, or similar — read the file to confirm). Named descriptively (e.g. EngagementDetailBodySkeleton).

3. tasks/[id]/page.tsx — build a skeleton for the real body content shape (likely task details, comments/activity, or similar — read the file to confirm). Named descriptively (e.g. TaskDetailBodySkeleton).

Each skeleton should follow the dashboard reference pattern: sized/colored placeholder divs matching the real content's actual layout (field rows, list items, card shapes), not generic boxes. Wire each in to show during the same loading condition that currently gates the header skeleton, so header and body skeletons appear and disappear together.

Do not touch the existing header skeletons themselves, only add body coverage. Do not touch any other file — this task is scoped to these three only.

VERIFY AFTER ACT:

grep -n "Skeleton" "src/app/(app)/clients/[id]/page.tsx"
grep -n "Skeleton" "src/app/(app)/engagements/[id]/page.tsx"
grep -n "Skeleton" "src/app/(app)/tasks/[id]/page.tsx"

Confirm each file now has both its original header skeleton and a new body skeleton component.

git diff --stat

Confirm the diff touches only these three files.

MANUAL VERIFICATION:

Ben will run npm run build himself in the frontend directory and confirm it's clean before trusting this as done.

**Restart the frontend.** With network throttled in devtools, visit a real client detail page, a real engagement detail page, and a real task detail page. Confirm the body content area now shows a real, shaped skeleton during load instead of popping in blank after the header skeleton disappears. Report back plainly, page by page.

GIT:

Do not commit until Ben confirms in the browser.