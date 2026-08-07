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

TASK: Three fixes to the Archive page's star column, now that the real cause of the "glitchy" star behavior is confirmed: it was never a bug in most cases, it was the owner correctly getting rejected for trying to star entries in someone else's archive (working as designed per spec, starring belongs to whoever the work is assigned to, not the viewer), just failing completely silently with no explanation. Alongside that, two real independent bugs were also found directly in the code and need fixing regardless.

USE: claude sonnet

ENVIRONMENT SANITY CHECK:

pwd

State plainly that no path in this task resolves against /mnt/c/Users or any Windows-side copy.

VERIFY BEFORE ACT:

grep -n -B 5 -A 25 "const handleStarToggle" "src/app/(app)/archive/page.tsx"

grep -n -B 5 -A 20 "{/\* Star \*/}" "src/app/(app)/archive/page.tsx"

grep -n "toast\." "src/app/(app)/archive/page.tsx" | head -5

Paste the real output of all three. Confirm the current handleStarToggle logic, the current star button JSX, and confirm whether toast is already imported and used elsewhere in this file for the error-message pattern to match.

WHAT THIS IS:

Fix 1, real bug: starredOverrides[entry.task_id] never gets cleared once set, permanently shadowing entry.starred after the first toggle for that row, causing a real, permanent divergence from server truth.

Fix 2, real bug: handleStarToggle calls refetch() unconditionally after every successful toggle, even though the optimistic update already correctly reflects the new state, causing an unnecessary full data reswap and the visual row-shift Ben described.

Fix 3, real UX gap, not a permission bug: when the current user is viewing an archive that is not their own (the selected user in the manager/owner staff-picker differs from the logged-in user's own id), every star in that archive is not actually toggleable, since starring is scoped to whoever the task is assigned to, confirmed correct and intentional per spec section 7's "anyone can star rows in their own archive" and section 3's employee-owned-evidence framing constraint. Right now the star renders as if fully clickable regardless, and a click silently fails with a 403 the UI never surfaces, which reads as a random, unexplained glitch. The star should render visibly disabled (greyed out, not the normal amber/gray toggle colors) with a tooltip explaining why, whenever the archive being viewed does not belong to the current logged-in user, and clicking it in that state should do nothing at all, not attempt the API call.

CHANGE INSTRUCTIONS:

Remove the refetch() call from handleStarToggle's success path entirely.

Do not clear starredOverrides after a successful toggle, let it remain the source of truth for that row going forward within the session, since there is no longer an automatic refetch to reconcile against; this is correct because it will already hold the accurate, current value.

Ensure the toggle direction is computed from the latest state at click time using the functional form of setState, not a value captured in a stale closure, so rapid or repeated clicks each correctly compute their own direction.

Determine whether the currently viewed archive belongs to the logged-in user (compare the archive's target user_id, whatever that variable is called in this file, against the logged-in user's own id from useAuth). When it does not match, render the star button with a disabled/muted style (grey, not the normal amber-filled or outline-gray toggle colors), a title/tooltip attribute explaining "You can only star items in your own archive," and make its onClick a no-op or simply omit the onClick handler entirely in that state, so no API call is attempted at all, not just prevented server-side.

Add a toast.error call in handleStarToggle's catch block, using the exact same toast pattern already used elsewhere in this codebase, surfacing whatever real detail message the API returns (for example the confirmed real "You may only star tasks assigned to you." message) rather than failing with no visible feedback, this is a real safety net for any other unexpected failure beyond the now-prevented case above.

VERIFY AFTER ACT:

cd /home/corby/jamm-os/frontend
npm run build

grep -n -A 20 "const handleStarToggle" "src/app/(app)/archive/page.tsx"

grep -n "toast.error" "src/app/(app)/archive/page.tsx"

git diff --stat

MANUAL VERIFICATION:

Restart the frontend dev server only. Reload /archive as owner@riverside-demo.com viewing your own archive if you have any real starrable rows, confirm star/unstar toggles cleanly with no row-shift and no stuck state, and persists correctly after a full page reload. Switch to viewing a different user's archive via the staff selector, confirm every star in that view now renders visibly greyed/disabled with a tooltip, and confirm clicking one does nothing, no network request fires at all. Report back with a screenshot of both states, your own archive's active stars and someone else's archive's disabled stars.

GIT:

Do not commit until Ben confirms both states look and behave correctly in the browser.