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

TASK: Add a deterministic, pre-computed portal status field to get_client_full_snapshot, ending the model's reliance on prose instructions to reconcile portal access facts it never actually had

USE: claude sonnet

VERIFY BEFORE ACT:

sed -n '426,480p' /home/corby/jamm-os/app/api/concierge/functions.py

sed -n '385,390p' /home/corby/jamm-os/app/api/concierge/prompts.py

Confirm get_client_full_snapshot's real, current return dict includes portal_access, sourced from client.portal_access_enabled, but does not include portal_invite_sent_at anywhere in the returned data at all. Confirm the reconciliation instruction added earlier tonight in prompts.py asks the model to reconcile these two facts, but the underlying fact, portal_invite_sent_at, was never actually present in the tool's own output for the model to reason about, meaning the earlier fix could never have worked reliably no matter how the prompt was worded, since the real data was missing at the source.

WHAT THIS IS:

Live testing tonight, after the backend was correctly restarted, showed the earlier prompt-only reconciliation instruction still failed, the response mentioned portal access being enabled without any mention of the invite never being sent. Investigation found the real, deeper cause: portal_invite_sent_at was never included in this tool's returned data in the first place, so the model had no real fact to reconcile in the first place, no prompt wording could have fixed this reliably. This matches the core lesson proven repeatedly tonight, and the correct fix here goes one step further than usual: not only must the real data be included, but the reconciliation itself should be computed deterministically in Python and handed to the model as a ready-made, already-correct fact, rather than trusting the model to correctly combine two raw fields into the right sentence on every single call.

CHANGE INSTRUCTIONS:

In get_client_full_snapshot, add portal_invite_sent_at to the returned dict, formatted the same isoformat-or-None style already used for other date fields in this function. Also add a new field, portal_status_note, computed deterministically with plain Python conditional logic before the return statement: if portal_access_enabled is true and portal_invite_sent_at is null, set this to the exact sentence "Portal access is enabled, but this client has never been sent their invite link." If portal_access_enabled is true and portal_invite_sent_at is set, set it to a sentence confirming both access and that the invite was sent. If portal_access_enabled is false, set it to a sentence stating portal access has not been enabled for this client. Include this new field in the returned dict alongside the existing portal_access field.

In prompts.py, update the reconciliation instruction added earlier tonight to tell the model to use the value of portal_status_note directly when describing a client's portal status, rather than attempting to reconcile portal_access and portal_invite_sent_at itself, since this is now pre-computed and guaranteed correct.

VERIFY AFTER ACT:

grep -n "portal_status_note\|portal_invite_sent_at" /home/corby/jamm-os/app/api/concierge/functions.py

python3 -c "
import sys
sys.path.insert(0, '/home/corby/jamm-os')
from app.api.concierge.functions import get_client_full_snapshot
print('function updated, real check requires live data')
"

python3 -c "from app.main import app; print('OK')"

MANUAL VERIFICATION:

Restart the backend.

Ask the Concierge to tell you about Robert & Carol Tanner three times in a row. Confirm all three responses now correctly and consistently mention that portal access is enabled but the invite has never been sent, not just once but reliably every time, since this is no longer dependent on the model's own discretion.

Report pass or fail, quoting all three responses verbatim, since this is meant to permanently close a problem that has now failed twice tonight with prompt-only approaches.

GIT:

git add -A

git commit -m "add a deterministic, pre-computed portal_status_note field to get_client_full_snapshot, ending reliance on a prose instruction to reconcile portal_access_enabled and portal_invite_sent_at, since the earlier prompt-only fix still failed live tonight after a correct restart, and investigation found the deeper cause, portal_invite_sent_at was never actually included in this tool's returned data at all, meaning no prompt wording could have worked reliably since the real fact was missing at the source; the reconciliation is now computed once in deterministic Python and handed to the model as a ready-made, guaranteed-correct fact instead of being left to the model's own discretion on every call"

git pull --rebase origin main

git push origin main