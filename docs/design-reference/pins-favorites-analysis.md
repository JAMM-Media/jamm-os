# Pins and Favorites Visual Analysis
# docs/design-reference/pins-favorites-analysis.md

## 1. Source

docs/design-reference/pins-favorites-mock.html (7704 bytes, confirmed non-zero)

---

## 2. Confirmed design decisions (from HTML comment in mock)

- Two distinct concepts: Favorite (private, per-user) and Pin (shared, engagement-scoped, trio-gated).
- No separate pinned strip. Pins are visible and marked directly in the table (cap of 5 makes the table sufficient).
- Pin indicator sits directly to the left of the folder/file icon in the Name column. No separate column, no reserved empty space on unpinned rows.
- Pinned rows sort to the top and get a faint warm background tint.
- The inline pin icon is READ-ONLY. Toggle actions live in the three-dot menu only (Pin to engagement / Remove pin, Add to Favorites / Remove from Favorites).
- Favorites star is a later concern; this task focuses on the pin indicator only.

---

## 3. Pin icon

SVG path (verbatim from mock):
M16 3l5 5-1.5 1.5L18 8l-5.5 5.5L14 16l-1.5 1.5L9 14l-5 5-1-1 5-5-3.5-3.5L6 8l2.5 2.5L14 5l-.5-1.5L15 2z

Fill color: #1F3148 (brand navy, same as .btn-primary background in mock CSS)
Size: 13x13px (width="13" height="13" viewBox="0 0 24 24")

Cross-reference: #1F3148 is the established brand navy used as bg-brand throughout this codebase. No new hex value introduced.

---

## 4. Row tint

CSS class in mock: .row-pinned { background: #FEFCF5 }

Value: #FEFCF5 -- a faint warm off-white. Not present in the codebase today; introduced specifically for pinned rows. Deliberately faint so it does not compete with the navy pin icon.

Dark mode: no dark-mode equivalent specified in mock. For dark mode, omit the tint (empty string) to avoid inaccessible contrast.

---

## 5. Name column gap

Mock: .row-name { gap: 8px }
Existing code: gap-[9px] in name cell divs

Decision: preserve existing gap-[9px] in code. The 1px difference is not visually material and changing it would risk misaligning all existing rows. The pin icon slots in as an additional flex child within the same gap.

---

## 6. Menu item ordering

New items go ABOVE the existing Move to Folder (non-destructive, more frequently used).
Final order:
1. Pin to engagement / Remove pin  (gated to canPin users only -- hidden otherwise)
2. Add to Favorites / Remove from Favorites  (visible to all)
3. [border separator]
4. Move to Folder
5. [border separator]
6. Delete

This matches the established pattern in this file: destructive actions last, visually separated by a border-t.

---

## 7. Pin menu item visibility gating

Pattern reused from the engagement page: canFinalize (firm_owner or manager or currentUserIsAdministrator) is the exact same trio used for Staff actions and finalize gating. Passed as canPin prop to FolderBrowser, forwarded to each row.

The pin menu item is hidden (not disabled) when canPin is false, matching the hide-not-disable pattern used for the Staff Add/Remove controls on this page.
