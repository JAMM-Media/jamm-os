# Invoices Page Mock Analysis

Source: docs/design-reference/invoices-mock.png
Design tokens reference: docs/design-reference/portal-design-tokens.md

## Layout structure

The mock uses the old dark theme (dark navy sidebar, dark card backgrounds). This analysis
maps its structural intent to the established light theme using portal-design-tokens.md.

Left sidebar: standard navigation (not rebuilt -- handled by PortalShell).
Content area: page heading, stat strip, filter row, invoice table.

## Stat strip

Four cards in a horizontal row, each with:
- Small icon chip on the left (colored circle, ~36px)
- Label (muted, ~12px)
- Value (primary text, ~20px bold)
- "View all" link at bottom (Ben confirmed: calmer style, lowercase "View all", no arrow)

Stat card mapping:
1. Open invoices -- count of sent + overdue invoices
   Icon: FileText, chip bg `#DBEAFE`, icon color `#1E40AF` (informational blue from tokens)
   
2. Total due -- sum of total_amount for sent + overdue
   Icon: DollarSign, chip bg `#FEF3C7`, icon color `#D97706` (amber warning from tokens)
   
3. Paid total -- sum of total_amount for paid invoices
   Note: backend PortalInvoice type does not expose paid_at, so "this year" is not
   computable from frontend data. Label changed to "Paid (total)" to be honest.
   Icon: CheckCircle2, chip bg `#D1FAE5`, icon color `#059669` (success green from tokens)
   
4. Total invoices -- count of all non-draft invoices
   Icon: Receipt, chip bg `#F3F4F6`, icon color `#6B7280` (icon chip bg from tokens)
   The mock uses a calendar icon here, which does not represent a count well.
   Receipt is a better topic match. Ben confirmed: use real judgment.

## Filter row

Left: "All invoices" heading (14px semibold, `#1F3148`).
Right: "All statuses" dropdown -- a real native select element, not tabs.
Options: All statuses, Due, Overdue, Paid, Draft, Void.

## Invoice table

White card, rounded-xl, border-gray-100, overflow-hidden.
Column headers: Invoice #, Description, Amount, Due date, Status, Action.
Row padding: p-4 on each cell, border-b between rows.
Alternating: no alternating background -- plain white rows.

Description column: first line item description (or "Multiple items" if more than one,
or "Invoice" if no line items).

Status badge mapping to tokens:
- Paid: bg `#D1FAE5`, text `#065F46` (Completed/success pill)
- Due (sent): bg `#FEF3C7`, text `#92400E` (Due soon / amber warning pill)
- Overdue: bg `#FEE2E2`, text `#991B1B` (Overdue pill)
- Draft: bg `#F3F4F6`, text `#9CA3AF` (neutral/tertiary)
- Void: bg `#F3F4F6`, text `#9CA3AF` (neutral/tertiary)

Action column:
- Unpaid (sent or overdue): "Pay now" button, navy bg `#1F3148`, white text, rounded-md
- Paid: "View" button (outline), triggers PDF download
- Three-dot menu on every row

Three-dot menu (MoreHorizontal icon):
- Download PDF: REAL. Fetches `/api/backend/portal/invoices/{id}/pdf` with auth header,
  triggers browser download. Uses weasyprint-based render_invoice_to_pdf confirmed real.
- Email a copy: NOT REAL. No portal-facing endpoint. Rendered disabled/grayed with
  "(coming soon)" label, matching the honest pattern used elsewhere this session.

## Empty state

Centered text: "No invoices yet." / "Invoices from your accountant will appear here."
Uses white card, rounded-xl, consistent with other pages.

## Pay Now behavior

Preserved exactly from existing component. POST to `/portal/invoices/{id}/pay`,
receives Stripe client_secret, expands inline Stripe card form (PaymentForm component).
Stripe integration already real and working. No changes to payment logic.

## New hex values (none genuinely new)

All status badge and stat chip colors derive directly from existing portal-design-tokens.md
status pill and icon chip values. No new hex values needed.

## Top three discrepancies not resolvable with confidence

1. "Paid this year" vs "Paid total": PortalInvoice frontend type has no paid_at field,
   so filtering by current year is not possible client-side. Shown as "Paid (total)".
   Fixable by adding paid_at to PortalInvoice interface and backend response -- flagged
   as a future data-shape improvement.

2. Table description column: PortalInvoice has line_items[] but no top-level description.
   Using first line item's description as a best approximation. If a firm uses invoice-level
   notes (notes_client_visible), those are not the same as a description and are not shown
   in the table (they appear in the PDF only).

3. Three-dot menu "Email a copy": no portal-facing endpoint exists. Shown as disabled.
   Requires a new backend endpoint that calls EmailService.send_invoice_email() scoped
   to the authenticated portal client's own invoice -- not built yet.
