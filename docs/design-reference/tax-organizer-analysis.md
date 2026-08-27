# Tax Organizer Mock Analysis

Source: docs/design-reference/tax-organizer-mock.png
Design tokens reference: docs/design-reference/portal-design-tokens.md

## Layout structure

The mock shows the section-overview state of a single opened organizer (not the year-list).
Two-column layout inside the content area:
- Left: progress card (full width), then "Organizer sections" heading + section list card (flex-1)
- Right: "Need help?" card + "Tip" card (w-[200px], flex-shrink-0)
Max content width approximately 880px.

## Progress card

Full-width white card, rounded-xl, border-gray-100, p-5.
Three horizontal areas in a flex row:

1. **Progress area** (flex-1):
   - Label: "Your progress" -- 12px, `#6B7280`
   - Sub-text: "4 of 5 sections complete" -- 14px medium, `#1F3148`
   - Progress bar: h-2, rounded-full, track `#F3F4F6`, fill amber `#F59E0B`
   - Percentage: "80%" -- 13px semibold, `#1F3148`

2. **Due date area** (min-w-[140px]):
   - Label: "Due date" -- 12px, `#6B7280`
   - Calendar icon: green, color `#10B981`
   - Date value: 13px, `#1F3148`
   - Days remaining: 12px, `#D97706` (amber warning, matches tokens)
   - **FINDING: No due_date field exists on TaxOrganizer or TaxOrganizerTemplate in the backend model. Rendered as "Not set" in this implementation.**

3. **View summary button** (flex-shrink-0, self-start):
   - h-9, px-4, rounded-lg, bg `#1F3148`, text white, 13px medium

## Section list

"Organizer sections" heading: 14px semibold, `#1F3148`, above the card.

White card, rounded-xl, border-gray-100, overflow-hidden.
Rows separated by border-b border-gray-100, last row has no border.
Each row is a clickable button:

- **Left icon chip** (w-8, h-8, rounded-full, flex-shrink-0):
  - Complete: bg `#D1FAE5`, icon color `#059669`, icon = Check
  - In progress: bg `#DBEAFE`, icon color `#2563EB`, icon = Clock
  - Not started: bg `#F3F4F6`, icon color `#9CA3AF`, icon = Minus

- **Title**: 13px medium, `#1F3148`
- **Description**: 12px, `#6B7280` (below title, if present)

- **Status label** (right side, 12px medium):
  - Complete: `#059669`
  - In progress: `#2563EB`
  - Not started: `#9CA3AF`

- **Chevron**: ChevronRight, 14px, `#9CA3AF`

Section completion is computed client-side from responses. No per-section status field exists in the backend response.

## Right panel

Two stacked white cards, rounded-xl, border-gray-100, p-4, w-[200px].

**"Need help?" card**:
- Heading: "Need help?" -- 13px semibold, `#1F3148`
- Body: 12px, `#6B7280`
- "Send a message" button: full-width, h-8, rounded-lg, border `#1F3148`, text `#1F3148`
- **FINDING: Button renders but is not yet wired to the portal messaging tab. Requires prop or router.push integration at the portal/page.tsx level.**

**"Tip" card**:
- Lightbulb icon in amber chip: bg `#FEF3C7`, icon color `#D97706`, w-6 h-6
- "Tip" label: 11px semibold, `#1F3148`
- Body: 11px, `#6B7280`

## Organizer list view (not in mock; inferred from system pattern)

White card, rounded-xl, border-gray-100, overflow-hidden.
Rows: year label (14px semibold `#1F3148`) + status pill + ChevronRight.
Status pill colors matching section status system:
- Submitted: bg `#D1FAE5`, text `#059669`
- In progress: bg `#DBEAFE`, text `#2563EB`
- Ready to complete: bg `#FEF3C7`, text `#D97706`

## Hex values added (not previously in portal-design-tokens.md)

All derived from existing token values where possible:
- Progress bar fill: `#F59E0B` (amber-400)
- Complete chip bg: `#D1FAE5` (matches tokens "Completed/success" pill bg)
- In progress chip bg: `#DBEAFE` (matches tokens "Later/informational" pill bg)
- Not started chip bg: `#F3F4F6` (matches tokens "Icon chip background")
- Complete icon + label color: `#059669` (matches tokens "Completed/success" pill text)
- In progress icon + label color: `#2563EB` (matches tokens "Later/informational" pill text)
- Not started icon + label color: `#9CA3AF` (matches tokens "Tertiary/faint text")
- Calendar icon (due date, complete color): `#10B981`
- Tip chip bg: `#FEF3C7` (matches tokens "Due soon / amber warning" bg)
- Tip icon color: `#D97706` (matches tokens "Amber warning text")

## Top three discrepancies not resolvable with confidence

1. **Due date field absent from backend**: The mock shows "May 30, 2021 / 20 days left." No `due_date` field exists on TaxOrganizer or TaxOrganizerTemplate. Requires a real schema addition plus a backend endpoint change. Rendered as "Not set" with a gray calendar icon in this implementation.

2. **In-progress section icon ambiguous**: At mock resolution the icon inside the blue chip for in-progress sections looks like either a clock, pencil, or progress indicator. Using `Clock` from lucide-react as the best match. Could be `PenLine` or `Edit` depending on semantic intent.

3. **"Send a message" routing not wired**: The mock implies this button opens the messaging feature. This implementation renders the button statically. Wiring it requires either a callback prop or access to the router at the portal/page.tsx level, which is outside the scope of this component rebuild.
