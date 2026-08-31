# Messages Page -- Visual Analysis

*Mock file: docs/design-reference/messages-mock.png*
*Analyzed: 2026-08-30*

## Infrastructure status (pre-existing)

All backend infrastructure existed before this task:
- `ClientMessage` model (`app/models/message.py`): `firm_id`, `client_id`, `sender_id` (nullable), `sender_role` ("staff"/"client"), `body`, `created_at`, read receipts
- Portal endpoints: `GET /clients/{client_id}/messages`, `POST /clients/{client_id}/messages`, `GET .../unread-count`
- `PortalMessages.tsx` component existed but used dark-theme defaults and lacked the mock's visual structure
- Messages nav item in `PortalShell.tsx` with unread badge already functional

## Page header

- Title: "Messages" -- 20px bold, color #1F3148 (established primary text)
- Subtitle: "Communicate securely with your accounting team." -- 13px, color #6B7280 (established muted)

## Conversation header

- Firm name: 14px font-semibold, color #1F3148
- Below: "Typically replies within one business day" -- 12px, color #9CA3AF (established tertiary)

### INTENTIONAL PLACEHOLDER: reply-time line

The "Typically replies within one business day" line is **unconfirmed placeholder copy**. It represents an SLA-shaped commitment (same-day turnaround) that has not been reviewed or agreed to by any firm using this software. Shipping it as-is would create a client expectation the firm may not be able to meet.

Implementation: the element carries `data-placeholder-unconfirmed="reply-time"` and the component emits a `console.warn` on mount. A code comment immediately above the element marks it for review. This copy must not be committed as permanent without a deliberate decision about what SLA, if any, should be stated.

## Message bubbles

### Staff messages (left-aligned)

- Staff avatar: small circle (28px), background = per-firm `accentColor` (default `#3A6A94`), white initials text, font-bold text-[10px]
- Sender name + timestamp: 11px, color #9CA3AF, shown once per consecutive-sender group (not per message)
- Bubble background: #FFFFFF (white) with `border border-gray-100`
- Bubble text: 13px, color #1F3148, `leading-relaxed whitespace-pre-wrap`
- Bubble border-radius: rounded-[12px]

### Client messages (right-aligned)

- No avatar, no sender name displayed
- Bubble background: per-firm `accentColor` (variable, default `#3A6A94`) -- see token note below
- Bubble text: 13px, color #FFFFFF, `leading-relaxed whitespace-pre-wrap`
- Timestamp: 10px, color #9CA3AF, shown after last message in group

## Design tokens added

### Client message bubble background

Uses the per-firm `accentColor` prop (not a fixed hex -- it is intentionally firm-specific). The default is `#3A6A94` (JAMM navy accent, already established). No new fixed-hex token is required because the value is the same as the already-established accent color used elsewhere in the portal. Added a note to portal-design-tokens.md confirming this.

### Staff message bubble

White (`#FFFFFF`) with `border border-gray-100`. The border color (`#F3F4F6`) is already established as "Card border" in portal-design-tokens.md. No new token needed.

## Consecutive-sender grouping

The mock shows sender name and timestamp displayed once per group of consecutive messages from the same sender, not per individual message. Implementation: group messages by `sender_role` (new group starts when sender_role changes), show sender label before the group's first bubble and timestamp after the last bubble.

## Compose area

- Container: white background, `border border-gray-200`, `rounded-xl`
- Paperclip icon: `size={16}`, color #9CA3AF -- visual only, no attachment functionality yet (disclosure in report)
- Textarea: `text-[13px]`, placeholder "Type your message...", auto-expands (rows=1 to start), no border (integrated into container)
- "Send message" button: `accentColor` background, white text, `text-[13px] font-medium`, includes Send icon + text label, right-aligned inside compose container

## Remaining discrepancies vs mock

1. **Attachment functionality absent**: the paperclip icon renders but has no upload behavior. The mock implies an attachment affordance. This is a placeholder visual only.
2. **"Typically replies" line**: present in the mock as normal copy, present in the build as a flagged placeholder. Visual appearance is identical; the flag is in code only.
3. **Email-style vs chat-style tone**: the mock shows formal email-style messages with salutations and sign-offs. The seeded demo data follows this style, but the component itself renders whatever body text exists -- the tone question is unresolved and the component is neutral on it.
