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

TASK: Build a get_firm_settings tool covering subscription, notification preferences, and connected integrations, closing the confirmed live fabrication in this domain

USE: Fable 5

VERIFY BEFORE ACT:
grep -n "class Firm" -A 5 /home/corby/jamm-os/app/models/firm.py
grep -n "settings\|feature_flags" /home/corby/jamm-os/app/models/firm.py
grep -n "quickbooks_connected\|stripe_account\|is_connected\|connected_at" /home/corby/jamm-os/app/services/quickbooks_service.py /home/corby/jamm-os/app/services/stripe_service.py 2>/dev/null
grep -rn "class.*Integration\|quickbooks_id\|stripe_account_id" /home/corby/jamm-os/app/models/*.py 2>/dev/null

Read all of this in full before writing anything. This task's whole point is replacing a confirmed live fabrication with real data, so every field used must be verified to genuinely exist and genuinely mean what it appears to mean, not assumed from a plausible-sounding name.

WHAT THIS IS:

Confirmed live during a deep audit: asked what integrations are connected, the Concierge invented a list naming QuickBooks, Dropbox Sign, and Stripe, none of which were verified as actually connected. Asked about notification preferences, it invented a Notifications tab that does not exist. This is the exact same confident-fabrication pattern already found and fixed twice tonight for portal data and staff workload, in the one domain that currently has zero tool coverage at all in the entire Concierge tool inventory.

CHANGE INSTRUCTIONS:

In functions.py, add a new tool function, get_firm_settings, firm scoped, matching the existing docstring and structure pattern used by neighboring tools. It should return, using only fields confirmed to genuinely exist: the real subscription_tier, whatever real notification-relevant keys actually exist inside the settings JSON field on Firm, the real staff_auth_policy, the real timesheet_approval_required flag, and the real verification status of sending_domain and portal_domain, framed honestly as domain configuration, not invented as generic feature toggles.

For connected integrations specifically, base this only on whatever real, verifiable signal actually exists, such as a real non-null credential or connection timestamp field found during the verify step, for each of QuickBooks, Stripe, and e-sign. If no real signal exists at all for a given integration, the tool must report it as not connected or unknown, never invent a connected status. If none of the three have any real trackable connection signal anywhere in the codebase, say so plainly in the tool's returned data rather than guessing, and note this limitation in the tool's own description so the model knows not to overstate certainty here.

Register the tool in _CONCIERGE_TOOLS with a clear description covering subscription plan, notification preferences, and integration status questions. Add relevant keywords to both _OPERATIONAL_KEYWORDS and _TOPIC_KEYWORDS, including subscription, plan, integrations, connected, notification preferences, settings, since this domain currently has zero coverage in either keyword set.

VERIFY AFTER ACT:

grep -n "get_firm_settings" /home/corby/jamm-os/app/api/concierge/functions.py /home/corby/jamm-os/app/api/concierge/route.py

python3 -c "
from app.db.session import SessionLocal
from app.api.concierge.functions import get_firm_settings
db = SessionLocal()
result = get_firm_settings('185314c9-e702-4eab-8600-249848022206', db)
print(result)
db.close()
"

Paste this real output, confirm every field in it is something you can independently verify against the actual database record for this firm, not something that merely looks plausible.

python3 -c "from app.main import app; print('OK')"

MANUAL VERIFICATION:

Restart backend, keep terminal visible filtered for Tool executed.

Ask what integrations are connected, confirm get_firm_settings fires and the response contains only real, verified information, explicitly saying so plainly if integration status genuinely cannot be determined from any real data, rather than naming specific tools as connected without real evidence.

Ask what our notification preferences are, confirm the same tool fires and returns real data from the actual settings field, not an invented tab or feature.

Ask what's our current subscription plan, confirm the real subscription_tier value comes back correctly.

Report pass or fail for all three, including the exact tool name confirmed in the log for each, and paste the actual response text for all three, not a summary.

GIT:
git add -A
git commit -m "add get_firm_settings tool covering subscription tier, notification preferences, and integration status where a real verifiable signal exists, closing the confirmed live fabrication where the agent invented a QuickBooks Stripe Dropbox Sign integrations list and a nonexistent notifications tab, the one domain with zero tool coverage anywhere in the Concierge tool inventory"
git pull --rebase origin main
git push origin main