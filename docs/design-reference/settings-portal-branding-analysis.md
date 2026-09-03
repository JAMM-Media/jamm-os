# Settings Portal Branding Page -- Visual Analysis

Source: docs/design-reference/settings-portal-branding-mock.png
Viewed: 2026-09-02

---

## Overall Page Layout

Two-column layout at the settings content width (wider than the current max-w-2xl constraint):
- Left column (~60% width): main editor -- setup status, firm name, logo, portal branding card, save button
- Right column (~40% width): "Live portal preview" panel, sticky alongside the editor

The outer container uses the full settings content area width (no max-w-2xl).

---

## Setup Status (top, full width)

**Mock shows:** A compact card with 3 inline green-checked items displayed HORIZONTALLY, not as a vertical list.

Each item: small green circle with checkmark + label text, arranged in a row.
- Display name customized (checked green)
- Firm logo uploaded (checked green)
- Colors customized (checked green)

Spacing: items spaced with gap between them, displayed inline/flex-row.

---

## Second Row -- Two Side-by-Side Cards

Two equal-width cards in a grid row:

**Left card: "Firm name in portal"**
- Label: "Firm name in portal" (small uppercase)
- Text input with value "Riverside Tax & Advisory"
- Hint text below

**Right card: "Firm logo"**
- Label: "Firm logo" (small uppercase)
- Upload zone or logo display
- Logo shown as image inside the card
- Hint text below

---

## Portal Branding Card (main editor, full width of left column)

### Header area
- "Portal branding" label (small uppercase, muted)
- Subtext about configuring colors for dark/light modes

### Tab bar
- "Dark mode" tab | "Light mode" tab -- pill/button style tabs, one underlined or highlighted to show active
- Inline badge: "Active mode: Dark" (green pill, same style as current Active badge) -- shows which mode clients see, separate from which tab is being edited

### Color grid
- 2-column CSS grid (not single list)
- Each cell: [color swatch 32px] [hex text input 7-char] [label text]
- 9 tokens across 5 rows x 2 cols (last row has 1 item, first col)
- Estimated column order (left col first): top_bar, tab_bar, accent, card, text_muted -- right col: page, avatar, subtitle, text_primary

### Inside tab header area
- "Set as active" button (small link-style, only visible on inactive mode tab)
- Contrast warnings if any appear below the grid

---

## Right Panel -- "Live portal preview"

### Header row (top of right panel)
- "Live portal preview" label (bold/medium weight)
- "Reset to defaults" text button (right-aligned within header)
- "Open preview" small button or link (opens portal in new tab -- route TBD)

### Preview render
- Mini portal UI matching the currently-selected mode tab colors
- Top bar: firm name + "Client Portal" subtitle + avatar circle
- Tab bar: To-do | Documents | Invoices
- Page area with a card item sample
- Renders the dark or light colors based on whichever mode tab is active in the editor

### Panel width
- Approximately 280-320px wide
- Vertically aligned with the main editor content

---

## Save Button (bottom of left column)
- "Save changes" primary button (blue/brand colored, same as current "Save branding")
- Confirmation text appears inline after save

---

## Design Tokens Referenced

All colors match the existing portal-design-tokens.md tokens already in use:
- Active badge: bg #D1FAE5, text #065F46 (same as current)
- Card surface: bg-surface-card / bg-dark-card (same as current)
- Border: border-surface-border / border-dark-border (same as current)
- Tab active underline: uses brand accent color
- "Reset to defaults" text: text-[#6B7280] hover:text-brand-light (same as current pattern)

No new colors introduced beyond what already exists in the codebase.

---

## Current vs Mock Discrepancies

1. **Setup status**: Current = vertical list. Mock = horizontal inline badges.
2. **Firm name + Logo**: Current = stacked vertically. Mock = side-by-side grid.
3. **Dark/Light mode**: Current = both ColorSections stacked simultaneously. Mock = tabbed, only one shown at a time.
4. **Active mode indicator**: Current = "Active" pill inside each ColorSection header. Mock = single "Active mode: [X]" badge inline with the tab switcher.
5. **Color grid**: Current = single column list. Mock = 2-column grid.
6. **Mini preview**: Current = embedded inside each ColorSection at the bottom. Mock = separate right panel alongside the editor.
7. **Reset to defaults**: Current = inside ColorSection header. Mock = inside right preview panel header.
8. **Preview portal button**: Current = does not exist. Mock = "Open preview" button in right panel header. No standalone preview route exists in codebase (portalPreviewApi.ts is a data API, not a page URL). Button will render as a visible but disabled/labeled placeholder.
9. **max-w-2xl constraint**: Current = limits width to ~672px. Mock = uses wider setting content width. Will remove constraint.
