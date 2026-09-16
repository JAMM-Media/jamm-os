# Reset Password Email Mock Analysis

Source: docs/design-reference/reset-password-email-mock.png (viewed directly)
Reference: app/templates/email/password_reset.html, app/services/email_service.py,
           app/services/password_reset_service.py, app/templates/email/notification.html

---

## 1. Mock layout observations

**Page background:** Light gray, approximately #f4f4f4 to #f4f5f7. Email content centered.

**JAMM header (above card, centered):**
- "JAMM" in large bold text, approximately 48px, dark navy (#1F3148)
- "PRACTICE EXPERIENCE" in small ~10px gold (#B07D3A), uppercase, wide letter-spacing
- Text-only, no image (correction 1 applied)

**White card (centered, ~560px, rounded corners ~8px, soft shadow):**
- White background (#ffffff), padding approximately 40px

**Inside card -- main section (centered):**
- Circular lock badge: ~64px diameter, light blue-gray background (~#EFF3F7), lock icon inside
- "Reset your password" heading: ~22px, bold, dark navy (#1F3148), centered
- Body text: ~14px, muted gray (#6B7280), centered, ~1.7 line-height
  - "Hi [recipient_name]," then two more lines
- CTA button: full-width, dark navy (#1F3148), white text (~15px bold), ~14px vertical padding,
  border-radius ~6px, right-arrow character at end
- Expiry note: ~12px, muted (#9CA3AF), centered, below button

**Inside card -- "Didn't request this?" section (separated by thin rule):**
- Thin horizontal rule (~#E5E7EB) between sections
- "Didn't request this?" label: ~14px, weight 700, darker gray (#374151)
- Explanation text: ~13px, muted (#6B7280), line-height ~1.6
- "Thanks, / The JAMM Team" signature, same muted style

**Footer (below card, on page background):**
- Helper tagline: ~12px, muted (#9CA3AF), centered
- Three footer items separated by pipes: "Help Center | Contact Support | Privacy Policy"
- Copyright: ~11px, very muted (#C8CDD6), centered

---

## 2. Dimensions and tokens

| Element | Mock estimate | Applied value |
|---------|--------------|---------------|
| Page bg | ~#f4f4f4 | #f4f5f7 |
| Card bg | #ffffff | #ffffff |
| Card radius | ~8px | 8px |
| JAMM text | ~48px bold serif | 48px Georgia bold |
| PRACTICE EXPERIENCE | ~10px gold tracked | #B07D3A, letter-spacing 0.22em |
| Lock badge bg | ~#EFF3F7 | #EFF3F7 |
| Lock badge size | ~64px circle | 64px, border-radius 50% |
| Heading | ~22px bold | 22px bold Arial |
| Body text color | muted gray | #6B7280 |
| Button bg | #1F3148 navy | #1F3148 |
| Expiry note | ~12px muted | #9CA3AF |
| Section rule | ~#E5E7EB | #E5E7EB |
| "Didn't request" label | ~14px bold | #374151, weight 700 |
| Footer items | muted plain text | #9CA3AF plain spans |
| Copyright | very muted | #C8CDD6 |

---

## 3. Applied corrections

**Correction 1 -- Text-only JAMM header:**
No image logo. "JAMM" is styled HTML text in Georgia serif (the closest reliable system
serif to the app's Playfair Display, which cannot be loaded in email clients). "PRACTICE
EXPERIENCE" is a styled paragraph with uppercase and letter-spacing.

**Correction 2 -- Lock icon as inline SVG:**
Inline SVG chosen over Unicode emoji because emoji rendering is font-dependent and
inconsistent across email clients and operating systems. The SVG uses three shapes:
a rect for the body, a path for the shackle, and a circle for the keyhole. Colors:
#1F3148 fill on the body/shackle, white fill on the keyhole. Justified by the
modern-client-only constraint; older Outlook SVG incompatibility explicitly accepted.

**Correction 3 -- Footer links as plain text:**
No support email address is confirmed in task_ben.md's standing notes. All three
footer items (Help Center, Contact Support, Privacy Policy) are rendered as plain
muted text spans, not anchor elements.

**Correction 4 -- Expiry hours pluralization:**
Jinja2 inline conditional: `{{ 'hour' if expiry_hours == 1 else 'hours' }}`. Reads
"1 hour" for the current EXPIRY_HOURS=1 value and "N hours" for any future change.
Does not change the value passed in from email_service.py.

**Correction 5 -- Colors from existing palette:**
All hex values drawn from the palette already used in the existing template or
elsewhere in the app: #1F3148 (brand navy), #B07D3A (gold), #6B7280 (body text),
#9CA3AF (muted), #C8CDD6 (border/faint text), #EFF3F7 (surface-input / badge bg).

---

## 4. Layout approach

Table-based layout, matching notification.html (the other structured template in this
folder). An outer full-width table applies the page background and centers content.
An inner 560px table holds content rows. The white card is a single td with
border-radius:8px and overflow:hidden, containing a nested table to separate the
main content from the "Didn't request this?" section via a 1px rule row.

Consistent with notification.html's approach; standalone, no shared header/footer
component. Every style is an inline style attribute; no external stylesheet or style
block is used.

---

## 5. Pre-existing gap noted

The original template read "{{ expiry_hours }} hour" (singular always) -- correct
today (EXPIRY_HOURS=1) but would produce "2 hours" -> "2 hour" if the constant
ever changed. Fixed by correction 4. The constant in password_reset_service.py
was not changed.
