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

TASK: Move get_recent_notes and get_recent_firm_chat_activity from the staff-only tool list to the main tool list, fixing them being unreachable for owner and manager accounts

USE: claude sonnet

VERIFY BEFORE ACT:

sed -n '245,280p' /home/corby/jamm-os/app/api/concierge/route.py

grep -n "_active_tools = _STAFF_CONCIERGE_TOOLS\|_active_tools = _CONCIERGE_TOOLS" /home/corby/jamm-os/app/api/concierge/route.py

Confirm get_recent_notes and get_recent_firm_chat_activity are currently defined inside _STAFF_CONCIERGE_TOOLS, immediately after get_my_tasks, and confirm _active_tools is only ever set to _STAFF_CONCIERGE_TOOLS for the staff role, with owner and manager roles receiving _CONCIERGE_TOOLS instead. This confirms these two tools are currently completely unreachable for owner and manager accounts, which is exactly the account type used to test them live tonight, explaining why the model consistently and honestly reported having no access despite the tools being correctly built and the operational keyword gate already being fixed.

WHAT THIS IS:

A mistake made earlier tonight when these two tools were first built: the task instructions said to add them to the tools list without naming which of the two real, separate tool lists in this file, and they were added to the wrong one, _STAFF_CONCIERGE_TOOLS, the narrow, deliberately restricted subset built earlier this session for security reasons, rather than _CONCIERGE_TOOLS, the full list used by owner and manager accounts. This was only caught because live testing tonight, as an owner account, still failed after the operational keyword fix, which led to checking every layer between question classification and the actual tool list sent to the model.

CHANGE INSTRUCTIONS:

Move the get_recent_notes and get_recent_firm_chat_activity tool schema entries out of _STAFF_CONCIERGE_TOOLS and into _CONCIERGE_TOOLS, placed anywhere reasonable among the other entries there, for example near get_stalled_engagements. After moving them, _STAFF_CONCIERGE_TOOLS should contain only get_my_tasks, exactly as it did before these two tools were first added earlier tonight. Do not duplicate the entries into both lists, this is a move, not a copy, staff accounts should not gain access to these two tools as part of this fix, that would be a separate, deliberate decision, not an accidental side effect of correcting this mistake.

VERIFY AFTER ACT:

grep -n "get_recent_notes\|get_recent_firm_chat_activity" /home/corby/jamm-os/app/api/concierge/route.py

python3 -c "
import sys
sys.path.insert(0, '/home/corby/jamm-os')
from app.api.concierge.route import _CONCIERGE_TOOLS, _STAFF_CONCIERGE_TOOLS
concierge_names = [t['name'] for t in _CONCIERGE_TOOLS]
staff_names = [t['name'] for t in _STAFF_CONCIERGE_TOOLS]
print('in main list:', 'get_recent_notes' in concierge_names, 'get_recent_firm_chat_activity' in concierge_names)
print('in staff list:', 'get_recent_notes' in staff_names, 'get_recent_firm_chat_activity' in staff_names)
print('staff list contents:', staff_names)
"

Expected: both tools show True for being in the main list, False for being in the staff list, and the staff list contents show only get_my_tasks.

python3 -c "from app.main import app; print('OK')"

MANUAL VERIFICATION:

Restart the backend.

Re-ask the exact same four questions from tonight's audit, one at a time, logged in as the firm owner, and report each response verbatim:
"What's in the notes for Robert & Carol Tanner?"
"Has anyone written any client notes recently?"
"What's been said in Firm Chat today?"
"Summarize the most recent Firm Chat messages"

Real test data still exists, a real note on Robert & Carol Tanner and a real Firm Chat message in the general channel. Confirm all four now return real, accurate answers referencing this real data, and none of them deny access or claim the tool does not exist.

Report pass or fail for each of the four questions individually, quoting the actual response text.

GIT:

git add -A

git commit -m "move get_recent_notes and get_recent_firm_chat_activity from the staff-only tool list to the main tool list, fixing a mistake made when these tools were first built tonight where ambiguous task instructions led to them being added to the wrong of two separate tool lists in this file, making them completely unreachable for owner and manager accounts, the exact account type used to test them live, and confirmed as the real remaining root cause after the operational keyword gate fix alone did not resolve the live failures"

git pull --rebase origin main

git push origin main