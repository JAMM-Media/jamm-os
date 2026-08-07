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

TASK: Replace the native browser time inputs for Start Time and End Time on the Daily timesheet tab with a custom text field that parses common typed time formats directly, since native <input type="time"> forces clunky segment-by-segment interaction (separate hour/minute/AM-PM fields) instead of letting someone just type a time and have it work.

USE: claude sonnet

ENVIRONMENT SANITY CHECK:

pwd

State plainly that no path in this task resolves against /mnt/c/Users or any Windows-side copy.

VERIFY BEFORE ACT:

grep -n -B 10 -A 5 "function calcDuration" "src/app/(app)/timesheets/DailyTab.tsx"

grep -n "roundToNearest15" "src/app/(app)/timesheets/DailyTab.tsx"

Paste the real output of both. Confirm the exact real "HH:mm" string format calcDuration and the rest of this form actually expect, and confirm the real roundToNearest15 helper's signature, since the new component needs to produce output in the identical format these existing functions already consume, not a new format that would need every downstream consumer changed too.

WHAT THIS IS:

form.startTime and form.endTime are plain "HH:mm" 24-hour strings today, produced by the native time input. This task only changes how that same string gets entered, not what it is or how anything else in this file uses it. A new small component takes free-text input like "10am", "10:00 AM", "3pm", "1500", "15:00", parses it on blur or Enter into the same "HH:mm" format, and calls the exact same onChange the native input currently calls. If what's typed can't be parsed as a real time, show a clear inline error rather than silently accepting garbage or crashing.

CHANGE INSTRUCTIONS:

Create a small reusable component, for example TimeTextInput, in a sensible location near DailyTab.tsx or in a shared components folder if this codebase already has a convention for small shared form inputs, check for one before deciding where it lives. It should render a plain text input, hold its own local typed-text state distinct from the committed "HH:mm" value, and on blur or Enter, attempt to parse the typed text. Support at minimum: "h:mma", "h:mm a", "ha", "h a", "HH:mm" 24-hour, and bare hour shorthand like "3pm" or "1500". If parsing succeeds, call the passed-in onChange with the real "HH:mm" value and update the displayed text to a clean, consistent format like "3:00 PM". If parsing fails, keep the invalid text visible and show a small inline error, do not silently clear it or fall back to a default time.

Replace both the Start Time and End Time native <input type="time"> elements with this new component, passing the same value and onChange props they already receive, so calcDuration, the payload sent to POST /time-entries/, and the timer-start flow all continue working unchanged, since they only care about the final "HH:mm" string, not how it was entered.

VERIFY AFTER ACT:

cd /home/corby/jamm-os/frontend
npm run build

grep -n "TimeTextInput" "src/app/(app)/timesheets/DailyTab.tsx"

git diff --stat

MANUAL VERIFICATION:

Restart the frontend dev server only. Reload Timesheets, Daily tab. Type "10am" into Start Time, tab or click away, confirm it becomes a clean "10:00 AM" and the underlying value is correct. Try "3:15pm", "1500", and "9" alone, confirm each parses sensibly or shows a clear error if genuinely ambiguous. Confirm the duration calculation between start and end still works correctly once both are set. Submit a real entry with times entered this way, confirm it saves correctly. Report back with a screenshot and confirm which input formats worked and which, if any, showed an error.

GIT:

Do not commit until Ben confirms the typed time entry actually feels right and works correctly in the browser.