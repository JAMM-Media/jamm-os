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

# PRE-TASK
cd /home/corby/jamm-os
source .venv/bin/activate
python3 -c "from app.api.concierge.route import router; print('OK')"
If the import fails, stop and report. Do not proceed.
git add -A
git commit -m "checkpoint before [task name]"

---

# Section 3 - Your Task 

TASK: Fix intake selection response with few-shot examples

Pre-task:
cd /home/corby/jamm-os
git add -A && git commit -m "checkpoint before intake few-shot examples"

VERIFY BEFORE ACT:
sed -n '195,210p' /home/corby/jamm-os/app/api/concierge/prompts.py
Paste output before touching anything.

Change 1: prompts.py -- replace vague intake rule with locked few-shot examples

Find exactly:
When the firm selects one (they will type "1", "2", "3", or the name of the practice type), append a CONCIERGE_ACTION line at the very end of your response, after all text:
CONCIERGE_ACTION:{"type":"set_firm_type","firm_type":"tax_prep"}
Use tax_prep for option 1, bookkeeping for option 2, advisory for option 3.
Then output the matching starter prompts for their type exactly as specified below.

Replace with:
When the firm selects one, output the matching response exactly as shown in these examples. No other output. No variation.

<intake_example>
  <user>1</user>
  <assistant>Got it. Here are three things to work on first:
1. Walk me through setting up my first 1040 engagement
2. How do I send an IRS authorization to a client?
3. What automation presets should I turn on for a tax firm?
CONCIERGE_ACTION:{"type":"set_firm_type","firm_type":"tax_prep"}</assistant>
</intake_example>

<intake_example>
  <user>2</user>
  <assistant>Got it. Here are three things to work on first:
1. How do I set up a recurring monthly bookkeeping engagement?
2. Walk me through connecting QuickBooks
3. What automation presets should I turn on for a bookkeeping firm?
CONCIERGE_ACTION:{"type":"set_firm_type","firm_type":"bookkeeping"}</assistant>
</intake_example>

<intake_example>
  <user>3</user>
  <assistant>Got it. Here are three things to work on first:
1. How do I create an advisory engagement template?
2. Walk me through setting up billing for a retainer client
3. What should I set up first for an advisory practice?
CONCIERGE_ACTION:{"type":"set_firm_type","firm_type":"advisory"}</assistant>
</intake_example>

The same mapping applies when the firm types the name instead of the number:
"Tax prep and returns" = tax_prep
"Bookkeeping and monthly close" = bookkeeping
"Advisory and planning" = advisory

VERIFY AFTER ACT:
grep -n "intake_example\|set_firm_type" /home/corby/jamm-os/app/api/concierge/prompts.py
Confirm three intake_example blocks and one set_firm_type per block (three total).
grep -n "append a CONCIERGE_ACTION" /home/corby/jamm-os/app/api/concierge/prompts.py
Confirm zero results.

No build needed -- prompts.py is backend only.
Restart the backend after this change.

Database reset for browser test:
psql postgresql://postgres:postgres@localhost:5432/jammpx_dev -c "UPDATE firms SET firm_type = NULL WHERE id = '185314c9-e702-4eab-8600-249848022206';"

Browser test:
1. Hard refresh
2. Open panel -- intake appea