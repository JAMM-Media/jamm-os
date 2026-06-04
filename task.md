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

# POST-TASK — run after task completes
find /home/corby/jamm-os/app/api/concierge/ -name "*.py" | sort
ls /home/corby/jamm-os/migrations/versions/ | tail -5
python3 -c "from app.api.concierge.route import router; print('OK')"
find /home/corby/jamm-os/frontend/src/components/concierge/ -name "*.tsx" | sort

---

# Feature: Add firm type intake to empty state

Task: Add firm_type to the context snapshot so the Concierge knows whether the firm has
set their type yet. Update the empty state prompt to ask the firm type question when
firm_type is null, and show type-specific starter prompts when it is set.

Two files. Do them in order.

---

## File 1 of 2: context.py

Task: Add firm_type to the context snapshot.

VERIFY BEFORE ACT:
grep -n "firm_type\|from app.models.firm\|Firm" /home/corby/jamm-os/app/api/concierge/context.py | head -15

Paste before touching anything.

Find the Firm model import at the top of context.py and confirm Firm is already imported.
Then make exactly one change:

OLD:
    return {
        "client_count": client_stats["total"],
        "clients_missing_email": client_stats["missing_email"],
        "clients_inactive": client_stats["inactive"],
        "import_log": import_log,
        "onboarding_steps": onboarding_steps,
        "engagement_summary": engagement_summary,
        "staff_summary": staff_summary,
        "portal_adoption": portal_adoption,
        "irs_coverage": irs_coverage,
        "question_history_topics": question_history,
    }

NEW:
    firm = db.execute(select(Firm).where(Firm.id == firm_id)).scalar_one_or_none()
    firm_type = firm.firm_type if firm else None
    return {
        "client_count": client_stats["total"],
        "clients_missing_email": client_stats["missing_email"],
        "clients_inactive": client_stats["inactive"],
        "import_log": import_log,
        "onboarding_steps": onboarding_steps,
        "engagement_summary": engagement_summary,
        "staff_summary": staff_summary,
        "portal_adoption": portal_adoption,
        "irs_coverage": irs_coverage,
        "question_history_topics": question_history,
        "firm_type": firm_type,
    }

Confirm Firm and select are already imported. If not, add them.

Do not change anything else.

VERIFY AFTER ACT:
1. grep -n "firm_type" /home/corby/jamm-os/app/api/concierge/context.py
   Confirm present in the return block.
2. cd /home/corby/jamm-os
3. source .venv/bin/activate
4. python3 -c "from app.api.concierge.context import get_firm_context; print('ok')"
   Confirm no import errors.

---

## File 2 of 2: prompts.py

Task: Update the empty state prompt to ask the firm type intake question when firm_type
is not set, and show type-specific starter prompts when it is.

VERIFY BEFORE ACT:
sed -n '191,200p' /home/corby/jamm-os/app/api/concierge/prompts.py

Paste before touching anything.

OLD:
EMPTY STATE — FIRST OPEN
When the messages array is empty and this is the firm's first interaction, output exactly this and nothing else:
"Welcome to JAMM Concierge. Here are three things I can help you with right now:
1. Walk me through importing my clients from TaxDome (or another platform)
2. Explain the difference between engagements and tasks in JAMM PX
3. What should I set up first after signing up?"
Do not add any other text. Do not greet. Do not explain what you are. The three prompts are the entire first message.

NEW:
EMPTY STATE — FIRST OPEN
When the messages array is empty and this is the firm's first interaction, check firm_type in the live firm context.

If firm_type is null or not set, output exactly this and nothing else:
"Welcome to JAMM Concierge. Before we start -- what does your firm do most? This lets me point you to the right setup path.
1. Tax prep and returns
2. Bookkeeping and monthly close
3. Advisory and planning"
Do not add any other text. When the firm selects one, confirm their firm type and immediately recommend the three automation presets and one engagement template that match their practice type. Then proceed to the normal starter prompts for their type.

If firm_type is tax_prep, output exactly this and nothing else:
"Welcome back. Here are three things to work on next:
1. Walk me through setting up my first 1040 engagement
2. How do I send an IRS authorization to a client?
3. What automation presets should I turn on for a tax firm?"

If firm_type is bookkeeping, output exactly this and nothing else:
"Welcome back. Here are three things to work on next:
1. How do I set up a recurring monthly bookkeeping engagement?
2. Walk me through connecting QuickBooks
3. What automation presets should I turn on for a bookkeeping firm?"

If firm_type is advisory, output exactly this and nothing else:
"Welcome back. Here are three things to work on next:
1. How do I create an advisory engagement template?
2. Walk me through setting up billing for a retainer client
3. What should I set up first for an advisory practice?"

Do not add any other text. Do not greet beyond what is shown above. The prompts are the entire first message.

Do not change anything else.

VERIFY AFTER ACT:
1. grep -n "EMPTY STATE\|firm_type\|tax_prep\|bookkeeping\|advisory" /home/corby/jamm-os/app/api/concierge/prompts.py | head -15
   Confirm firm_type logic and all three practice types present.
2. Restart the backend.
3. Browser test: open a fresh Concierge panel with no prior messages.
   Confirm: the three-option firm type question appears, not the old generic prompts.