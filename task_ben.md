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

TASK: Fix assembleSSELines never handling the [FILTERED] replacement sentinel, causing duplicated garbled output whenever the backend corrects a response

USE: claude sonnet

VERIFY BEFORE ACT:
cat /home/corby/jamm-os/frontend/src/lib/concierge/assembleSSEStream.ts

Confirm this matches exactly what is described below before editing.

WHAT IS WRONG:

The backend, when its leak filter or the OPTIONS safety net changes the final response text after it has already started streaming, sends a specific sequence over SSE: the originally streamed lines, then a blank data line, then a line containing exactly [FILTERED], then the fully corrected final text as new data lines. This is meant to signal the frontend to discard everything shown so far and replace it entirely with what follows. assembleSSELines has no handling for this sentinel at all, it simply concatenates every line in order regardless of content. Confirmed live: a real response showed the original correct bulleted list, followed by the literal visible text [FILTERED], followed by a duplicated repeat of the same content, because the frontend appended everything instead of replacing.

This is not a new bug introduced tonight. This mechanism has existed in the backend for some time and this is simply the first time it happened to fire on a response that got directly observed and reported, meaning any past response where the backend's leak filter changed the final text after streaming began would have shown this same garbled duplication to a real firm owner.

CHANGE INSTRUCTIONS:

In assembleSSELines, before assembling anything, scan the input rawLines array for a data line whose content, after stripping the data: prefix and trimming whitespace, is exactly [FILTERED]. If found, discard every line before and including that marker line, and only assemble the lines that come after it, using the exact same assembly logic already in the function for the remaining lines. If no such marker line exists anywhere in the input, behave exactly as the function already does today, with no change in output.

If the marker appears more than once in the input, use the last occurrence, since that represents the most final, most fully corrected version the backend intended to send.

Do not change how any other part of this function works, only add this discard-and-restart behavior keyed on the marker.

VERIFY AFTER ACT:

Write and run a standalone test directly exercising this function with three cases, and paste the real output, not a summary:

node -e "
const { assembleSSELines } = require('./frontend/src/lib/concierge/assembleSSEStream.ts');
" 

If this cannot run directly due to TypeScript, instead write a small inline test using ts-node or by temporarily compiling, or simply construct the exact three test cases as plain JavaScript logic mirroring the real function and run them with plain node, clearly labeled as a manual equivalence check if the real module cannot be executed directly outside the Next.js build. Whatever approach is used, the three cases to prove are:

Case one: no [FILTERED] line anywhere in the input, confirm output is identical to what the function already produces today, unchanged behavior.
Case two: a [FILTERED] line appears once in the middle of the input, confirm the output contains only the content from after that line, with none of the content from before it present anywhere in the result.
Case three: multiple lines of real content both before and after a single [FILTERED] marker, confirm the assembled output exactly matches only the after-marker lines, correctly rejoined with newlines exactly as the existing assembly logic already does.

npm run build in frontend, expected zero TypeScript errors.

MANUAL VERIFICATION:

Full kill, .next wipe, restart both servers, this touches core message assembly.

Reproduce a response that is known to trigger the backend's leak filter or the OPTIONS safety net replacement path, and confirm the displayed message no longer shows any raw [FILTERED] text or duplicated content, only the single, final, correct version.

Separately, ask several normal questions that should not trigger any filtering at all, confirm they display exactly as they always have, with no regression from this change.

Report pass or fail for the standalone test cases, the filtered-response reproduction, and the normal-response regression check, individually.

GIT:
git add -A
git commit -m "fix assembleSSELines never handling the FILTERED replacement sentinel the backend sends when its leak filter or safety net corrects a response after streaming has already begun, which was causing the original text, the raw marker, and a duplicated corrected version to all display together instead of the frontend cleanly replacing the display with only the final corrected text"
git pull --rebase origin main
git push origin main