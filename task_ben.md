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

TASK: Add missing client-overview keywords to the operational-question gate, fixing get_client_full_snapshot being unreachable for natural client-overview questions

USE: claude sonnet

VERIFY BEFORE ACT:

python3 -c "
import sys
sys.path.insert(0, '/home/corby/jamm-os')
from app.api.concierge.route import _is_operational_question
print(_is_operational_question('Tell me about Robert & Carol Tanner'))
"

sed -n '281,308p' /home/corby/jamm-os/app/api/concierge/route.py

sed -n '139,143p' /home/corby/jamm-os/app/api/concierge/route.py

Confirm this currently prints False, and confirm get_client_full_snapshot is correctly registered inside _CONCIERGE_TOOLS, the main tool list, not the staff-only list, ruling out the tool-list placement mistake found and fixed earlier tonight. This confirms the sole remaining root cause is the operational keyword gate having no awareness of natural client-overview phrasing.

WHAT THIS IS:

Confirmed live tonight, twice, with two different real symptoms that turned out to share one root cause. A live browser audit earlier found that asking "Tell me about Robert & Carol Tanner" produced a response with a wrong filing deadline, off by one day, and a fabricated email address that did not match the real client record. Re-testing live just now, the same question instead produced a stalled non-answer, "Let me pull up the details on Robert & Carol Tanner," with nothing delivered after it. Both symptoms trace to the same cause: _is_operational_question returns False for this phrasing, so the question never enters the tool-use code path and get_client_full_snapshot, which already exists, is already correctly registered, and already returns real, correct, unmodified data straight from the database, is never actually called. With no real data available, the model either stalls or invents plausible-sounding but wrong details, depending on the specific run, which is exactly the same unreliable pattern already proven and fixed for Notes and Firm Chat earlier tonight.

CHANGE INSTRUCTIONS:

Add a new line to the _OPERATIONAL_KEYWORDS set containing real, specific phrases for asking about a named client's overall status, matching the exact existing style, for example "tell me about", "give me an overview", "client overview", "client summary", "client snapshot", "what's going on with", "summarize this client", "pull up their", "pull up this client". Do not remove or change any existing keyword, this is purely an addition.

VERIFY AFTER ACT:

python3 -c "
import sys
sys.path.insert(0, '/home/corby/jamm-os')
from app.api.concierge.route import _is_operational_question
print(_is_operational_question('Tell me about Robert & Carol Tanner'))
print(_is_operational_question('Give me an overview of Marcus and Diana Webb'))
print(_is_operational_question('Which engagements are stalled?'))
"

Expected: all three now print True, including the pre-existing stalled-engagements question, confirming nothing already working was broken.

python3 -c "from app.main import app; print('OK')"

MANUAL VERIFICATION:

Restart the backend.

Ask "Tell me about Robert & Carol Tanner" and report the exact response verbatim. Confirm it now delivers a real, complete answer rather than stalling.

Specifically check the email address and the engagement deadline stated in the response against the real values on the actual client record, confirmed a few minutes ago as rtanner@example.com and the real filing deadline shown on the Engagements page. Confirm both now match exactly, with no fabricated or off-by-one values.

Ask it a second time to confirm the fix is reliable, not just correct once. Report both responses verbatim.

Report pass or fail for each check individually.

GIT:

git add -A

git commit -m "add missing client-overview keywords to the operational-question gate, fixing get_client_full_snapshot being unreachable for natural phrasings like tell me about a client, confirmed as the shared root cause behind two different symptoms found tonight, a stalled non-answer and, separately, a fabricated email address and an off-by-one filing deadline, both occurring because the question never reached the tool-use path and the model had no real data to answer from"

git pull --rebase origin main

git push origin main