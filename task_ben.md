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

TASK: Pin tool-use loop to claude-sonnet-5 permanently, based on measured timing evidence, not as a temporary stopgap

USE: claude sonnet

VERIFY BEFORE ACT:
grep -n "model=\"claude-fable-5\"" /home/corby/jamm-os/app/api/concierge/route.py

Confirm the current model reference and its exact line number before editing.

WHAT THIS IS:

Earlier tonight the tool-use loop was reverted from a temporary claude-sonnet-5 substitution back to claude-fable-5, since the export control suspension that necessitated that substitution had been lifted. Direct timing evidence was then measured for the same question, which clients have overdue invoices right now, on both models using identical backend log timestamps. On claude-sonnet-5, the full round trip measured approximately 4.0 seconds. On claude-fable-5, the identical question measured approximately 8.8 seconds, roughly double. Both models produced correct, complete answers, this is a pure speed difference, not a correctness difference. This matches Anthropic's own guidance that claude-fable-5 is built for long, complex, autonomous work, while a short, well-scoped single question is equally good and meaningfully faster and cheaper on claude-sonnet-5.

CHANGE INSTRUCTIONS:

Change the model parameter in the tool-use loop from claude-fable-5 to claude-sonnet-5. Add a short comment directly above it explaining this is a deliberate, permanent choice based on measured timing evidence, not a temporary substitution awaiting reversion, so a future reader does not mistake this for another TEMP style stopgap and revert it without checking. State plainly in the comment that claude-fable-5 was measured to take roughly double the time for the same real question with no accuracy benefit for this specific use case, a single focused chat response rather than long autonomous work.

Do not change any other model reference in this file.

VERIFY AFTER ACT:

grep -n "claude-sonnet-5\|claude-fable-5" /home/corby/jamm-os/app/api/concierge/route.py

Expected: claude-sonnet-5 present with the new explanatory comment above it, claude-fable-5 no longer present anywhere in the file.

python3 -c "from app.main import app; print('OK')"

MANUAL VERIFICATION:

Restart backend. Ask which clients have overdue invoices right now, confirm it still works correctly end to end, tool_choice forcing still fires, OPTIONS safety net and buttons still work.

GIT:
git add -A
git commit -m "pin tool-use loop to claude-sonnet-5 as a permanent, deliberate choice based on measured timing evidence showing claude-fable-5 takes roughly double the time for the same real question with no correctness benefit for this single-question use case"
git pull --rebase origin main
git push origin main