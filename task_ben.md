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

TASK: Add a business description field so clients can be found by a rough description of what their business does, not just by name

USE: Fable 5

VERIFY BEFORE ACT:
sed -n '55,80p' /home/corby/jamm-os/app/models/client.py
grep -n "def resolve_client_by_name" -A 25 /home/corby/jamm-os/app/api/concierge/functions.py
grep -n "class ClientCreate\|class ClientUpdate\|class ClientOut" -A 15 /home/corby/jamm-os/app/schemas/client.py
grep -rn "entity_type" /home/corby/jamm-os/frontend/src/app --include="*.tsx" | head -10
.venv/bin/alembic heads

Confirm current state matches described below. Check the real client creation and edit forms in the frontend to see where a new optional field would naturally fit into the existing form layout, do not guess at frontend structure.

WHAT THIS IS:

Confirmed live: asking to find a client by a rough business description, such as the client that does landscaping, correctly returns an honest I do not see a match, since no field anywhere on Client stores what kind of business a client actually runs, only entity_type, which is a tax classification, individual, business, trust, estate, unrelated to industry or business description. This is a real, deliberate product decision to close, not a bug, since the standards document calls for finding a client from a rough description as part of what full client knowledge coverage means.

CHANGE INSTRUCTIONS:

Add a new nullable field, business_description, a short free text string, to the Client model, matching the style of neighboring optional fields. Write a proper migration, checking alembic heads first and branching from the true current head, not a stale one.

Add this same field to the client create and update schemas as optional, and to the client response schema so it round-trips correctly.

Add a simple text input for this field to the real client creation form and the real client edit form in the frontend, labeled something like What does this client's business do, optional, placed near the existing entity type field since they are conceptually related. Keep this genuinely optional, do not require it, and do not backfill it for any existing client, leaving existing clients with this field empty is correct and expected.

Extend resolve_client_by_name so that, in addition to the existing name match, it also matches against business_description using the same case insensitive partial match pattern, returning a match from either field without duplicating a client that happens to match both.

Add an instruction to the system prompt, in the section governing client lookup, telling the model that if a firm owner describes a client by what their business does rather than by name, it should still call resolve_client_by_name, since business description is now included in that search, rather than assuming a description-based reference can never be resolved.

VERIFY AFTER ACT:

grep -n "business_description" /home/corby/jamm-os/app/models/client.py /home/corby/jamm-os/app/schemas/client.py /home/corby/jamm-os/app/api/concierge/functions.py /home/corby/jamm-os/app/api/concierge/prompts.py

Expected: present in all four.

.venv/bin/alembic upgrade head

Paste the real output, confirm it applies cleanly with no multi-head error.

Manually set a real business_description on one existing test client directly against the database to make this testable, for example set Brightline Properties LLC's business_description to landscaping and lawn care services, and confirm this update succeeds:

python3 -c "
from app.db.session import SessionLocal
from app.models.client import Client
db = SessionLocal()
client = db.query(Client).filter(Client.name == 'Brightline Properties LLC').first()
client.business_description = 'landscaping and lawn care services'
db.commit()
print('set business_description on', client.name)
db.close()
"

python3 -c "
from app.db.session import SessionLocal
from app.api.concierge.functions import resolve_client_by_name
db = SessionLocal()
result = resolve_client_by_name('185314c9-e702-4eab-8600-249848022206', db, 'landscaping')
print(result)
db.close()
"

Expected: Brightline Properties LLC appears as a match, confirming the extended search actually works before manual testing in the browser.

npm run build in frontend, expected zero TypeScript errors.
python3 -c "from app.main import app; print('OK')"

MANUAL VERIFICATION:

Restart both servers. Ask the exact question that originally failed to resolve, draft an email to the client that does landscaping about their overdue invoice, now that Brightline Properties LLC genuinely has that description set, confirm it now correctly resolves to Brightline Properties LLC instead of asking for the real name.

Separately, open the real client edit form for a different client and confirm the new business description field is visible, editable, and saves correctly.

Report pass or fail individually for the resolve_client_by_name test, the live chat question, and the frontend form check.

GIT:
git add -A
git commit -m "add business_description field to Client, closing a real gap where clients could only be found by name, never by what their business actually does, confirmed live during a deep audit; extends resolve_client_by_name to search both fields and adds the field to the real client creation and edit forms as optional"
git pull --rebase origin main
git push origin main