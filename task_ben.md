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

TASK: Extend get_portal_inactive_clients with real firm-wide portal enablement and login statistics

USE: claude sonnet

VERIFY BEFORE ACT:
grep -n "portal_access_enabled\|portal_last_login_at" /home/corby/jamm-os/app/models/client.py
grep -n "def get_portal_inactive_clients" -A 55 /home/corby/jamm-os/app/api/concierge/functions.py

Confirm the real fields exist as described and read the full current function before editing.

WHAT THIS IS:

Confirmed live, twice, with per-tool-call logging proving no second tool was ever called: the model was volunteering specific portal enablement and firm-wide login statistics, such as 3 of 27 clients have portal access enabled and 0 of 27 have ever logged in, with zero real data behind those numbers, since get_portal_inactive_clients does not compute or return anything like this. A prompt-only prohibition against fabricating numbers was already added and did not stop this from recurring identically on the next live test. Rather than attempt a third prompt rewrite, the actual fix is giving the model genuine data to draw from, since portal_access_enabled and portal_last_login_at already exist as real fields on the Client model and this is not a data modeling gap, only a tool coverage gap.

CHANGE INSTRUCTIONS:

Extend get_portal_inactive_clients to also compute and return, alongside its existing inactive client list: the total client count for the firm, the count of clients with portal_access_enabled true, and the count of clients where portal_last_login_at is not null, meaning they have logged in at least once. Add these as new top level keys in the returned dict, do not remove or rename any existing key, the existing inactive_count, threshold_days, and clients fields must remain exactly as they are for backward compatibility with anything already depending on this tool's current shape.

Update this tool's description in the tool registration in route.py to mention that it now also returns firm-wide portal enablement and login statistics, not only the inactivity list, so the model knows this data is available without needing to reach for a second tool call or invent it.

VERIFY AFTER ACT:

grep -n "def get_portal_inactive_clients" -A 60 /home/corby/jamm-os/app/api/concierge/functions.py

Confirm the new fields are present in the return statement alongside the original three.

python3 -c "from app.main import app; print('OK')"

MANUAL VERIFICATION:

Restart backend, keep terminal visible filtered for Tool executed. Ask which clients haven't logged into their portal recently. Confirm only get_portal_inactive_clients fires, same as before. Confirm the response's portal enablement and login statistics now match the real numbers the tool actually returned, not just numbers that happen to look the same as before, verify this by comparing the tool's actual return value in a quick direct database check against what the response states, using something like:

python3 -c "
from app.db.session import SessionLocal
from app.api.concierge.functions import get_portal_inactive_clients
db = SessionLocal()
result = get_portal_inactive_clients('185314c9-e702-4eab-8600-249848022206', db)
print(result)
db.close()
"

Paste this real output alongside the actual chat response, side by side, so the two can be directly compared and confirmed to match exactly.

GIT:
git add -A
git commit -m "extend get_portal_inactive_clients with real firm-wide portal enablement and login statistics, using existing portal_access_enabled and portal_last_login_at fields, so the model has genuine data instead of inventing plausible sounding numbers, addressing the actual root cause after a prompt only prohibition failed to stop the same fabrication from recurring"
git pull --rebase origin main
git push origin main