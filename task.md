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

TASK: Prompt coverage audit -- 7 new sections

Pre-task:
cd /home/corby/jamm-os
git add -A && git commit -m "checkpoint before prompt coverage audit"

VERIFY BEFORE ACT:
grep -n "PORTAL ADOPTION SEQUENCE\|TERMINOLOGY RULES" /home/corby/jamm-os/app/api/concierge/prompts.py
Paste output before touching anything.

---

Change 1: Insert 7 new workflow sections between PORTAL ADOPTION SEQUENCE and TERMINOLOGY RULES

Find exactly:
---
TERMINOLOGY RULES

Replace with:
---
DOCUMENT REQUESTS

A document request is a checklist sent to a client asking them to upload specific files through their portal. Each request belongs to one engagement.

How to create and send a document request:
1. Navigate to Clients > [Client Name] > Engagements > [Engagement Name].
2. Select the Document Requests tab inside the engagement.
3. Select New Request.
4. Enter a title (e.g. "2024 Tax Return Documents").
5. Add checklist items. Each item has a label, an optional description, and a required or optional flag.
6. Set a due date. This is shown to the client on their portal.
7. Select Send. The client receives an email with a link to their portal.

Checklist item statuses: pending (not yet uploaded), uploaded (client uploaded but staff has not reviewed), approved (staff marked as accepted), rejected (staff marked as unacceptable -- client must re-upload).

Overall request statuses:
- pending: no items uploaded yet.
- partial: some items uploaded or approved, but not all required items are done.
- complete: all required items are approved.

The request status rolls up automatically from item statuses. Staff do not set it manually.

Prerequisites before sending: the client must have an email address on their record, and portal access must be enabled. If the client has not received a magic-link yet, send one first from the Portal tab on their client record.

Reminder emails: JAMM PX tracks reminder count and last reminder sent date per request. Use the automation presets to trigger automatic reminders when a document request is overdue.

<document_request_qa>
  <qa>
    <q>Why did my client not receive the document request email?</q>
    <a>Check two things: the client must have an email address on their record, and portal access must be enabled. Go to the client profile and confirm both. If both are set, check the client's spam folder.</a>
  </qa>
  <qa>
    <q>How do I mark a document as approved?</q>
    <a>Open the document request inside the engagement. Find the checklist item and change its status to approved. Once all required items are approved the request status automatically updates to complete.</a>
  </qa>
  <qa>
    <q>Can I add items to a document request after sending it?</q>
    <a>Yes. Open the request and edit the checklist. The client will see the updated checklist on their next portal visit. Consider sending a manual reminder so they know new items were added.</a>
  </qa>
  <qa>
    <q>What happens when a client uploads a file I rejected?</q>
    <a>The item status resets to uploaded when the client re-uploads. Review the new file and approve or reject it again.</a>
  </qa>
</document_request_qa>
---
SIGNATURE ENVELOPES

A signature envelope is an e-signature request sent to a client via Dropbox Sign. It tracks the full lifecycle of a signing request.

Statuses: draft (created but not sent), sent (delivered to signer), completed (all parties signed), declined (signer declined), expired (signing window closed), cancelled (firm cancelled).

How to send a signature envelope:
1. Navigate to Clients > [Client Name] > Engagements > [Engagement Name].
2. Select the Signatures tab inside the engagement.
3. Select New Signature Request.
4. Upload or select the document to be signed.
5. Add signers -- each signer needs a name and email address.
6. Add a subject line and optional message to the signer.
7. Send. The signer receives an email from Dropbox Sign with a link to review and sign.

Once all signers complete signing, the completed signed PDF is automatically attached to the engagement. The envelope status updates to completed via webhook.

Reminders: JAMM PX tracks reminder count and last reminder date per envelope. Manual reminders can be sent from the envelope detail view.

Dropbox Sign must be connected under Settings > Integrations before any signature envelope can be sent. If the firm has not connected Dropbox Sign, direct them there first.

<signature_envelope_qa>
  <qa>
    <q>My client says they never received the signature request email.</q>
    <a>Check the signer email address on the envelope. If it is correct, ask the client to check their spam folder -- Dropbox Sign emails sometimes land there. You can also resend from the envelope detail view.</a>
  </qa>
  <qa>
    <q>How do I cancel a signature request I already sent?</q>
    <a>Open the envelope inside the engagement and select Cancel. The status updates to cancelled and the signer link becomes invalid. You will need to create a new envelope if signing is still required.</a>
  </qa>
  <qa>
    <q>Where does the signed document go after everyone signs?</q>
    <a>The completed signed PDF is automatically attached to the engagement under Documents. The envelope status updates to completed.</a>
  </qa>
</signature_envelope_qa>
---
TAX ORGANIZERS

A tax organizer is a structured questionnaire sent to a client to collect their tax information before the engagement begins. JAMM PX includes three default templates: Individual (1040), Business (1120/1065/1120S), and Rental Property.

Templates define the structure: sections containing questions. Question types: text, number, boolean, select, textarea. Each question can be marked required or optional.

How to send a tax organizer:
1. Navigate to Clients > [Client Name] > Engagements > [Engagement Name].
2. Select the Tax Organizers tab inside the engagement.
3. Select Send Organizer.
4. Choose a template (Individual, Business, Rental, or a custom template).
5. Set the tax year.
6. Add an optional message to the client.
7. Send. The client sees the organizer in their portal and can fill it out and submit.

Organizer statuses:
- sent: delivered to portal, client has not started.
- in_progress: client has saved at least one answer.
- submitted: client has clicked Submit and all required questions are answered.

Firms can create custom templates under Settings > Tax Organizers > New Template. Custom templates can have any section and question structure. The three default templates can also be edited.

<tax_organizer_qa>
  <qa>
    <q>How do I see what my client answered on their tax organizer?</q>
    <a>Open the engagement and select the Tax Organizers tab. Open the organizer to see all responses by section and question.</a>
  </qa>
  <qa>
    <q>My client submitted their organizer but I need them to add more information.</q>
    <a>Tax organizers are locked after submission. Send the client a message through the portal or a document request for the additional items. Alternatively, create a new organizer with only the missing questions if your custom template supports it.</a>
  </qa>
  <qa>
    <q>Can I create my own tax organizer template?</q>
    <a>Yes. Navigate to Settings > Tax Organizers > New Template. Add sections and questions in any structure you need. Custom templates are available when sending organizers from any engagement.</a>
  </qa>
</tax_organizer_qa>
---
TIME ENTRIES

Time entries track billable and non-billable hours worked on an engagement. Each entry belongs to one engagement and one staff member.

Fields on a time entry: description, hours, hourly rate, date, billable flag, activity type, start time (optional), end time (optional).

Statuses:
- Unsubmitted: draft entry, only visible to the staff member who created it.
- Submitted: sent to manager for approval.
- Approved: manager has approved. Approved entries can be added to an invoice.
- Billed: entry has been included on an invoice.

If the firm has timesheet approval enabled (Settings > Team > Timesheet Approval), staff must submit entries for manager approval before they can be billed. If approval is disabled, entries can be billed directly.

How to log a time entry:
1. Navigate to the engagement.
2. Select the Time tab.
3. Select New Entry.
4. Fill in description, hours, hourly rate, date, and billable flag.
5. Save. Submit if timesheet approval is required.

How to add time entries to an invoice:
1. Create a new invoice for the client.
2. On the invoice, select Add Time Entries.
3. Select the approved, unbilled entries to include.
4. The entries are added as line items and marked as billed.

Editing after submission: if a staff member edits an entry after submitting it, the entry is flagged as edited after submission and an edit note is required. The manager sees the flag during approval.

<time_entry_qa>
  <qa>
    <q>Why can I not add a time entry to an invoice?</q>
    <a>Time entries must be approved before they can be billed. If timesheet approval is enabled, the entry needs manager approval first. Check the entry status -- if it shows submitted, a manager needs to approve it.</a>
  </qa>
  <qa>
    <q>How do I see all unbilled hours across the firm?</q>
    <a>Navigate to Timesheets from the left sidebar. Filter by billable and unbilled to see all entries that have not yet been invoiced across all engagements.</a>
  </qa>
  <qa>
    <q>A staff member submitted a time entry with the wrong hours. Can it be fixed?</q>
    <a>Yes. The staff member can edit the entry after submission. The entry will be flagged as edited and an edit note is required. The manager will see the flag when reviewing.</a>
  </qa>
</time_entry_qa>
---
BILLING AND INVOICES

Invoices in JAMM PX are created per client and can be linked to an engagement. Payment is collected via Stripe. Stripe must be connected before any invoice can be sent for online payment.

Invoice statuses: draft (created, not sent), sent (delivered to client), paid (payment received), overdue (past due date, not paid), void (cancelled).

Line items: invoices support manual line items and time entry line items. Time entries added to an invoice are automatically marked as billed.

How to create and send an invoice:
1. Navigate to Billing in the left sidebar, or to the client record > Billing tab.
2. Select New Invoice.
3. Select the client and optionally link to an engagement.
4. Add line items manually or select Add Time Entries to pull in approved unbilled time.
5. Set a due date.
6. Add internal notes (not visible to client) and client-visible notes if needed.
7. Select Send. The client receives an email with a link to view and pay the invoice in their portal.

Delivery methods: portal (client pays online via Stripe) or manual (firm records payment offline).

Stripe fees: Stripe charges a transaction fee on every payment processed. JAMM PX does not add any additional transaction fees. The Stripe fee is separate from the JAMM PX subscription cost.

Tax rate: invoices support a tax rate field. Tax amount is calculated automatically.

Refunds and voids: to cancel an invoice, void it. Voids cannot be undone. For refunds on paid invoices, process the refund directly in Stripe -- JAMM PX will reflect the updated status via webhook.

<billing_qa>
  <qa>
    <q>How do I connect Stripe?</q>
    <a>Navigate to Settings > Billing > Connect Stripe. Complete the Stripe Connect OAuth flow. Once connected, invoices can be sent for online payment.</a>
  </qa>
  <qa>
    <q>My client says they paid but the invoice still shows as sent.</q>
    <a>Payment status updates via Stripe webhook. Check the Stripe dashboard to confirm the payment was processed. If it was, the webhook may have been delayed -- the status should update within a few minutes. If it does not update, contact support.</a>
  </qa>
  <qa>
    <q>Can I send an invoice without Stripe connected?</q>
    <a>Yes. Set the delivery method to manual. The client will not receive a payment link but you can record the payment manually when it arrives and mark the invoice as paid.</a>
  </qa>
  <qa>
    <q>How do I add time entries to an invoice?</q>
    <a>When creating or editing a draft invoice, select Add Time Entries. This shows all approved unbilled time entries for that client. Select the ones to include and they are added as line items.</a>
  </qa>
</billing_qa>
---
CLIENT PORTAL EXPERIENCE

The client portal is a separate interface clients use to interact with their firm. Clients access it via magic-link (passwordless) or password if they set one. Magic-links expire after 72 hours.

What clients see in the portal:
- Engagements: engagement name, status, and notes_client_visible only. Internal notes are never shown to clients.
- Document requests: checklist items to upload, with labels, descriptions, due dates, and item statuses.
- Documents: files uploaded by the firm or by the client.
- Invoices: outstanding and paid invoices. Online payment via Stripe if connected.
- Tax organizers: questionnaires to fill out and submit.
- Messages: direct messages from the firm.

What clients cannot see: internal engagement notes, staff assignments, hourly rates, time entries, internal billing notes, or any data belonging to other clients.

How to send a magic-link:
1. Navigate to Clients > [Client Name] > Portal tab.
2. Select Send Magic-Link.
3. The client receives an email with a secure link valid for 72 hours.

How to revoke portal access:
Navigate to Clients > [Client Name] > Portal tab > Revoke Access. The client's active sessions are terminated immediately.

Portal password: clients can set a password from the portal settings page after first login. Once set, they can log in with email and password instead of a magic-link.

Common portal issues:
- Client cannot log in: magic-link may have expired. Send a new one from the Portal tab.
- Client does not see a document request: confirm the request was sent (not just saved as draft) and that the client is logged into the correct portal account.
- Client cannot pay an invoice: confirm Stripe is connected and the invoice delivery method is set to portal.

<portal_qa>
  <qa>
    <q>How do I know if my client has logged into their portal?</q>
    <a>Navigate to the client record > Portal tab. The last login date is shown there. You can also see portal login activity in the engagement timeline.</a>
  </qa>
  <qa>
    <q>My client says the magic-link is not working.</q>
    <a>Magic-links expire after 72 hours. Send a new one from the client record > Portal tab > Send Magic-Link. Also check that the client is opening the most recent link -- older links become invalid when a new one is sent.</a>
  </qa>
  <qa>
    <q>Can two clients share the same email address?</q>
    <a>No. Each client record requires a unique email address. Portal access is tied to the email address. If two clients share an email, one must use a different address.</a>
  </qa>
</portal_qa>
---
ERROR STATES AND WHAT TO DO

These are the most common error states firms encounter and how to resolve them.

Document request not delivered: client has no email address, or portal access is not enabled. Go to the client profile and check both.
Magic-link not received: check spam folder. Resend from Portal tab. Confirm the email address on the client record is correct.
QuickBooks import client skipped: four reasons -- no email, duplicate email, inactive in QuickBooks, sub-customer. Fix in QuickBooks and re-import.
Invoice not updating to paid after Stripe payment: webhook delay -- wait a few minutes. If still not updated, check Stripe dashboard for the payment status.
Signature request not received: check signer email on the envelope. Ask client to check spam. Resend from envelope detail view.
Staff cannot log in: check that the staff invitation was accepted. If not, resend the invitation from Settings > Team.
Time entry cannot be added to invoice: entry must be approved first. If timesheet approval is enabled, a manager must approve it.
Automation preset not firing: confirm the preset is enabled under Settings > Automations. Check that the trigger condition has been met. Some presets require specific engagement statuses or due dates to be set.
Client sees wrong engagement notes: only notes_client_visible are shown in the portal. Internal notes are never visible. Check which field the notes were entered in.
---
TERMINOLOGY RULES