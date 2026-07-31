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

TASK: Add the missing Notes and Firm Chat keywords to the operational-question gate, fixing the new tools being unreachable despite being correctly built and registered

USE: claude sonnet

VERIFY BEFORE ACT:

grep -n "\"note\"\|\"notes\"\|\"firm chat\"\|\"channel\"" /home/corby/jamm-os/app/api/concierge/route.py

sed -n '281,308p' /home/corby/jamm-os/app/api/concierge/route.py

python3 -c "
import sys
sys.path.insert(0, '/home/corby/jamm-os')
from app.api.concierge.route import _is_operational_question
print(_is_operational_question(\"What's in the notes for Robert & Carol Tanner?\"))
print(_is_operational_question(\"Has anyone written any client notes recently?\"))
print(_is_operational_question(\"What's been said in Firm Chat today?\"))
print(_is_operational_question(\"Summarize the most recent Firm Chat messages\"))
"

Confirm all four print False, and confirm zero note or firm chat related terms currently exist anywhere in _OPERATIONAL_KEYWORDS, before editing. This confirms the exact root cause: get_recent_notes and get_recent_firm_chat_activity were correctly built and registered as real tools earlier tonight, but every one of the four real questions used to test them never reaches the tool-use code path at all, because _is_operational_question gates entry to that path and has no awareness these topics exist, so the model falls back to a plain conversational response with zero tools available, honestly reporting it has no tool access, which is true for that fallback path even though the real tools do exist in the other one.

CHANGE INSTRUCTIONS:

Add a new line to the _OPERATIONAL_KEYWORDS set containing real, specific terms for these two topics, matching the exact existing style, comma-separated short phrases in quotes, for example "note", "notes", "client note", "client notes", "firm chat", "firm-chat", "team chat", "internal chat", "channel", "chat messages". Do not remove or change any existing keyword in this set, this is purely an addition.

VERIFY AFTER ACT:

python3 -c "
import sys
sys.path.insert(0, '/home/corby/jamm-os')
from app.api.concierge.route import _is_operational_question
print(_is_operational_question(\"What's in the notes for Robert & Carol Tanner?\"))
print(_is_operational_question(\"Has anyone written any client notes recently?\"))
print(_is_operational_question(\"What's been said in Firm Chat today?\"))
print(_is_operational_question(\"Summarize the most recent Firm Chat messages\"))
print(_is_operational_question(\"Which engagements are stalled?\"))
"

Expected: the first four now print True, and the fifth, an existing, already-working question, still prints True, confirming the addition did not break anything already working.

python3 -c "from app.main import app; print('OK')"

MANUAL VERIFICATION:

Restart the backend.

Re-ask the exact same four questions from tonight's audit, one at a time, and report each response verbatim:
"What's in the notes for Robert & Carol Tanner?"
"Has anyone written any client notes recently?"
"What's been said in Firm Chat today?"
"Summarize the most recent Firm Chat messages"

Real test data already exists for this check: a real note on Robert & Carol Tanner, and a real Firm Chat message in a channel called general. Confirm the first two questions now return real, accurate answers referencing this real note. Confirm the last two questions now return real, accurate answers referencing the real Firm Chat message, and no longer deny that Firm Chat exists as a feature.

Report pass or fail for each of the four questions individually, quoting the actual response text.

GIT:

git add -A

git commit -m "add the missing Notes and Firm Chat keywords to the operational-question gate, fixing the two new tools built earlier tonight, get_recent_notes and get_recent_firm_chat_activity, being completely unreachable because _is_operational_question had no awareness these topics exist, causing every real question about them to fall back to a plain conversational path with zero tools available, confirmed as the exact root cause by directly testing the classifier function against all four of tonight's audit questions before and after this change"

git pull --rebase origin main

git push origin main