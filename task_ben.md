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

TASK: Fix real UI flicker on the Archive page confirmed by Ben: switching any filter causes a visible flash/flicker because isLoading flips to true on every single refetch (client filter, staff switch, search, anything), and confirmed in code the aggregate row is conditionally hidden whenever !isLoading is false, meaning it disappears and reappears on every filter change even though the underlying data from the previous fetch is still sitting in memory the whole time (useFetch never clears data during a refetch). Also fix the real column-count layout shift when toggling to/from All Staff, which changes the table from 8 to 9 columns.

USE: claude sonnet

ENVIRONMENT SANITY CHECK:

pwd

State plainly that no path in this task resolves against /mnt/c/Users or any Windows-side copy.

VERIFY BEFORE ACT:

grep -n -B 10 -A 30 "Aggregate row\|isLoading" "src/app/(app)/archive/page.tsx"

Paste the real output. Confirm every place isLoading currently gates what's shown (the aggregate row, the table body, any skeleton), so the fix covers every real instance, not just the one already found.

WHAT THIS IS:

useFetch never clears data to null during a refetch, it only replaces it once the new result actually arrives, confirmed directly in its real source tonight. This means the old, still-valid data is available the entire time a refetch is in flight, there is no real need to hide anything just because isLoading briefly becomes true. Real fix: distinguish between a genuine first load (no data has ever arrived yet, a real skeleton is appropriate) and a background refetch of an already-loaded page (data already exists, keep showing it, do not hide it, optionally show a subtle in-place loading indicator instead of hiding content).

For the column-shift on toggling All Staff, the table structure changing width abruptly is jarring specifically because it happens with no transition and alongside the full-hide flicker described above, fixing the flicker issue should make this feel significantly less jarring on its own, since the column change will happen once cleanly against otherwise-stable content instead of compounding with a full hide-and-reshow.

CHANGE INSTRUCTIONS:

Change the aggregate row's condition from aggregates && !isLoading to just aggregates, so it stays visible and simply updates in place once new aggregates arrive, never disappearing just because a refetch is in progress.

Find wherever the table body is conditionally replaced with a skeleton based on isLoading, and change that condition to only show the skeleton when there is no data at all yet (the real first load), not on every subsequent refetch where data already exists from before. If a subtle in-place loading cue is wanted for refetches (for example a slight opacity reduction on the existing table while new data loads), that is acceptable and matches common real-world patterns, but do not fully hide or replace already-loaded content with a skeleton again once it has loaded once.

Do not change useFetch itself, it already behaves correctly (never clearing data), this fix belongs entirely in how the Archive page consumes isLoading and data together.

VERIFY AFTER ACT:

cd /home/corby/jamm-os/frontend
npm run build

grep -n "aggregates &&\|isLoading" "src/app/(app)/archive/page.tsx"

git diff --stat

MANUAL VERIFICATION:

Restart the frontend dev server only. Reload /archive, switch between client filters, staff selections, and toggle All Staff on and off several times, confirm the flicker/flash Ben described is genuinely gone or substantially reduced, the aggregate row and table should update smoothly in place rather than disappearing and reappearing. Confirm the very first page load still shows a proper skeleton, this fix should not remove the real first-load skeleton, only the unnecessary repeated ones on every subsequent filter change. Report back with a screenshot and a plain description of whether it now feels smooth.

GIT:

Do not commit until Ben confirms it actually feels smoother in the browser.