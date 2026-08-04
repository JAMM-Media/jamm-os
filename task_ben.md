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

TASK: Build a shared, timezone-safe date formatter and apply it to every confirmed date-only field across the app, fixing the systemic off-by-one display bug found tonight

USE: Fable 5

VERIFY BEFORE ACT:

psql postgresql://postgres:postgres@localhost:5432/jammpx_dev -c "SELECT id, name, filing_deadline, extended_deadline FROM engagements WHERE client_id = 'e6e6c68f-2b47-42dd-bbcd-b17594c4b687' AND name LIKE '%2026 Individual%';"

Confirm the real, raw stored filing_deadline for this engagement is 2027-04-15, and confirm EngagementTable.tsx currently displays this as Apr 14, 2027, one day earlier than the real value, because new Date(raw) parses a plain YYYY-MM-DD string as UTC midnight, which then renders one day earlier in any browser timezone behind UTC when passed to toLocaleDateString. This is the confirmed, real root cause of a live fabrication finding from tonight's audit, later found to actually be a real, separate frontend bug rather than a Concierge fabrication once the underlying database value was checked directly.

Here are the 18 real call sites in the codebase using this same new Date(...).toLocaleDateString or toLocaleString pattern, found by a live grep tonight. For every single one of these, before changing anything, find and read the actual backend Pydantic schema or SQLAlchemy model field feeding the value, to determine whether it is a real DATE-only field, vulnerable to this exact bug, or a real DATETIME or TIMESTAMPTZ field, which already carries explicit time and is not vulnerable to this specific bug. Do not assume based on variable naming alone, confirm each one against the real backend type.

/home/corby/jamm-os/frontend/src/app/(app)/clients/[id]/page.tsx:552 (qboAr.last_payment_date)
/home/corby/jamm-os/frontend/src/app/(app)/clients/[id]/page.tsx:957 (thread.date)
/home/corby/jamm-os/frontend/src/app/(app)/concierge-log/page.tsx:18 (iso)
/home/corby/jamm-os/frontend/src/app/(app)/dashboard/page.tsx:399 (item.sent_at)
/home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx:1191 (new Date() with no argument, today's date)
/home/corby/jamm-os/frontend/src/components/engagements/SendEngagementLetterModal.tsx:255 (displayDate)
/home/corby/jamm-os/frontend/src/components/engagements/SendEngagementLetterModal.tsx:336 (new Date() with no argument, today's date)
/home/corby/jamm-os/frontend/src/components/engagements/EngagementTable.tsx:37 (raw, confirmed vulnerable, filing_deadline or extended_deadline)
/home/corby/jamm-os/frontend/src/components/settings/AutomationsTab.tsx:119 (rule.last_executed_at)
/home/corby/jamm-os/frontend/src/components/portal/PortalInvoices.tsx:29 (dateStr)
/home/corby/jamm-os/frontend/src/components/portal/PortalOrganizer.tsx:337 (activeOrganizer.submitted_at)
/home/corby/jamm-os/frontend/src/components/portal/PortalTodo.tsx:26 (iso)
/home/corby/jamm-os/frontend/src/components/portal/PortalBillingDetail.tsx:100 (report.created_at)
/home/corby/jamm-os/frontend/src/components/clients/IrsAuthBadge.tsx:65 (dateStr)
/home/corby/jamm-os/frontend/src/components/clients/PortalPreview.tsx:27 (iso)
/home/corby/jamm-os/frontend/src/components/clients/PortalPreview.tsx:35 (iso, uses toLocaleString not toLocaleDateString)
/home/corby/jamm-os/frontend/src/components/clients/DocumentExpirySection.tsx:44 (d, likely expires_on)
/home/corby/jamm-os/frontend/src/components/clients/IrsAuthTab.tsx:30 (d, likely an expiry date)

WHAT THIS IS:

A live browser audit tonight flagged what looked like a Concierge fabrication, a filing deadline stated as one day different from what the Engagements page showed. Direct investigation proved the Concierge was actually correct, the real database value is 2027-04-15, and the Engagements page itself has a real, confirmed, systemic frontend bug: any plain date-only string like 2027-04-15, passed directly to new Date(), gets interpreted as UTC midnight by the JavaScript Date constructor, then rendered in the browser's local timezone, shifting the displayed date backward by one day for any user in a timezone behind UTC. A grep tonight found this same unsafe pattern at 18 real call sites across the app. Bare new Date() calls with no argument, and any date field carrying a real time component like a created_at or sent_at timestamp, are not vulnerable to this specific bug and must not be touched, only genuine date-only fields are at risk.

CHANGE INSTRUCTIONS:

Create a new shared utility function, for example formatLocalDate, in a sensible shared location such as frontend/src/lib/utils.ts if date utilities do not already have a dedicated file, or a new frontend/src/lib/dateUtils.ts if they do not. This function should accept a date-only string in YYYY-MM-DD form and a set of Intl.DateTimeFormat-style formatting options, and safely construct a Date object using the year, month, and day components extracted directly from the string, passed to the multi-argument Date constructor, which is always interpreted in local time by JavaScript and never shifts across a UTC boundary, then call toLocaleDateString on that safely-constructed date with the given options. This avoids the entire class of bug at its root rather than patching each call site with a different workaround.

For each of the 18 call sites listed above, after confirming the real backend field type: if the field is a genuine date-only field, replace the unsafe new Date(value).toLocaleDateString(...) call with a call to the new formatLocalDate utility, preserving the exact same formatting options already used at that call site so the visual output format does not change, only the correctness of which day is shown. If the field is confirmed to be a real datetime or timestamp field, or if the call has no argument at all, leave it completely unchanged and note in your final report that it was checked and confirmed safe, do not modify it.

VERIFY AFTER ACT:

grep -n "formatLocalDate" /home/corby/jamm-os/frontend/src/lib/*.ts

Expected: the new utility function defined, and imported in every file where a genuine date-only field was fixed.

npx tsc --noEmit

Provide a full written report listing all 18 original call sites, stating for each one whether it was confirmed as a real date-only field and fixed, or confirmed as a safe datetime or no-argument call and left unchanged, with the real backend field type cited as evidence for each classification, not assumed.

MANUAL VERIFICATION:

Restart the frontend.

Visit the Engagements page, confirm Robert & Carol Tanner's 2026 Individual Tax Return now correctly shows April 15, 2027, matching the real database value, not April 14.

Spot check at least three other pages among the ones actually changed, for example a client's IRS Authorizations tab, Document Expiry tracking, and the client portal invoices view if reachable, confirming dates there now display correctly and did not silently shift in the opposite direction or break formatting.

Confirm at least one of the pages deliberately left unchanged, for example the Dashboard's sent_at timestamp display, still renders exactly as it did before, confirming the fix was correctly scoped only to genuine date-only fields.

Report pass or fail for each of these checks individually.

GIT:

git add -A

git commit -m "fix a systemic off-by-one date display bug found while investigating what a live audit tonight initially flagged as a Concierge fabrication, which turned out to actually be a real, correct answer from the Concierge and a genuine frontend bug instead: plain date-only values were being parsed as UTC midnight by the JavaScript Date constructor and then rendered in local time, shifting the displayed date back by one day for any user behind UTC; added a shared, timezone-safe formatLocalDate utility and applied it to every confirmed genuine date-only field among 18 real call sites found across the app, leaving real datetime and timestamp fields, which were never vulnerable to this specific bug, untouched"

git pull --rebase origin main

git push origin main