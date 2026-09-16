# Login Page Design Analysis

Source: docs/design-reference/login-mock.png (viewed directly)
Reference: tailwind.config.ts, portal-design-tokens.md, frontend/public logo assets

---

## 1. Mock layout (verbatim observations)

**Page background:** Light blue-gray, approximately #E5EBF0 -- close to the existing
`surface.page` token (#D6DEE6). Using `bg-surface-page` avoids a one-off hex.

**Logo area (centered, above card):**
- Logo mark (puzzle-piece icon, navy/medium-blue) left of "JAMM PX" wordmark
- Below: tagline "PRACTICE EXPERIENCE" in very small uppercase, muted blue-gray, letter-spaced
- All centered horizontally

**Card:**
- Centered, approximately 380-400px wide
- White background (#FFFFFF), NOT the surface.card token (#E9EEF3)
- Rounded corners approximately 16px
- Soft drop shadow (~rgba(0,0,0,0.10) spread 24px)
- Internal padding approximately 40px horizontal and 40px vertical

**Inside card -- typography and controls:**
- Heading "Sign in": approximately 28px, weight heavier than body. Applied at 500 per design system rule.
- Subtitle "Welcome back to JAMM PX.": approximately 14px, muted #6B7280
- "Email address" label: 12px, #6B7280
- Email input: light gray bg, 44-48px tall, rounded-lg, placeholder "you@yourfirm.com"
- "Password" label: 12px, #6B7280
- Password input: same style, eye toggle icon on right
- Below password: right-aligned small link "Use a magic link instead" (~12px, blue link color)
- Error state: not shown in mock
- "Sign in" button: full width, dark navy (#1F3148), white text, 44-48px tall, same radius

**Footer (below card):**
- "Need help signing in? Contact support" -- small centered text, muted
- Thin horizontal divider
- "2026 JAMM PX. All rights reserved." -- very small, muted, centered

---

## 2. Dimensions and tokens

| Element | Mock value | Token used |
|---------|-----------|------------|
| Page bg | ~#E5EBF0 | `bg-surface-page` (#D6DEE6, close enough) |
| Card bg | #FFFFFF | `bg-white` (deviation from surface.card -- see section 4) |
| Card radius | ~16px | `rounded-2xl` |
| Card shadow | soft, ~10% opacity | `shadow-[0_4px_24px_rgba(0,0,0,0.10)]` |
| Card width | ~380-400px | `max-w-[400px]` |
| Card padding | ~40px | `px-10 py-10` |
| Heading | ~28px, 500 | `text-[28px] font-medium` |
| Subtitle | ~14px, muted | `text-[14px] text-[#6B7280]` |
| Labels | ~12px | `text-[12px] font-medium text-[#6B7280]` |
| Input height | ~44px | `h-11` |
| Input radius | ~8px | `rounded-lg` |
| Input bg | light gray | `bg-surface-input` (#EFF3F7) |
| Input border | light | `border-surface-border` (#C2CDD8) |
| Button height | ~44px | `h-11` |
| Button bg | #1F3148 | `bg-brand` |
| Link color | blue | `text-brand-light` (#4A7FA5) |
| Footer text | ~12px muted | `text-[12px] text-[#9CA3AF]` |

---

## 3. Applied overrides (Ben's five decisions)

**Decision 1 -- Real logo, not the mock's mark:**
The mock's logo is a generic puzzle-piece icon. The real logo mark is at
`/jamm-logo-mark.svg`. Used as-is with the existing "JAMM PX" wordmark treatment
(PX in gold #B07D3A). Tagline "PRACTICE EXPERIENCE" added in small uppercase
muted text below the wordmark row.

**Decision 2 -- "Forgot password?" link preserved:**
Not visible in the mock (only "Use a magic link instead" is shown below the
password field). Both links are placed in a flex row below the password input:
"Forgot password?" on the left, "Use a magic link instead" on the right.

**Decision 3 -- Magic link behind a toggle:**
The mock shows only the password form. "Use a magic link instead" is a toggle
link that swaps the card's form content -- password form hidden, magic link form
shown (email prefilled from password form email, Send link button, sent/error
states, "Back to password sign in" link). They are never shown simultaneously.

**Decision 4 -- "Contact support" is plain text, no link:**
Rendered as "Need help signing in?" followed by "Contact support" in muted text,
not a link, until a confirmed support address exists.

**Decision 5 -- Two-factor step inside the card:**
The 2FA step (authenticator code, backup code toggle, Back) is not in the mock.
It renders inside the same card in place of the password form when step === 'code',
using the same input and button styling as the password step.

---

## 4. Deviation from surface.card token

The mock's card is pure white (#FFFFFF). The app's `surface.card` token is
#E9EEF3 (a cool light blue-gray that matches the page's card-surface treatment).
On this public-facing page only, the card is `bg-white` to match the mock's
higher contrast. In dark mode the card uses `dark:bg-dark-card` as the existing
dark token. This deviation is intentional and isolated to the login page.

---

## 5. Magic link expiry fix

Backend: `_MAGIC_LINK_EXPIRY_MINUTES = 30` in app/services/staff_magic_link.py.
Current page: says "15 minutes" in the helper text and "30 minutes" in the sent
state. Both corrected to 30 minutes in the rebuild.

---

## 6. Dark mode

The mock shows light mode only. Dark mode follows the existing token system:
- Page: `dark:bg-dark-page` (#1D232A)
- Card: `dark:bg-dark-card` (#272D35)
- Text: `dark:text-[#EDEEF0]`
- Inputs: `dark:bg-dark-card dark:border-dark-border`
- Button: `dark:bg-brand-btn` (#3A6A94)
This is intentional rather than an afterthought; the card is visually distinct from
the page in dark mode due to the card/page token difference.

---

## 7. Mock v2 (login-mock-v2.png) -- logo block superseded

Mock v2 supersedes login-mock.png for the logo block only. All other decisions
from the first build remain.

**What mock v2 shows:**
- Large "JAMM" wordmark in heavy navy, positioned above the card
- The real mark /jamm-logo-mark.svg to its left at cap height
- Below the mark+wordmark row: "PRACTICE EXPERIENCE" in gold (#B07D3A),
  uppercase with wide letter-spacing, visually spanning approximately the same
  width as the row above
- No "PX" in the logo block. PX is the app header treatment; the front door
  uses the full category name.

**Decisions applied from v2:**

1. Wordmark: "JAMM" only, no PX, at text-[48px] font-medium (500 weight) in
   brand navy. Size does the work per the design system weight rule.

2. Mark: /jamm-logo-mark.svg at height 35px, approximately the cap height of
   48px Plus Jakarta Sans. Gap between mark and wordmark: gap-3 (12px).

3. Gold line: "Practice Experience" in #B07D3A, uppercase, tracking-[0.2em],
   text-[11px], mt-2 below the mark+wordmark row. Width visually balances with
   the row above at this size and tracking.

4. Two layouts implemented, toggled by the constant on line 10 of the page file:
     const LOGO_LAYOUT: 'beside' | 'stacked' = 'beside'
   - 'beside' (default): mark on the left, wordmark to its right in a row
   - 'stacked': mark centered above the wordmark in a column
   Both share the same gold line below.
   To compare: change 'beside' to 'stacked' on that line and reload.

5. Copyright line updated to include the copyright symbol:
   "(c) 2026 JAMM PX. All rights reserved."

6. Subtitle inside the card stays "Welcome back to JAMM PX." -- the product
   name, not the wordmark. Not changed by v2.
