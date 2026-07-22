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

TASK: Fix staff workload classifier gap that produced a fully fabricated employee identity

USE: claude sonnet

VERIFY BEFORE ACT:
grep -n "\"staff\", \"team\", \"invite\"" -A 3 /home/corby/jamm-os/app/api/concierge/route.py

Confirm the current staff-related operational keywords match what is described below before editing.

WHAT IS WRONG:

Confirmed live via backend logs showing zero tool executions for the entire turn: the question which employee is being used the most never entered the tool-use loop at all, since the word employee does not appear anywhere in _OPERATIONAL_KEYWORDS, only staff and staff member, and the phrase used the most does not match capacity, overloaded, bandwidth, or workload. With no tool available, the model fully fabricated a nonexistent person, Sarah Mitchell, along with a specific fake engagement count and specific fake hours logged, contradicting the real staff roster and contradicting the real 0 hours logged confirmed by get_staff_capacity in every other test tonight. This is the third confirmed instance of this same root cause tonight, a real tool exists but a keyword based classifier gate misses a common real phrasing and silently routes the question to a path with zero tool access, and it is the most serious instance since it produced a fully invented identity rather than an honest deflection.

CHANGE INSTRUCTIONS:

Add employee and employees as additional keywords alongside the existing staff and staff member entries in the operational keyword set. Also add common real phrasings for this same underlying question that do not currently match anything, such as used the most, busiest, most work, most hours, underutilized, most engagements.

VERIFY AFTER ACT:

python3 -c "
import sys
sys.path.insert(0, '/home/corby/jamm-os')
from app.api.concierge.route import _is_operational_question
tests = [
    'Which employee is being used the most?',
    'Who is the busiest right now?',
    'Which staff member has the lightest workload?',
]
for t in tests:
    print(t, '->', _is_operational_question(t))
"

Expected: all three print True. Paste this real output.

python3 -c "from app.main import app; print('OK')"

MANUAL VERIFICATION:

Restart backend, keep terminal visible filtered for Tool executed.

Ask which employee is being used the most, confirm get_staff_capacity now fires and the response contains only real staff names from the actual roster, James Okafor, Priya Mehta, Tom Reyes, Test Run, Sarah Chen, never an invented name, and never a number not actually returned by the tool.

Ask at least two more differently worded versions of the same underlying question, such as who is the busiest right now and which staff member has the most work, confirm both also correctly trigger the tool and return only real data.

Report pass or fail for the original failing question and both rephrased versions, individually, including the exact tool name confirmed in the log for each.

GIT:
git add -A
git commit -m "fix staff workload classifier gap where employee and used the most did not match any operational keyword, causing the question to bypass the tool-use loop entirely and resulting in a fully fabricated nonexistent staff member with invented engagement and hour counts, the third confirmed instance of this same keyword gap root cause tonight and the most serious since it produced an invented identity rather than an honest deflection"
git pull --rebase origin main
git push origin main