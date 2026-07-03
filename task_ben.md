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

# Task: Fix billing/calendar topic misclassification caused by overly short "ar" keyword substring collision

USE: claude sonnet

## VERIFY BEFORE ACT

grep -n '"ar"' /home/corby/jamm-os/app/api/concierge/route.py

Confirm "ar" exists as a standalone keyword in the billing entry of _TOPIC_KEYWORDS.

python3 -c "
msg = 'is there any calendar in the app?'
print('ar' in msg)
"

Confirm this prints True, demonstrating that the short keyword "ar" matches as a substring inside "calendar" even though the message has nothing to do with billing.

## WHAT IS WRONG

Confirmed via live testing and direct reproduction: a calendar-only question ("is there any calendar in the app?") was classified as [TOPIC:billing] instead of [TOPIC:calendar], showing the wrong suggestion chip. Root cause: _classify_topic uses plain substring matching (kw in lower), not word-boundary-aware matching. The billing keyword set includes the short abbreviation "ar" (shorthand for accounts receivable), which matches as a substring inside any word containing those two consecutive letters, including "calendar" itself. This produces a tied score between billing and calendar for calendar-related messages, and since billing is defined earlier in the dictionary, ties resolve in its favor via Python's max() returning the first-encountered maximum. This is a pre-existing flaw in the keyword matching approach that was only exposed now that a calendar topic exists to collide with it, but the same short-keyword substring risk could affect other topics too.

## ACTION

File: /home/corby/jamm-os/app/api/concierge/route.py

Remove the standalone "ar" keyword from the billing entry in _TOPIC_KEYWORDS, since "accounts receivable" (the full phrase) is already present in the same set and provides the same intent-matching without the substring collision risk. Find the billing keyword set and remove just the "ar" entry:

    "billing": {
        "invoice", "invoices", "billing", "payment", "stripe", "overdue invoice",
        "ar", "accounts receivable", "send invoice", "invoice status",
        "partial payment", "payment receipt", "invoice line", "bill",
        "unbilled", "collect payment", "paid", "unpaid", "owes", "owe", "money",
    },

Change to:

    "billing": {
        "invoice", "invoices", "billing", "payment", "stripe", "overdue invoice",
        "accounts receivable", "send invoice", "invoice status",
        "partial payment", "payment receipt", "invoice line", "bill",
        "unbilled", "collect payment", "paid", "unpaid", "owes", "owe", "money",
    },

Do not change any other keyword in any topic's set. Do not change _classify_topic's matching algorithm itself in this task -- switching from substring matching to word-boundary matching across all topics is a larger, separate change that could affect every topic's behavior simultaneously and should be scoped on its own if this kind of collision is found again elsewhere. This task only removes the one confirmed problematic short keyword.

## VERIFY AFTER ACT

grep -n '"billing": {' -A 6 /home/corby/jamm-os/app/api/concierge/route.py

Expected: "ar" is no longer present in the billing set, "accounts receivable" still is.

python3 -c "
msg = 'is there any calendar in the app?'
print('ar' in msg)
"

Expected: still True (this is just confirming the substring exists in the word, which is unavoidable and fine) -- the actual fix is that "ar" is no longer a keyword being checked against messages at all, not that the substring stopped existing in the English language.

python3 -c "from app.api.concierge.route import router; print('OK')"

Expected: OK, no import errors.

## MANUAL VERIFICATION (the actual test)

1. Restart the backend (full kill and restart, not reload).
2. Ask "is there any calendar in the app?" again, the exact question that triggered the misclassification.
3. Check DevTools Console [CONCIERGE RAW] output, confirm [TOPIC:calendar] now appears instead of [TOPIC:billing].
4. Confirm the Go to Calendar chip now appears and navigates correctly.
5. Regression check: ask a real billing question (e.g. "what invoices are overdue?") and confirm it still correctly tags [TOPIC:billing] and shows the Go to Billing chip, unaffected by removing the "ar" keyword since "accounts receivable" and "overdue invoice" still cover that intent.

Report the exact [TOPIC:...] value observed at step 3, and confirm step 5 still works correctly.

## GIT

cd /home/corby/jamm-os
git add -A
git commit -m "fix: remove overly short 'ar' keyword from billing topic classifier, which was matching as a substring inside unrelated words like 'calendar' (c-a-l-e-n-d-AR) and causing calendar questions to be misclassified as billing due to a tied keyword score resolving in billing's favor"
git pull --rebase origin main
git push origin main

If conflicts on task.md use --theirs. Conflicts on source files use --ours.