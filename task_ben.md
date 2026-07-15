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

TASK: Prevent the model from answering live-data questions from memory instead of a fresh tool call

USE: claude sonnet

VERIFY BEFORE ACT:
grep -n "_CONCIERGE_TOOLS\s*=" /home/corby/jamm-os/app/api/concierge/route.py
grep -n "SCOPE\|live data\|always call" /home/corby/jamm-os/app/api/concierge/prompts.py | head -20

Confirm current state before editing. Read the full system prompt section governing tool use and live data in full.

WHAT IS WRONG:

Confirmed live via backend logs: when the same live-data question was asked a fourth time within the same conversation, having already been asked and correctly answered three times before, the model did not call get_overdue_invoices at all this turn, captured_tools was empty. It answered directly from its own memory of the earlier turns in the conversation instead of re-querying live data. This caused the OPTIONS safety net to correctly find nothing to attach to, since no tool was actually called, but the underlying issue is more serious than the missing marker: the model treating a repeated question as not requiring a fresh data lookup is a real staleness risk, directly contradicting the core standard that the agent must always know the real, current, live answer, not a remembered one from earlier in the same conversation. If the underlying data had genuinely changed between the first and fourth ask, this same behavior would have produced a confidently wrong answer instead of just a missing marker.

CHANGE INSTRUCTIONS:

Add an explicit, absolute instruction to the system prompt, in the section governing tool use and live data: whenever a question requires live firm data, the relevant tool must be called fresh every single time that question is asked, even if the exact same question was already asked and answered earlier in the same conversation. Never answer a live data question using only a remembered result from an earlier turn. State plainly that conversation history is for context and continuity, not a substitute for a fresh data lookup, and that a firm owner asking the same question twice may legitimately be checking whether anything has changed since they last asked, which a memory based answer would silently fail to reflect.

VERIFY AFTER ACT:

grep -n "fresh every single time\|Never answer a live data question" /home/corby/jamm-os/app/api/concierge/prompts.py

Expected: present.

python3 -c "from app.main import app; print('OK')"

MANUAL VERIFICATION:

Restart backend, keep terminal visible filtered for OPTIONS SAFETY NET and tool execution logs. In a single fresh conversation, ask which clients have overdue invoices right now at least six times in a row, spaced normally. For every single attempt, confirm in the backend log that get_overdue_invoices was actually called that turn, not skipped, and confirm the OPTIONS marker and clickable buttons are present every time as a result.

Report the tool-call confirmation and marker presence individually for all six attempts, not a general impression.

GIT:
git add -A
git commit -m "require the model to always call live data tools fresh for every question requiring live data, even when the same question was already asked earlier in the same conversation, since answering from memory instead of a fresh lookup was causing the OPTIONS safety net to have no fresh tool result to work with and is a real staleness risk independent of that specific symptom"
git pull --rebase origin main
git push origin main