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

TASK: Fix billing questions misclassifying as engagements when the word engagement appears alongside financial language

USE: claude sonnet

VERIFY BEFORE ACT:
grep -n "\"billing\": {" -A 8 /home/corby/jamm-os/app/api/concierge/route.py

python3 -c "
import sys
sys.path.insert(0, '/home/corby/jamm-os')
from app.api.concierge.route import _classify_topic
print(_classify_topic(\"What's Marcus & Diana Webb's outstanding balance from last year's engagement?\"))
"

Confirm this currently prints engagements, not billing, before editing.

WHAT IS WRONG:

Confirmed live: a genuinely financial question, asking about an outstanding balance, classifies as the engagements topic instead of billing, because the word engagement is present and scores in that bucket while the billing bucket's keyword set does not contain balance or outstanding balance, so the engagements bucket wins the scoring even though the question is fundamentally about money owed. This produces a Go to Engagements chip on an invoice focused answer, the same wrong-destination pattern already found and fixed for other topics earlier tonight.

CHANGE INSTRUCTIONS:

Add balance and outstanding balance to the billing topic keyword set, matching the exact existing style and format of that set. Do not remove or change anything in the engagements keyword set, and do not change the underlying scoring logic itself, this is purely a missing keyword in one bucket.

VERIFY AFTER ACT:

python3 -c "
import sys
sys.path.insert(0, '/home/corby/jamm-os')
from app.api.concierge.route import _classify_topic
print(_classify_topic(\"What's Marcus & Diana Webb's outstanding balance from last year's engagement?\"))
print(_classify_topic('Which engagements are stalled right now?'))
"

Expected: the first line now prints billing, the second line still prints engagements, confirming the fix is targeted and did not break the legitimate engagements case.

MANUAL VERIFICATION:

Restart backend. Ask what's Marcus and Diana Webb's outstanding balance from last year's engagement again, confirm the chip now correctly reads Go to Billing.

GIT:
git add -A
git commit -m "add balance and outstanding balance to the billing topic keyword set, fixing questions about money owed misclassifying as engagements when the word engagement also appears, which was producing a Go to Engagements chip on answers that were fundamentally about invoices"
git pull --rebase origin main
git push origin main