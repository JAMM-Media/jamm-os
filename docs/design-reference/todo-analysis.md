# To-do Page Visual Analysis

Source: docs/design-reference/todo-mock.png
Session: 2026-08-21

---

## 1. Overall Layout Structure

The mock uses a two-zone structure inside the content area:

**Zone A (full width):**
- Page title "To-do" in large bold text (~22-24px, navy)
- Subtitle "Here are the tasks and action items that need your attention." in muted text (~13px, gray)
- 4-column stat strip below the title

**Zone B (two-column, below stat strip):**
- Left column (flex-1, ~65-70% of width): "Open tasks" section + "Recent documents" section
- Right column (fixed ~240-260px): "Need help?" card, top-aligned

Spacing rhythm: ~24px vertical gap between the title block and stat strip, ~24px between stat strip and the two-column zone, ~24px between sections within the left column.

---

## 2. Stat Strip (4 cards)

**Layout within each card:**
1. Small label text (e.g., "Open tasks") at TOP -- ~11-12px, muted gray (#9CA3AF), normal weight
2. Large bold number in the MIDDLE -- visually ~38-44px, bold, color-semantic
3. Small subtext at BOTTOM -- ~11px, muted gray (#9CA3AF)

Current implementation has this ORDER INVERTED: number first, then label, then subtext. The mock shows label -> number -> subtext.

**Color semantics on numbers (matches existing tokens):**
- Open tasks: #1F3148 (navy)
- Overdue: #DC2626 or similar red -- matches token `#FEE2E2` pill family, number itself a stronger red
- Due this week: #1F3148 (neutral navy)
- Completed: #059669 or similar green -- matches token `#065F46` pill family

**Card surface:** White background, very subtle gray border, rounded corners. No visible shadow. Looks flat and clean.

**Estimate: number font size in mock is ~40-42px.** Current implementation uses 28px -- significantly smaller than mock.

---

## 3. "Open Tasks" Section

**Section heading:** "Open tasks" in sentence case, ~13px, semi-bold, muted dark (#1F3148 or #374151). NOT uppercase/tracked. Current implementation uses uppercase tracking -- differs from mock.

**Task rows:**
- White card background, subtle gray border, ~8px rounded corners
- Left: icon chip (rounded-lg, ~36x36px, #F3F4F6 background) with a document/file icon in the firm accent color
- Center: task title (~14px, semi-bold, #1F3148) + description (~12px, muted, #6B7280) stacked
- Right: colored due-date pill + chevron icon (#9CA3AF)
- Row internal padding: ~16-20px horizontal, ~14-16px vertical

**Due-date pills:** Matches existing token colors (red for overdue, amber for due soon, blue for later). Pill text ~11px, rounded-full.

---

## 4. "Need help?" Right Panel

**Entirely absent from current implementation.**

Structure (from mock):
- White card, rounded corners (~12px), subtle border
- Heading: "Need help?" (~14px, semi-bold, #1F3148)
- Body text (~12-13px, muted, #6B7280): "If you have any questions about your task list, reach out to your accountant."
- Button: "Send a message" -- navy background (#1F3148), white text (~12-13px), rounded-lg, full-width within the card
- Padding: ~20px

---

## 5. "Recent Documents" Section

**Section heading:** "Recent documents" -- same style as "Open tasks" (sentence case, not uppercase).

**Table structure:** White card wrapping a table. Columns: Name (with file icon), Uploaded (date), Status (pill).
- Header row: ~10-11px uppercase tracking-wider, #9CA3AF
- Data rows: 13px, #1F3148 for name, #6B7280 for date
- Status pill: green "Uploaded" -- matches existing token #D1FAE5 / #065F46

"View all documents" link at bottom of table, in accent color.

---

## 6. Specific Discrepancies (current vs. mock)

| # | Category | Mock | Current | Priority |
|---|----------|------|---------|----------|
| 1 | Layout | Two-column zone (tasks left, "Need help?" right) | Single column | High |
| 2 | Page identity | "To-do" heading + subtitle visible | No heading | High |
| 3 | Stat card order | Label -> Number -> Subtext | Number -> Label -> Subtext | High |
| 4 | Stat number size | ~40-42px bold | 28px bold | High |
| 5 | "Need help?" panel | Present with "Send a message" button | Absent | High |
| 6 | Section headings | Sentence case, ~13px semi-bold | 12px uppercase tracking-wider | Medium |
| 7 | Stat card label weight | Normal weight, muted gray | Semi-bold, navy | Medium |

---

## 7. Colors Not in Existing Tokens

No new colors required. All colors in the mock are covered by portal-design-tokens.md:
- Stat numbers use #1F3148 (navy), #DC2626 (red -- close to Overdue pill family), #059669 (green -- close to success token)
- "Need help?" button uses #1F3148 (JAMM navy)

Note: the stat card's overdue number color and the green completed color are slightly bolder versions of the pill text colors. Using the same values (#DC2626 and #059669) is a reasonable match; the exact hue can be confirmed after Ben reviews the rendered output.

Adding to tokens file: stat number color for overdue (#DC2626) and completed (#059669) are already functionally in use via PortalTodo.tsx; this analysis confirms they match the mock's color intent.
