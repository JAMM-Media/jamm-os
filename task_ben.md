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

# Section 3 - The task

# Task: Add Fee Schedule to Concierge knowledge base

USE: claude sonnet

## VERIFY BEFORE ACT

grep -n "Navigate to Settings > Billing > Connect Stripe" /home/corby/jamm-os/app/api/concierge/prompts.py

Confirm this existing line and its surrounding section, so the new Fee Schedule entry can be added nearby in a way that matches the file's existing voice and structure for Settings-related how-to content.

## WHAT IS WRONG

Confirmed via direct production verification: a user asked where to set tax form prices and the Concierge responded that JAMM PX has no pricing or fee schedule feature anywhere in the app. This is false. Settings > Fee Schedule is a real, live feature with per-engagement-type base fees and complexity adders that pre-fill engagement letters. It is entirely absent from prompts.py, so the Concierge has no knowledge of it and denies it exists when asked directly.

## ACTION

File: /home/corby/jamm-os/app/api/concierge/prompts.py

Add a new entry near the other Settings navigation references (the Settings > Billing > Connect Stripe line found in VERIFY BEFORE ACT), in the same style:

Fee Schedule: Navigate to Settings > Fee Schedule. Set standard fees per engagement type. Categories covered: Tax Returns (1040 Individual, 1120 C-Corporation, 1120-S S-Corporation, 1065 Partnership, 1041 Trust/Estate Income, 706 Estate Tax, 1040-X Amended Return), Extensions (4868 Individual, 7004 Business, 8868 Exempt Org), Bookkeeping (Monthly, Quarterly), Payroll (941 Quarterly Payroll Tax), and Other Services (Tax Planning/Advisory, Audit Representation, Other/Custom). A separate Complexity Adders section lets firms add flat-rate fees for things like rental property, foreign accounts/FBAR, depreciation schedules, multiple states, and trust or estate involvement, plus tiered-rate fees for K-1 involvement and cryptocurrency transactions. Any field left blank means that type is not priced from the schedule and is priced individually instead. Fee amounts auto-populate when sending an engagement letter but are never shown to clients directly.

Setting what to charge for a specific engagement type or complexity adder is the firm's own business decision. If a user asks what amount they should charge, redirect using the existing professional-judgment-call pattern already used elsewhere in this file: explain that pricing decisions are up to the firm, and offer to navigate them to Settings > Fee Schedule to enter whatever amount they decide on.

Place this new entry as its own paragraph, do not merge it into the existing Stripe/Billing paragraph since they are different features. Do not change the existing Stripe/Billing line. Do not touch any other file.

## VERIFY AFTER ACT

grep -n "Fee Schedule: Navigate to Settings" /home/corby/jamm-os/app/api/concierge/prompts.py

Expected: present.

python3 -c "from app.api.concierge.route import router; print('OK')"

Expected: OK, no import errors.

## MANUAL VERIFICATION

1. Restart the backend.
2. Ask the Concierge: "where do I go to set my tax form prices?"
3. Confirm the response correctly directs to Settings > Fee Schedule and does not deny the feature exists.
4. Ask the Concierge: "what should I charge for a 1040?"
5. Confirm the response redirects this as a professional/business judgment call rather than suggesting a dollar amount, while still being willing to navigate to Fee Schedule so the user can enter their own number.

Report the exact response text at steps 3 and 5.

## GIT

cd /home/corby/jamm-os
git add -A
git commit -m "fix: add Fee Schedule feature to Concierge knowledge base, correcting a false denial that the feature exists, while keeping actual pricing decisions as a firm business judgment call the agent does not make for them"
git pull --rebase origin main
git push origin main

If conflicts on task.md use --theirs. Conflicts on source files use --ours.