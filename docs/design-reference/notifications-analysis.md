# Notifications Page -- Visual Analysis

*Mock file: docs/design-reference/notifications-mock.png*
*Analyzed: 2026-08-31*

## IMPORTANT: Mock content is fabricated

The specific notification content shown in the mock (invoice numbers like "#INV-2024-0123",
message subjects, filenames like "bank-statement-april.pdf") is placeholder content invented
for the mock. It MUST NOT be copied literally into the real build. All real notification
rows reference genuinely existing database records -- actual invoice numbers, actual message
timestamps, actual engagement names -- confirmed from real seeded data.

## Page structure

- Light theme, matching the established portal redesign (white card on #F7F8FA background)
- Page header: "Notifications" title (20px bold #1F3148) + subtitle "Stay up to date on
  important activity and updates." (13px #6B7280)
- Single white card (bg-white rounded-xl border border-gray-100) containing all rows
- No tabs, no "Mark all as read" button, no separate header bar
- Rows separated by border-b border-gray-100 (last row has no border)

## Notification row layout

Each row is a horizontal flex (px-4 py-4):
- Left: colored circle badge (~36px, rounded-full) with a lucide icon centered inside
- Middle (flex-1): bold title + smaller body description below it
- Right: timestamp (11px muted) + optional unread dot stacked vertically

## Icon badge colors

### Gold / action-needed (items requiring the client's attention)

Used for: new messages from the firm, overdue invoices, document requests, to-do assignments.

- Badge background: #FEF3C7 (established "Due soon / amber warning" status pill background)
- Icon color: #D97706 (established "Amber warning text" from portal-design-tokens.md)
- No new tokens required.

### Blue / informational (completed or informational events)

Used for: payment received confirmations, invoice sent notifications, engagement updates.

- Badge background: #DBEAFE (established "Later / informational" status pill background)
- Icon color: #3B82F6 (blue-500, new -- see token addition below)
- The informational icon background #DBEAFE already exists. The icon color #3B82F6 is added
  as a new token (see portal-design-tokens.md addition).

## Unread indicator

A small orange dot (~8px, rounded-full) appears to the right of the timestamp on unread rows.

- Color: #F97316 (orange-500, new token -- see portal-design-tokens.md addition)
- Rationale: visually distinct from both the gold (#D97706) action badge and the blue
  informational badge. Orange reads as "new / attention" without competing with gold.

## Typography

- Row title (unread): 13px font-medium, color #1F3148
- Row title (read): 13px font-medium, color #6B7280
- Row body: 12px, color #6B7280, mt-0.5
- Timestamp: 11px, color #9CA3AF

## Empty and loading states

Empty: bell icon centered, "No notifications yet." in muted gray.
Loading: skeleton rows (3 placeholder animated divs) inside the white card.
