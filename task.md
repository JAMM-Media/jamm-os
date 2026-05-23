== STANDING RULES — ENFORCE ALWAYS ==

Project: JAMM PX
Frontend only. No backend changes. No migration. No restart.
All files start with a path comment.
Never use && to chain commands — run them sequentially.
TypeScript must pass clean before committing.

== TASK: Restructure Templates deleted tab ==

Currently the Tax Organizers sub-tab has an Active/Deleted
toggle inline. This task moves deleted templates to a
proper top-level fourth sub-tab in the Templates page,
with its own three sub-sections for each template type.

Read this file in full before making any changes:
- frontend/src/app/(dashboard)/templates/page.tsx
- frontend/src/components/templates/TaxOrganizerTemplates.tsx

== FIX 1 — ADD DELETED AS A FOURTH SUB-TAB ==

File: frontend/src/app/(dashboard)/templates/page.tsx

Change the SUB_TABS array from:
  [
    { key: 'engagement', label: 'Engagement Templates' },
    { key: 'letters', label: 'Engagement Letters' },
    { key: 'tax_organizers', label: 'Tax Organizers' },
  ]

To:
  [
    { key: 'engagement', label: 'Engagement Templates' },
    { key: 'letters', label: 'Engagement Letters' },
    { key: 'tax_organizers', label: 'Tax Organizers' },
    { key: 'deleted', label: 'Deleted' },
  ]

Update the SubTab type to include 'deleted'.

When activeTab === 'deleted', render the DeletedTemplates
component (created below) instead of the existing content.

== FIX 2 — REMOVE ACTIVE/DELETED TOGGLE FROM TAX
ORGANIZER TEMPLATES COMPONENT ==

File: frontend/src/components/templates/TaxOrganizerTemplates.tsx

Read the file first. Find the Active/Deleted toggle that
currently exists inside this component. Remove it entirely
— the deleted view now lives in the top-level Deleted tab.

The component should only show active templates
(is_active=true). Remove any state or logic related to
showing deleted templates from this component.

== FIX 3 — CREATE DELETED TEMPLATES COMPONENT ==

Create:
frontend/src/components/templates/DeletedTemplates.tsx

This component renders inside the Deleted sub-tab of the
Templates page.

LAYOUT:
- Three internal sub-tabs across the top:
  "Engagement Templates" | "Tax Organizers" |
  "Engagement Letters"
- Active internal sub-tab: 2px border-bottom brand color
- Default active: "Engagement Templates"

ENGAGEMENT TEMPLATES DELETED SUB-TAB:
Fetch from GET /engagement-templates/?active_only=false
or GET /engagement-templates/ — check what the existing
endpoint accepts. Filter client-side for is_active=false
templates.

Each deleted template row:
- Template name — 13px weight 500 muted (#9CA3AF)
- Engagement type badge if set — muted opacity
- Deleted indicator — small red "Deleted" pill
- "Restore" button — ghost style, brand color text
  On click: PATCH /engagement-templates/{id} with
  { is_active: true }
  On success: toast "Template restored", remove from list

Empty state: "No deleted engagement templates"

TAX ORGANIZERS DELETED SUB-TAB:
Fetch from GET /tax-organizers/templates
Filter client-side for is_active=false templates.

Each deleted template row:
- Template name — 13px weight 500 muted
- Organizer type badge — muted
- Default badge if is_default — muted
- "Restore" button — PATCH /tax-organizers/templates/{id}
  with { is_active: true }
  On success: toast "Template restored", remove from list

Empty state: "No deleted tax organizer templates"

ENGAGEMENT LETTERS DELETED SUB-TAB:
Check if LetterTemplatesTab has soft delete support.
If not, show a simple message:
"Engagement letter templates cannot be deleted."

STYLING:
- Page bg: bg-surface-page dark:bg-dark-page
- Each row: bg-surface-card dark:bg-dark-card rounded-[8px]
  p-3 flex items-center justify-between
- All text muted to signal deleted state
- Restore button: text-brand dark:text-[#4A7FA5]
  border border-surface-border dark:border-dark-border
  rounded-[6px] px-3 py-1.5 text-[12px]
  hover:bg-surface-card dark:hover:bg-dark-card

== VERIFY ==

1. List every file created or modified
2. Confirm Templates page has four top-level sub-tabs
3. Confirm Tax Organizers sub-tab no longer has
   Active/Deleted toggle
4. Confirm Deleted tab has three internal sub-tabs
5. Confirm restore works for both template types
6. Run npx tsc --noEmit — fix all errors
7. git add .
   git commit -m "restructure deleted templates into
   top-level tab with sub-sections"
   git push

No backend changes. No migration. No droplet restart.