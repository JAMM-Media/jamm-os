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

TASK: Fix client name resolution failing for client names containing an ampersand, breaking any Concierge action that navigates to a specific client's page

USE: claude sonnet

VERIFY BEFORE ACT:

sed -n '1308,1330p' /home/corby/jamm-os/app/api/concierge/route.py

Confirm the client match query currently does a plain func.lower(Client.name).like(f"%{name.lower()}%") with no normalization of special characters, before editing.

WHAT THIS IS:

Confirmed live: asking the Concierge to send Robert & Carol Tanner their portal link, with autopilot on, correctly triggered the navigate-and-open action, but the app never navigated away from the current page. Root cause: the CONCIERGE_ACTION route uses a slug placeholder like /clients/[client-name-slug], which the frontend decodes by replacing dashes with spaces to recover a searchable name. Client names containing an ampersand, like "Robert & Carol Tanner", lose the ampersand somewhere in the slugification and decoding round trip, producing a search string like "robert carol tanner" with no ampersand. The backend's /clients/resolve endpoint does a plain substring match against the real client name "Robert & Carol Tanner", which does not contain "robert carol tanner" as a substring because of the ampersand and surrounding spacing sitting between the two names, so the match fails, the endpoint 404s, and the frontend silently shows "Could not find client" and never navigates, while the Concierge's own response text had already said it was navigating. This will affect every client whose name contains an ampersand or any other punctuation that does not survive the slug round trip cleanly, not just this one client.

CHANGE INSTRUCTIONS:

In the /clients/resolve endpoint, normalize both the incoming name query and the stored Client.name before comparing, stripping or ignoring ampersands and any other punctuation that is not a letter, number, or space, and collapsing repeated spaces, so that "robert carol tanner" and "Robert & Carol Tanner" match correctly regardless of how the slug was decoded. Do this as a real, deterministic normalization applied symmetrically to both sides of the comparison, not as a special case for the ampersand specifically, since other punctuation could cause the same class of failure. Do not change resolve_client_by_name in functions.py, the tool used by the model to answer questions, this task is scoped only to the /clients/resolve endpoint used for navigation.

VERIFY AFTER ACT:

python3 -c "
import sys
sys.path.insert(0, '/home/corby/jamm-os')
from app.api.concierge.route import resolve_client_by_name
"

grep -n "def resolve_client_by_name" -A 20 /home/corby/jamm-os/app/api/concierge/route.py

Confirm the normalization logic is present and applied to both sides of the comparison.

python3 -c "from app.main import app; print('OK')"

MANUAL VERIFICATION:

Restart the backend.

With autopilot on, ask the Concierge to send Robert & Carol Tanner their portal link.

Confirm the app actually navigates to Robert & Carol Tanner's page this time, not just that the response text claims it.

Confirm the portal-link button's ring highlight fires within about a second of arriving on the page.

Separately, test with a client whose name has no punctuation at all, to confirm the fix did not break the normal case.

Report pass or fail for all three checks individually.

GIT:

git add -A

git commit -m "normalize punctuation, specifically ampersands, on both sides of the client name comparison in the /clients/resolve endpoint, fixing navigation silently failing for any client whose name contains an ampersand or similar punctuation that does not survive the slug encode/decode round trip, confirmed live tonight with Robert and Carol Tanner never being navigated to despite the Concierge claiming it was"

git pull --rebase origin main

git push origin main