# Send Notification Action Config UI -- Design Analysis

Source: docs/design-reference/automation-send-notification-mock.html
Read: 2026-09-05

---

## Mock structure

The mock is a standalone HTML file with inline CSS and JS. It wraps the Send
Notification card inside an action-list context showing three other collapsed
action cards (Send Email, Create Task, Update Engagement). These are REVIEW
CONTEXT ONLY and are not built in this task.

A "Preview aid only" toolbar appears at the top of the mock with a Light/Dark
theme toggle. This is also REVIEW TOOLING ONLY and is not built into the real
component.

---

## Send Notification card -- field-by-field analysis

### Card header

- Icon: bell SVG (stroke, 15x15), gold (#B07D3A) stroke on white (#FFFFFF) bg
- Title: "Send Notification" -- 13px, bold, navy (#1F3148)
- Subtitle: "Choose who receives it, how it is delivered, and what it says." -- 11px, helper (#6B7280)
- Border-bottom on header: 0.5px solid #C8CDD6

### Field 1: Recipient (top of action-body)

- Label: "Who should be notified?" -- 11px, 500 weight, navy
- Control: native `<select>`, 36px height, 0.5px border, 6px border-radius, light bg (#F7F7F8)
- Options (exactly four, in order): Firm Owner, Manager, Assigned Staff, Client
- Helper text below: "Assigned Staff means whoever the triggering item is assigned to."
- Config key: `recipient_role` with values `firm_owner | manager | assigned_staff | client`

### Field 2: Urgency (segmented toggle)

- Label: "How urgent is this?" -- 11px, 500 weight, navy
- Control: 2-column segmented toggle, 3px padding and gap, 0.5px border, 7px radius, white bg
- Options (exactly two, in order):
  - "Notify right away" -- active = filled navy bg (#1F3148), white text; maps to tier=loud
  - "Save to list" -- inactive; maps to tier=quiet
- Config key: `tier` with values `loud | quiet`
- Default active option: "Notify right away" (tier=loud)

#### Live preview (rendered below the toggle, inside a bordered box)

- Container: 10px top margin, 11px padding, 0.5px border, 7px radius, #FAFAFB bg
- "LIVE PREVIEW" label: 10px, 650 weight, uppercase, 0.04em letter-spacing, helper color
- Preview content switches based on selected urgency:

**Loud preview ("Notify right away")**:
- Shows a minimal "screen" frame with macOS-style traffic-light dots
- A toast card overlaid at bottom-right of the screen:
  - Left gold border-left (3px), white bg, box-shadow
  - Top row: "Just now" timestamp (10px helper) + dismiss X button
  - Icon row: mini bell (gold) + title + body text
  - Title and body resolve merge fields from inputs using example values
- Caption below: "This will pop up immediately, interrupting whatever they're doing."

**Quiet preview ("Save to list")**:
- Shows the same screen frame
- A bell icon with badge "1" at top-right of screen frame
- A notification-center dropdown below the bell, containing one row:
  - Bell icon + resolved title + resolved body
- Caption below: "This will appear in their notification list to check when they're ready. No interruption."

**Merge field resolution** (preview only -- not runtime):
- `{{client_name}}` -> "Riverside Tax"
- `{{engagement_type}}` -> "1040 return"
- `{{firm_name}}` -> "Riverside Tax & Advisory"
- `{{days_until_due}}` -> "3"
- Unknown keys -> "Example value"
- Regex: `\{\{\s*([a-zA-Z0-9_]+)\s*\}\}`

### Field 3: Notification title

- Label: "Notification title" -- 11px, 500 weight, navy
- Control: text input, 36px height, placeholder "e.g. Engagement deadline approaching"
- Config key: `title`
- Field order: AFTER the urgency/preview block, not before

### Field 4: Notification message

- Label: "Notification message" -- 11px, 500 weight, navy
- Control: textarea, min-height 88px, resize:vertical, 9px/10px padding
- Placeholder: "e.g. {{client_name}}'s {{engagement_type}} is due in 3 days."
- Helper text: "You can use merge fields like client name and engagement type. They'll be filled in automatically when this fires."
- Config key: `body`

---

## Decisions confirmed during mock review (not to re-litigate)

1. Recipient is role-based, not an individual ID picker.
2. Urgency is exactly two options (loud, quiet). Silent is NOT offered here.
3. Field order is fixed: recipient, urgency+preview, title, body.
4. Live preview resolves merge fields with example values for display only.
5. Light/dark toggle and collapsed sibling cards are review tooling -- not built.

---

## Discrepancies: mock vs real AutomationEditModal.tsx

1. **No send_notification section exists at all.** The modal uses content-based
   detection (checks for config keys like `delay_days`, `subject`, `body`, etc.)
   and has no type==='send_notification' branch. A send_notification action would
   fall through and render nothing (it has no message field matching the existing
   "Notification message" section which detects `config.message`, not `config.body`).

2. **Backend config shape mismatch.** The current `_handle_send_notification`
   reads `recipient_id` (a fixed UUID) and `title` from the trigger payload, not
   from the action config. This is wrong for a reusable rule -- the recipient must
   be resolved at execution time from a role, not stored as a fixed ID.

3. **Tier is hardcoded.** The current handler always passes `tier=NotificationTier.quiet`
   regardless of config. This must be read from config.

4. **Design tokens match.** The real existing tokens in AutomationEditModal.tsx:
   - Navy: `#1F3148` -- matches mock `--navy`
   - Light bg: `#F7F7F8` -- matches mock `--input`
   - Border: `#C8CDD6` -- matches mock `--border`
   - Focus: `#4A7FA5` -- matches mock `--focus`
   - Helper: `#6B7280` -- matches mock `--helper`
   - Dark text: `#EDEEF0` -- matches mock `--dark-text`
   - Dark bg: `#2D2D2D` -- matches mock `--dark-input`

5. **Merge field availability gap.** The four fields shown in the mock preview
   (`client_name`, `engagement_type`, `firm_name`, `days_until_due`) are
   reasonable runtime fields available from trigger payloads, but `days_until_due`
   has no universal trigger source -- it only applies to deadline/due-date events.
   The preview shows it as an example only; actual runtime resolution depends on
   the trigger event and is handled separately by automation execution logic.
   Disclosed here as a gap; this task builds the preview only.

---

## Backend config shape (new)

```json
{
  "recipient_role": "firm_owner" | "manager" | "assigned_staff" | "client",
  "tier": "loud" | "quiet",
  "title": "string with optional {{merge_fields}}",
  "body": "string with optional {{merge_fields}}"
}
```

Recipient resolution at execution time:
- `firm_owner` -> first User in firm with role=firm_owner
- `manager` -> first User in firm with role=manager; falls back to firm_owner if none
- `assigned_staff` -> Task.assigned_to from payload["task_id"] if present;
  otherwise falls back to firm_owner (Engagement has no assigned_to field)
- `client` -> payload["client_id"] as recipient_id with RecipientType.client

Backward compatibility: if `recipient_role` is absent from config (pre-existing
rule stored before this change), the handler skips with a warning log rather than
crashing.
