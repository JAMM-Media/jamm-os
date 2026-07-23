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

TASK: Redact SSN and EIN patterns from the raw question text before it gets stored in ConciergeQuestionLog

USE: claude sonnet

VERIFY BEFORE ACT:
grep -n "def filter_output" -A 15 /home/corby/jamm-os/app/api/concierge/route.py
grep -n "question_text=last_user_text" /home/corby/jamm-os/app/services/concierge_service.py
grep -n "SSN_PATTERN\|EIN_PATTERN" /home/corby/jamm-os/app/api/concierge/route.py | head -5

Confirm current state matches exactly what is described below before editing.

WHAT IS WRONG:

filter_output correctly redacts SSN and EIN patterns from the model's response before it reaches the firm owner, confirmed working in security testing earlier tonight. However, the raw user question text, last_user_text, gets written directly into ConciergeQuestionLog.question_text with zero filtering applied anywhere in the pipeline. If a firm owner types a real SSN or EIN into a question, expecting it to only be redacted from what comes back to them, that real number is currently being permanently stored in plain text in the review database, readable by anyone with access to the internal question log page.

CHANGE INSTRUCTIONS:

Extract the SSN and EIN redaction logic specifically, not the system prompt leak detection or the trailing parenthetical stripping, which are response-specific and must not run on raw user input, into its own small, standalone function, something like redact_sensitive_patterns(text), defined once and shared. Update filter_output to call this shared function for its own SSN and EIN redaction step, rather than duplicating the regex logic inline.

In concierge_service.py, apply this same shared redaction function to last_user_text before it gets used to build question_text, so a real SSN or EIN typed by a firm owner never reaches the stored log in plain text, even though it is fine for the live, in-conversation model to see it in order to answer the question naturally.

Do not change the existing behavior of filter_output for the response path in any way other than sourcing its SSN and EIN redaction from the newly shared function. Do not apply system prompt leak detection or parenthetical stripping to user input, only the redaction step.

VERIFY AFTER ACT:

grep -n "redact_sensitive_patterns" /home/corby/jamm-os/app/api/concierge/route.py /home/corby/jamm-os/app/services/concierge_service.py

Expected: present in both, confirming the shared function is genuinely shared, not duplicated.

python3 -c "
import sys
sys.path.insert(0, '/home/corby/jamm-os')
from app.api.concierge.route import redact_sensitive_patterns
test = 'Client SSN is 123-45-6789, please note it'
result = redact_sensitive_patterns(test)
print(result)
assert '123-45-6789' not in result, 'SSN was not redacted'
print('PASS')
"

Paste this real output. If redact_sensitive_patterns is defined inside a function scope rather than at module level and cannot be imported this way, adjust the test to whatever real invocation path is correct and explain why, do not skip this verification.

python3 -c "from app.main import app; print('OK')"

MANUAL VERIFICATION:

Restart backend. Type a message containing a fake SSN pattern, such as client SSN is 123-45-6789, can you note that, into the Concierge. Confirm the live response still correctly avoids repeating the SSN, exactly as it did before. Then check the /concierge-log review page directly, find this exact question, and confirm the stored question_text now shows REDACTED in place of the real number, not the real SSN in plain text.

Report pass or fail for both the response behavior and the stored log entry specifically, since both need to be checked, not just one.

GIT:
git add -A
git commit -m "redact SSN and EIN patterns from raw question text before it is stored in ConciergeQuestionLog, closing a real gap where sensitive numbers typed by a firm owner were correctly hidden from the live response but were being permanently stored in plain text in the internal review database, found during external research into financial-data handling expectations for AI assistants in accounting software"
git pull --rebase origin main
git push origin main