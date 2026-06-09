## Engagements > Overview > What an Engagement Is

An engagement is the core unit of work in JAMM PX. Every piece of billable or trackable work for a client lives inside an engagement. An engagement holds the name, type, status, assigned staff member, deadlines, tasks, document requests, time entries, and invoices for a single scope of work.

Engagements are also called jobs in TaxDome, work items in Karbon, and projects in some other practice management tools. In JAMM PX the term is always engagement.

Create a client record before creating an engagement. An engagement must be linked to a client and cannot exist without one.

---

## Engagements > Overview > Engagement Types

JAMM PX supports the following engagement types. Select the type that matches the work when creating an engagement.

Tax return types: 1040 for individual returns, 1120 for C-corporations, 1120-S for S-corporations, 1065 for partnerships, 1041 for trusts and estates, 706 for estate tax, and 1040-X for amended returns.

Extension types: 4868 for individual extensions and 7004 for business extensions.

Other types: payroll tax 941, bookkeeping monthly, bookkeeping quarterly, tax planning and advisory, audit representation, other advisory, and custom.

Selecting a tax return or extension type causes JAMM PX to populate the filing deadline automatically based on IRS deadlines. You can override the auto-populated date if an extension or a custom deadline applies.

---

## Engagements > Overview > Engagement Statuses

Every engagement has one of six statuses. Each status represents a defined stage in the work lifecycle.

Draft means the engagement has been created but work has not started. Use draft for engagements that are planned or pending client confirmation. A draft engagement is visible to staff but not surfaced to clients.

Active means work is currently in progress. This is the primary working status. Most engagements spend the majority of their lifecycle in active.

In Review means the work is complete and is waiting for a quality check, partner review, or manager approval before the engagement can be marked completed. Use in review when your firm requires a second set of eyes before filing or delivering.

Completed means the work is finished and delivered. The engagement is closed. Invoices can still be created against a completed engagement.

Acknowledged means the firm has confirmed the completed engagement with the client. Some firms use acknowledged as a post-completion confirmation step. Others skip it and move directly from completed to archived.

Archived means the engagement is no longer active and is removed from the standard working view. Archived engagements remain in the system and can be searched. Archiving is not deletion.

---

## Engagements > Creating an Engagement > How to Create an Engagement

Navigate to Engagements in the left sidebar and select New Engagement. You can also create an engagement from a client record by opening the client, selecting the Engagements tab, and clicking New Engagement.

Three fields are required before the engagement will save: the client, the engagement title, and the type. If you select Tax Return, Bookkeeping, or Payroll as the type, a subtype field appears and is also required before saving.

Optional fields at creation: end date. All other fields including status, start date, assigned staff, deadlines, notes, and complexity flags can be set after the engagement is created.

The engagement is created in draft status by default. Change the status to active when work begins.

---

## Engagements > Creating an Engagement > Engagement Title Conventions

The engagement title is a free text field. JAMM PX does not enforce a naming convention but a consistent format across your firm makes filtering and reporting more useful.

A common convention is: tax year, return type, and entity name. For example: 2024 1040 Patricia Nguyen or 2024 1065 Riverside Plumbing. For bookkeeping: 2024 Bookkeeping Monthly Riverside Plumbing.

The title appears in the engagement list, task views, document requests, invoices, and client portal. A clear title helps staff identify the engagement without opening it.

---

## Engagements > Creating an Engagement > Setting Deadlines

An engagement has two deadline fields: filing deadline and extended deadline.

Filing deadline is the standard IRS or statutory due date. For tax return types, JAMM PX populates this automatically when you select the engagement type. You can edit the auto-populated date.

Extended deadline is used when an extension has been filed. Enter the extended due date here. The morning briefing and deadline tracking use the extended deadline when it is present and the filing deadline when it is not.

Navigate to the engagement detail page and select Edit to set or change either deadline.

---

## Engagements > Creating an Engagement > Assigning Staff

An engagement can be assigned to one staff member. Navigate to the engagement detail page and select Edit. The assigned staff field accepts any active staff member on the firm.

The assigned staff member sees the engagement in their personal task view alongside their assigned tasks. The engagement list can be filtered by assigned staff.

If no staff member is assigned the engagement is visible to all staff with access to the Engagements module. Assigning staff is optional but recommended for firms with multiple preparers.

---

## Engagements > Engagement Templates > What Templates Are

An engagement template is a reusable starting configuration for a common engagement type. A template can include a pre-set task list, document request checklist, engagement type, and default status.

When you create an engagement from a template, the template copies its tasks and document requests into the new engagement. The client, deadlines, and staff assignment are set at creation time and are not part of the template.

Templates save time for engagement types your firm creates repeatedly such as 1040 returns, monthly bookkeeping, or quarterly payroll.

---

## Engagements > Engagement Templates > How to Create a Template

Navigate to Engagements in the left sidebar and select Templates. Click New Template. Give the template a name, select the engagement type, and add the tasks and document request items you want pre-populated.

Save the template. It becomes available as an option in the New Engagement flow under the Use Template option.

---

## Engagements > Engagement Templates > How to Create an Engagement from a Template

Navigate to Engagements and click New Engagement. Select Use Template and choose the template. Set the client, title, and deadlines. The template tasks and document request items are copied into the new engagement automatically.

You can add, edit, or remove the copied tasks and items after the engagement is created. The template itself is not modified.

---

## Engagements > Recurring Engagements > How Recurring Engagements Work

A recurring engagement is created automatically by JAMM PX on a defined schedule. You set up the recurrence on a template, not on individual engagements.

When the scheduled date arrives, JAMM PX spawns a new engagement for every active client associated with the recurring template. The spawned engagement copies the template tasks and document request items. No manual action is required from the firm owner or staff.

Recurring engagements are useful for monthly bookkeeping, quarterly payroll, and annual returns where the same work repeats on a predictable schedule.

---

## Engagements > Recurring Engagements > Setting Up a Recurring Template

Navigate to Engagements and select Templates. Create a new template or open an existing one. Enable the recurring option. Set the cadence to monthly, quarterly, or annually.

For monthly recurrence, set the day of the month the engagement should spawn. For quarterly recurrence, set the day and JAMM PX spawns on that day in January, April, July, and October. For annual recurrence, set the day and month.

Set the advance days field to control how far ahead of the due date the engagement is created. For example, setting advance days to 30 spawns the engagement 30 days before the deadline so staff have preparation time.

Save the template. JAMM PX begins spawning on the next matching date.

---

## Engagements > Recurring Engagements > What Happens When a Recurring Engagement Spawns

When the scheduled date arrives, JAMM PX creates a new engagement for each active client under the recurring template. The engagement starts in draft status. Staff receive a notification that a new recurring engagement is ready for review.

JAMM PX logs each spawn event so it does not create duplicate engagements if the process runs more than once on the same day. One engagement per client per period is enforced automatically.

Change the spawned engagement status to active when work begins. Edit the deadlines and assigned staff as needed for that specific period.

---

## Engagements > Managing Engagements > Moving an Engagement Through Statuses

Change an engagement status by opening the engagement detail page and selecting the status field. Select the new status from the list.

The typical flow for a tax return engagement is: draft when created, active when work begins, in review when the return is ready for partner sign-off, completed when the return is filed, acknowledged when the client confirms receipt, and archived at year end.

Not every status is required. A small firm without a formal review step may move directly from active to completed. Use the statuses that reflect your actual workflow.

---

## Engagements > Managing Engagements > Completing an Engagement

Set the engagement status to completed when all work is finished and delivered. JAMM PX records the completion date automatically.

After completing an engagement, open the engagement and verify that all tasks are marked done, all document request items are resolved, and all billable time is invoiced. Completed engagements remain in the main list until archived.

---

## Engagements > Managing Engagements > Reopening an Engagement

Change the engagement status from completed back to active to reopen it. Navigate to the engagement detail page, select Edit, and change the status field.

Reopening an engagement does not restore previously closed tasks or document request items automatically. Add new tasks or items as needed for the additional work.

---

## Engagements > Managing Engagements > Archiving an Engagement

Set the engagement status to archived to remove it from the active working view. Archived engagements are filtered out of the default engagement list but remain in the system.

To view archived engagements, apply the archived status filter on the Engagements list.

Archive engagements at the end of a tax season or when the work is fully complete and no further action is expected. Archiving keeps the working list focused on current work.

---

## Engagements > Managing Engagements > Adding Internal Notes

Open the engagement detail page and locate the Notes field. Internal notes are visible to firm staff only. They never appear in the client portal and are not shared with clients.

Use internal notes for preparer instructions, review comments, or context about the client situation that staff need to know.

---

## Engagements > Managing Engagements > Adding Client-Visible Notes

Open the engagement detail page and locate the Client Notes field. Client-visible notes appear in the client portal under the engagement. Use this field for status updates or instructions you want the client to see.

Internal notes and client-visible notes are separate fields. Content in the internal notes field is never shown to clients regardless of portal settings.

---

## Engagements > WIP Report > What the WIP Report Shows

The WIP report shows unbilled time entries across all active engagements. WIP stands for work in progress. The report displays each engagement with its client name, total hours logged, and the dollar value of those hours based on staff billing rates.

The WIP report helps identify completed or in-progress work that has not yet been invoiced. Review it before month-end billing runs.

Navigate to Billing in the left sidebar and select WIP Report.

---

## Engagements > WIP Report > Exporting the WIP Report

Navigate to Billing and select WIP Report. Click Export CSV in the top right corner. The file downloads with columns for client, engagement, hours, and value.

Use the export for billing review in external tools or to share with a billing manager.

---

## Engagements > Complexity Flags > What Complexity Flags Are

Complexity flags are markers on an engagement that indicate the engagement involves work beyond the standard scope for its type. Examples include cryptocurrency holdings, K-1 income, foreign accounts, or multiple state filings.

Complexity flags feed into the fee schedule model when it is configured. They allow JAMM PX to calculate a suggested fee that reflects the actual scope of the work rather than a flat rate.

Set complexity flags on the engagement detail page under the complexity section.

---

## Engagements > E-Filing > Recording a Filed Return

When a return is e-filed, you can record the IRS confirmation number on the engagement. Open the engagement detail page and locate the e-filing section. Enter the confirmation number and the filed date.

JAMM PX records the efiled_at timestamp automatically when the confirmation number is saved. The filing status is visible on the engagement detail and in the engagement list.

IRS acknowledgment file parsing from .ack files is also supported. See the IRS Authorizations module for details on authorization tracking.
