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

TASK: Fix document status question classifier gap and add a firm-wide outstanding document requests tool

USE: claude sonnet

VERIFY BEFORE ACT:
grep -n "\"document status\", \"uploaded\", \"missing documents\"" /home/corby/jamm-os/app/api/concierge/route.py
grep -n "def get_client_document_status" -A 30 /home/corby/jamm-os/app/api/concierge/functions.py
grep -n "def get_stalled_engagements" -A 15 /home/corby/jamm-os/app/api/concierge/functions.py

Confirm the current operational keyword line, the existing single-client tool, and read one existing firm-wide aggregate tool such as get_stalled_engagements to match its exact structure and return shape before writing anything.

WHAT IS WRONG:

Two separate, confirmed gaps. First, the question what documents is Goldstein Family Trust still missing failed to enter the tool-use loop at all, confirmed live, the model responded that it had no tool available despite get_client_document_status being correctly registered and wired. The operational keyword set only contains the exact phrase missing documents, not the reversed word order still missing used in the real question, so the classifier never routed this question to the tool-use path in the first place. Second, even when correctly routed, get_client_document_status requires a specific client_id and can only ever answer for one already-named client. There is no way currently to answer the broader question which clients firm wide have outstanding document requests, which is the actual capability this domain is supposed to have per the standards document.

CHANGE INSTRUCTIONS:

In _OPERATIONAL_KEYWORDS, add additional phrasings covering common real ways this question gets asked, such as still missing, what's missing, still need, still needs, hasn't uploaded, haven't uploaded, outstanding documents, missing paperwork. Do not remove the existing missing documents entry.

In functions.py, add a new function, get_outstanding_document_requests, firm scoped, matching the exact pattern and docstring style of get_stalled_engagements. It should query DocumentRequest where status is in pending or partial, firm wide, not scoped to one client, joined to Client for the client name and Engagement for the engagement title, returning each outstanding request's client name, engagement title, request title, status, and due date if set. Order by due date ascending with nulls last, matching the pattern already used elsewhere in this file for similar deadline-oriented lists.

Register this new tool in _CONCIERGE_TOOLS in route.py with a clear description distinguishing it from get_client_document_status, explicitly stating this one is for firm-wide questions about which clients have outstanding requests, while the existing tool remains for questions about one specific, already-named client's document status.

Do not modify get_client_document_status itself, it is correctly scoped for its own purpose and should remain unchanged.

VERIFY AFTER ACT:

grep -n "get_outstanding_document_requests" /home/corby/jamm-os/app/api/concierge/functions.py /home/corby/jamm-os/app/api/concierge/route.py

Expected: present in both files, properly registered.

python3 -c "from app.main import app; print('OK')"

MANUAL VERIFICATION:

Restart backend, keep terminal visible filtered for Tool executed.

Ask what documents is Goldstein Family Trust still missing, confirm this now correctly triggers get_client_document_status, not a deflection.

Ask which clients have outstanding document requests, confirm this now correctly triggers the new get_outstanding_document_requests tool and returns real, specific results, not a deflection to navigate manually.

Report pass or fail individually for both questions, including which tool name appears in the log for each.

GIT:
git add -A
git commit -m "fix document status question classifier gap where still missing did not match the existing missing documents keyword, and add get_outstanding_document_requests for firm-wide questions, closing the gap where only a single already-named client's document status could be answered"
git pull --rebase origin main
git push origin main