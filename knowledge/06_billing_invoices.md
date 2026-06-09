## Billing > Overview > What the Billing Module Is

The Billing module is where invoices are created, sent, tracked, and managed. Every invoice in JAMM PX is linked to a client and optionally to an engagement. The Billing module gives the firm a complete view of outstanding amounts, payment status, and billing history.

Navigate to Billing in the left sidebar to open the billing list.

---

## Billing > Overview > Invoice Statuses

Every invoice has one of five statuses.

Draft means the invoice has been created but not sent to the client. Draft invoices are not visible in the client portal. Edit and finalize an invoice while it is in draft before sending.

Sent means the invoice has been delivered to the client. The client can see it in their portal and pay it online.

Paid means the client has paid the invoice. JAMM PX records the paid date automatically when payment is received through Stripe or when a staff member manually marks the invoice as paid.

Overdue means the invoice due date has passed and it has not been paid. The overdue status is set automatically by the system.

Void means the invoice has been cancelled. A voided invoice cannot be edited or paid. Use void to cancel an invoice that should not be collected.

---

## Billing > Overview > Invoice Numbers

Every invoice has a unique invoice number. Invoice numbers are assigned automatically when the invoice is created. They appear on the invoice and in the billing list.

---

## Billing > Creating an Invoice > How to Create an Invoice

Navigate to Billing in the left sidebar and click New Invoice. Select the client the invoice is for. Optionally link the invoice to a specific engagement. Set the invoice number, line items, subtotal, tax rate, and due date.

The engagement link is optional. An invoice can be created for a client without being tied to a specific engagement.

---

## Billing > Creating an Invoice > Invoice Line Items

An invoice is made up of line items. Each line item has a description and an amount. The subtotal is the sum of all line items before tax. The tax rate is applied to the subtotal to calculate the tax amount. The total is the subtotal plus the tax amount.

Add as many line items as needed. Common line items for accounting firms include preparation fees, consultation fees, filing fees, and hourly charges.

---

## Billing > Creating an Invoice > Creating an Invoice from Time Entries

Invoices can be created directly from unbilled time entries logged against an engagement. This eliminates manual re-entry of hours and ensures billing reflects actual time worked.

Navigate to the engagement the time was logged against. Select the option to create an invoice from time entries. Choose the time entries to include. JAMM PX creates a draft invoice with those entries as line items. The time entries are marked as billed automatically.

Review the draft invoice and adjust as needed before sending.

---

## Billing > Creating an Invoice > Client-Visible Notes

An invoice has two notes fields. Internal notes are visible to staff only and never shown to the client. Client-visible notes appear on the invoice when it is sent and are visible in the client portal.

Use internal notes for billing context, fee justification, or reminders for the billing manager. Use client-visible notes for messages to the client such as payment instructions or scope clarifications.

---

## Billing > Sending an Invoice > How to Send an Invoice

An invoice must be in draft status before it can be sent. Open the invoice and click Send. JAMM PX delivers the invoice to the client according to the delivery method set on the invoice.

Delivery methods are email, portal, or both. Portal delivery makes the invoice visible in the client portal. Email delivery sends the client an email notification. Both sends the email and makes it visible in the portal.

Once sent, the invoice status changes from draft to sent and the sent date is recorded.

---

## Billing > Sending an Invoice > Bulk Sending Invoices

Select multiple draft invoices in the billing list using the checkboxes. With invoices selected, the bulk action toolbar appears. Click Send to send all selected invoices at once.

Bulk send only works on draft invoices. If any selected invoice is not in draft status the bulk send button will not be active for that selection.

---

## Billing > Collecting Payment > How Clients Pay Online

Clients pay invoices through the client portal. The invoice appears on the Invoices tab in the portal with a Pay Now button. Clicking Pay Now opens a Stripe payment form where the client enters their credit or debit card details.

When the payment is processed successfully, the invoice status updates to paid automatically and the paid date is recorded. The client sees the invoice marked as paid in their portal.

For Stripe payments to work, the firm must have a connected Stripe account. Navigate to Settings and connect Stripe before sending invoices for online payment.

---

## Billing > Collecting Payment > Marking an Invoice as Paid Manually

If a client pays by check, bank transfer, or any method outside of Stripe, mark the invoice as paid manually.

Open the invoice from the billing list. Click Mark as Paid. JAMM PX records the payment and changes the invoice status to paid. The paid date is set to the current date.

Use manual payment recording for any payment received outside the portal payment flow.

---

## Billing > Managing Invoices > Voiding an Invoice

Void an invoice when it needs to be cancelled. Open the invoice and click Void, or select invoices in the billing list and use the bulk void action.

A voided invoice cannot be edited, sent, or paid. The invoice remains in the billing list with void status for record-keeping purposes. Voiding is not the same as deleting.

---

## Billing > Managing Invoices > The Billing List

Navigate to Billing in the left sidebar to see all invoices across all clients. The list shows invoice number, client, engagement, amount, due date, and status.

The list supports two views: table view and card view. Filter by status, client, or engagement using the filter controls. Search by invoice number or client name using the search field. Sort by due date ascending or descending.

---

## Billing > Managing Invoices > The WIP Report

The WIP report shows unbilled time across all active engagements. WIP stands for work in progress. Navigate to Billing and select WIP Report.

The report shows each engagement with its client name, total hours logged, and the dollar value of unbilled time. Use the WIP report before month-end billing to identify work that has been done but not yet invoiced.

Export the WIP report to CSV using the Export CSV button in the top right corner.

---

## Billing > Managing Invoices > Overdue Invoice Tracking

An invoice becomes overdue automatically when its due date passes and it has not been paid. The status changes to overdue and the invoice appears in the overdue filter view.

The automation system can send overdue reminders automatically. The Invoice Overdue Reminder preset sends a payment reminder when an invoice first becomes overdue. The Invoice Overdue Escalating Sequence sends reminders on day one and day seven, then notifies the firm owner on day fourteen. See the Automation Presets module to enable these.

---

## Billing > Stripe Integration > Connecting Stripe

JAMM PX processes online payments through Stripe Connect. The firm must connect their Stripe account before clients can pay invoices online through the portal.

Navigate to Settings and open the Billing section. Click Connect Stripe and follow the Stripe onboarding flow. Once connected, the Pay Now button becomes active for sent invoices in the client portal.

---

## Billing > Stripe Integration > What Happens When a Client Pays

When a client clicks Pay Now and completes payment, Stripe processes the card charge and sends a webhook notification to JAMM PX. JAMM PX receives the webhook, marks the invoice as paid, and records the Stripe charge ID and payment date automatically. No staff action is required.

If a payment fails, the invoice remains in sent status and the client sees an error message in the portal. The client can retry with a different card.
