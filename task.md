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

# Task: Write /knowledge/13_reports_analytics.md

## VERIFY BEFORE ACT

```bash
grep -r "13_reports" /home/corby/jamm-os/knowledge/
```

If the file exists, stop and report. Do not overwrite.

```bash
ls /home/corby/jamm-os/knowledge/
```

Confirm the `/knowledge/` directory exists before proceeding.

---

## ACTION

Create the file `/home/corby/jamm-os/knowledge/13_reports_analytics.md` with exactly the content below. No modifications. Copy verbatim.

```markdown
## Reports and Analytics > Overview > Where to Find Reports

JAMM PX surfaces reporting data in two places. The Dashboard shows a live snapshot of firm-wide metrics each time it loads. The Billing section contains the WIP Report, which tracks unbilled time across active engagements.

Navigate to Dashboard in the left sidebar for the firm overview. Navigate to Billing and select WIP Report for work-in-progress data.

---

## Reports and Analytics > Dashboard > What the Dashboard Shows

The Dashboard is the home screen of JAMM PX. It loads a set of firm-wide metrics automatically each time it is opened. The metrics are calculated fresh on each load and reflect the current state of the firm.

The Dashboard is visible to all staff roles. Firm owners and managers see all firm-wide data. Staff members see data scoped to their assigned engagements and tasks.

---

## Reports and Analytics > Dashboard > Metric Cards

The Dashboard displays six metric cards at the top of the page.

Monthly Recurring Revenue shows the total value of invoices marked as recurring for the current month and the count of invoices included.

Outstanding AR shows the total dollar value of unpaid sent invoices and the number of those invoices. It also shows how many days the oldest overdue invoice has been unpaid.

WIP Value shows the total dollar value of unbilled billable time across all active engagements and the total hours that value represents.

Overdue Engagements shows the count of engagements whose deadline has passed and that are not yet completed.

Unsigned Documents shows the count of signature envelopes that have been sent but not yet signed by the client.

Total Clients, Active Engagements, Overdue, and Awaiting Docs are shown as a summary row below the metric cards.

---

## Reports and Analytics > Dashboard > Upcoming Deadlines

The Dashboard shows a list of engagements with deadlines in the next 14 days. Each row shows the client name, engagement type, deadline date, and a colored days-remaining badge.

The badge is green for deadlines more than 6 days away, amber for deadlines 3 to 6 days away, and red for deadlines 2 days away or less.

If no engagements have a deadline in the next 14 days, the section shows a clear runway message. Click View full calendar at the bottom of the list to open the calendar view.

---

## Reports and Analytics > Dashboard > Overdue Engagements

The Dashboard shows a list of engagements that have passed their deadline and are not yet completed. Each row shows the client name, engagement type, deadline date, how many days overdue the engagement is, and the assigned staff member.

Review this list to identify engagements that need immediate attention. Click any engagement in the list to open it directly.

---

## Reports and Analytics > Dashboard > Staff Utilization

The Dashboard shows a staff utilization panel with each staff member's hours logged this week and their utilization percentage. The utilization bar is green when below 80%, amber between 80% and 99%, and red at 100% or above.

Staff utilization data is visible to firm owners and managers only. Individual staff members do not see this panel.

Use the staff utilization panel to identify team members who have capacity and those who are at or near their limit before assigning new work.

---

## Reports and Analytics > Dashboard > Unsigned Documents

The Dashboard shows a list of signature envelopes that have been sent but not yet signed. Each row shows the client name, document title, the date the envelope was sent, and how many days the client has had it without signing.

Use this list to identify clients who need a follow-up on outstanding signature requests. The E-Signature Reminder automation preset sends reminders automatically, but this list gives a manual view of what is still outstanding.

---

## Reports and Analytics > WIP Report > What the WIP Report Shows

The WIP report shows all unbilled billable time entries across all active engagements. WIP stands for work in progress. The report shows each engagement with its client name, total hours logged, and the dollar value of those hours based on the billing rates on each time entry.

The total WIP value and total hours are shown at the top of the report as summary figures.

Navigate to Billing in the left sidebar and select WIP Report.

---

## Reports and Analytics > WIP Report > Using the WIP Report for Month-End Billing

Run the WIP report before each billing cycle to identify all work that has been done but not yet invoiced. The report shows only unbilled time. Once a time entry is added to an invoice it is marked as billed and removed from the WIP report.

Review the top engagements by WIP value first. These are the highest-priority items to invoice before month-end close.

---

## Reports and Analytics > WIP Report > Exporting the WIP Report

Click Export CSV in the top right corner of the WIP Report page. The file downloads with columns for client, engagement, hours, and value.

Use the export to review billing in a spreadsheet, share with a billing manager, or keep a record of unbilled work at a point in time.
```

---

## VERIFY AFTER ACT

```bash
wc -l /home/corby/jamm-os/knowledge/13_reports_analytics.md
```

Expected: between 100 and 130 lines.

```bash
grep -c "^##" /home/corby/jamm-os/knowledge/13_reports_analytics.md
```

Expected: 10 chunks (10 lines starting with ##).

```bash
grep "^---$" /home/corby/jamm-os/knowledge/13_reports_analytics.md | wc -l
```

Expected: 9 separators.

If any check fails, report what was found. Do not self-correct silently.

---

## GIT

```bash
cd /home/corby/jamm-os
git add knowledge/13_reports_analytics.md
git commit -m "knowledge: add 13_reports_analytics.md - 10 chunks"
```

Note: push is blocked by GitHub account suspension. Commit locally only.