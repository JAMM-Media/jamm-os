# JAMM PX Client Portal — Design Tokens

Real, established values from the portal redesign (light theme + sidebar, committed this session). Reference this file instead of re-deriving colors from a mockup image each task — it prevents color drift across pages.

## Layout shell (PortalShell.tsx)
- Sidebar background: per-firm `brandColor` prop, default `#1A2535`
- Sidebar active-item background: `rgba(255, 255, 255, 0.10)`
- Sidebar active-item left border: per-firm `accentColor` prop, default `#4A7FA5`
- Sidebar text (active): `#FFFFFF`
- Sidebar text (inactive): `rgba(255, 255, 255, 0.55)`
- Sidebar subtitle ("CLIENT PORTAL" label): per-firm `subtitleColor` prop, default `#7DA3C4`
- Content area background: `#F7F8FA`
- Top bar background: `#FFFFFF`
- Top bar bottom border: `#E5E7EB`
- Notification bell icon (on light top bar): `#374151`
- Avatar background: per-firm `avatarColor` prop, default `#3A6A94`

## Text colors (content area, light theme)
- Primary text (headings, titles): `#1F3148`
- Secondary/muted text: `#6B7280`
- Tertiary/faint text (icons, labels): `#9CA3AF`

## Cards and surfaces
- Card background: `#FFFFFF`
- Card border: `border-gray-100` (Tailwind, ~`#F3F4F6`)
- Icon chip background (inside a card row): `#F3F4F6`

## Status pill colors (established in PortalTodo.tsx)
- Overdue: background `#FEE2E2`, text `#991B1B`
- Due soon / amber warning: background `#FEF3C7`, text `#92400E`
- Later / informational: background `#DBEAFE`, text `#1E40AF`
- Completed / success: background `#D1FAE5`, text `#065F46`

## Brand accents
- JAMM navy (product brand, used sparingly outside per-firm theming): `#1F3148`
- JAMM gold (reserved for pinned/action-required notification treatment): `#B07D3A`
- Amber warning text (due-soon calendar icon, "Due soon" stat subtext): `#D97706`
- Folder brand yellow (folder iconography in stat cards and document table): `#FBBF24` -- distinct from the amber warning color; bright saturated yellow, not an urgency signal

## Stat card standard (confirmed across Documents and Invoices pages)
Use this standard when building any new page with a stat card strip. Do not reintroduce the old bubbly pattern.

- Icon badge: `w-10 h-10 rounded-lg` (40px, softened square -- NOT rounded-full)
- Icon badge background: page-specific color chip (e.g. `#DBEAFE` for informational, `#D1FAE5` for success)
- Icon size inside badge: `size={18}`
- Card layout: `px-5 py-4 flex items-center gap-4` (icon left, text column right)
- Stat label: `text-[11px] font-medium mb-1`, color `#9CA3AF`
- Stat value: `text-[24px] font-semibold leading-none mb-1`, color `#1F3148`
- Subtext (optional): `text-[11px] leading-snug`, color `#9CA3AF`
- View link (optional): `mt-1.5 text-left text-[11px] font-medium transition-opacity hover:opacity-70 self-start`, color `#3A6A94`

Rationale: rounded-full at 40-44px reads as a bubble (consumer/wellness aesthetic). rounded-lg at 40px reads as a chip (financial product aesthetic). 24px semibold is clearly legible as a large stat without dominating the card.

- Billing hours badge (Total hours this year stat card on Billing Detail page): background `#EDE9FE`, icon color `#7C3AED`
  Reason: no purple/violet chip existed. Violet reads as "time/duration" and is visually distinct from both the established green (money/success) and blue (informational) pairs. Follows the same lightness pattern: violet-100 bg / violet-600 icon.

## Rule
Before estimating a color for any new portal page, check this file first. If a genuinely new color is needed, add it here with its real hex and where it's used, rather than inventing a one-off value.
