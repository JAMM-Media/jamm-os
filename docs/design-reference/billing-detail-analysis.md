# Billing Detail -- Visual Analysis

*Mock file: docs/design-reference/billing-detail-mock.png*
*Analyzed: 2026-08-28*

## Page header

- Title: "Billing Detail" -- 20px bold, color #1F3148 (established primary text)
- Subtitle: "A breakdown of the services and charges billed to you." -- 13px, color #6B7280 (established muted)

## Stat card strip

Three cards in a 3-column grid. Each card follows the established stat card standard from portal-design-tokens.md exactly (px-5 py-4, icon left w-10 h-10 rounded-lg, text right with 11px label / 24px value).

### Card 1 -- Total billed this year

- Value shown in mock: $8,750.00
- Icon: Receipt (lucide)
- Badge background: #D1FAE5 (established success green)
- Icon color: #059669 (established success icon)

### Card 2 -- Average per engagement

- Value shown in mock: $1,458.33
- Icon: TrendingUp (lucide)
- Badge background: #DBEAFE (established informational blue)
- Icon color: #1E40AF (established informational icon)

### Card 3 -- Total hours this year

- Value shown in mock: 72.50
- Icon: Clock (lucide)
- Badge background: #EDE9FE (violet-100 -- new token, see below)
- Icon color: #7C3AED (violet-600 -- new token, see below)

### INTENTIONAL EXCLUSION: "View details" links

The mock shows "View details ->" links beneath each stat card value. These are intentionally excluded from this build. Reason: no settled destination exists for what those links would navigate to, and the backend does not expose a drill-down endpoint per stat category. Showing a link that goes nowhere, or inventing a destination that does not exist in the real system, would be a worse user experience than a static card. The honest choice is static summary cards. The established portal pattern on PortalInvoices.tsx does include "View all" links that trigger real filter state changes -- but the Billing Detail stat cards have no equivalent filter state to drive.

## Main content table

Single white card (bg-white, rounded-xl, border border-gray-100) containing the full engagement table.

### Column header row

- Background: #F9FAFB (Tailwind gray-50, one step lighter than pure white)
- Border-bottom: #F3F4F6 (established card border)
- Column labels: "Engagement" | "Description" | "Line total"
- Typography: 11px, font-semibold, uppercase tracking-wide, color #9CA3AF (established tertiary)
- Column proportions estimated from mock: engagement col ~35%, description ~45%, line-total ~20% (implemented as 2fr / 3fr / 148px fixed)

### Engagement header rows

Each engagement (invoice) has a collapsible header row:

- Background: #F9FAFB (same shade as column header, distinguishes header rows from line items)
- Hover: slightly darker (#F3F4F6), via Tailwind hover:bg-gray-100
- Far left: single ChevronRight (collapsed) or ChevronDown (expanded) -- size 14px, color #9CA3AF (established tertiary)
- Engagement name: 13px font-medium, color #1F3148
- "Billed on [date]": 11px, color #6B7280, stacked below engagement name in the same cell
- Right side: aggregate hours ("X.XX hrs") in 11px #6B7280, then "Subtotal $X,XXX.XX" in 13px font-medium #1F3148, stacked vertically
- No second chevron anywhere on the row, no boxed control, no "View details" link

### INTENTIONAL CORRECTION: per-line "View detail"/"Hide detail" toggle

The mock shows a "View detail" link on each line item row. When clicked in the mock, it reveals an Hours column and re-labels the Line total. This behavior cannot be built as shown because hours data exists only in the TimeEntry table, aggregated at the invoice level via invoice_id foreign key -- there is no hours field on individual JSON line items. Building the per-line toggle would require fabricating hours values that do not exist in the database. The honest substitution: real aggregate hours (sum of time_entries.hours for each invoice) appear on the engagement header row next to the subtotal. Line items show description and line total only, with no expand affordance of any kind.

### Line item rows (revealed when engagement is expanded)

- Background: #FFFFFF
- Border-top: #F3F4F6 (established card border)
- Left column (engagement cell): blank -- the chevron area is empty for line items
- Description: 13px, color #6B7280 (muted, matching mock)
- Amount: 13px, color #1F3148 (primary), right-aligned
- No "View detail" link, no Rate column, no Hours column, no staff name

### Grand total row

- Border-top: 2px solid #E5E7EB (slightly heavier than internal borders to visually anchor the total; this border weight is new but the color matches Tailwind gray-200 which is the established top-bar bottom border)
- Label: "Grand total (N engagements)" -- 13px font-semibold, color #1F3148
- Amount: 13px font-semibold, color #1F3148, right-aligned

## New design tokens

Two new tokens added to portal-design-tokens.md:

- **Billing hours badge background**: #EDE9FE (Tailwind violet-100)
- **Billing hours badge icon color**: #7C3AED (Tailwind violet-600)

Reason: no existing purple or violet chip color exists in portal-design-tokens.md. The Total hours this year stat card requires a third visually distinct color. The established pair (green for money/success, blue for informational) does not include a time/duration signal. Violet reads as "time" without conflicting with either existing badge color. Violet-100 / violet-600 follows the same lightness pattern as the other badge pairs (light bg / saturated icon).

## Top three remaining discrepancies vs the mock

1. **Stat card links missing**: The mock shows "View details ->" beneath each stat value. The real build omits these. The visual weight of each card is slightly lighter as a result. This is an intentional, documented correction.

2. **Per-line hours toggle replaced**: The mock shows individual line-item expansion revealing per-line hours. The real build shows aggregate invoice-level hours on the engagement header row. This is a real data-model constraint -- no per-line hours exist in the database.

3. **Grand total parenthetical**: The mock shows "(3 engagements)" where "engagements" refers to the row count. In the real build, each row is one invoice (an engagement can have multiple invoices). The parenthetical in the real build shows the invoice count, labeled as "engagements" to match the mock vocabulary, but the count may differ from a strict distinct-engagement count if one engagement has multiple invoices.
