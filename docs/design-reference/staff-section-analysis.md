# Staff Section Visual Analysis

Source: `docs/design-reference/staff-section-mock.html`

## Layout structure

The staff row spans both grid columns (`grid-column: 1 / -1`, Tailwind `col-span-2`).
Inside it: a label, then a single `relative`-positioned chip row (`flex flex-wrap items-center gap-6px`).
The dropdown is a direct child of that chip row container (not of the Add button), so `position: absolute; top: 32px; left: 0` anchors it just below the chip row, opening into empty space below.

## Spacing

| Element | Mock value | Tailwind equivalent |
|---|---|---|
| Label bottom margin | 6px | `mb-1.5` |
| Chip row gap | 6px | `gap-1.5` |
| Chip inner gap | 5px | `gap-[5px]` |
| Chip padding | 3px 8px 3px 4px | `py-0.5 pl-1 pr-2` |
| Add chip padding | 3px 10px 3px 8px | `py-0.5 pl-2 pr-2.5` |
| Dropdown top offset | 32px (fixed, ~chip-row height + gap) | `top-full mt-1` |
| Dropdown search padding | 8px | `p-2` |
| Dropdown item padding | 8px 10px | `px-2.5 py-2` |
| Dropdown item gap | 8px | `gap-2` |

## Colors -- cross-referenced against codebase

| Mock color | Use | Codebase match |
|---|---|---|
| `#E5E7EB` | Chip background | Used at engagement page line 395 `bg-[#E5E7EB]` |
| `#C8CDD6` | Chip border, avatar background | Used throughout as `border-[#C8CDD6]` |
| `#1F3148` | Chip name text, avatar text | Codebase `text-brand` / `text-[#1F3148]` |
| `#6B7280` | Chip X color, Add chip color | Established as mid-gray throughout |
| `#9CA3AF` | Add chip border (dashed), empty states | Established as light-gray throughout |
| `#FFFFFF` | Dropdown background | `bg-white` |
| `#F7F7F8` | Dropdown item hover | Replaced by `#F3F4F6` already established in this codebase for hover states |
| `#E5E7EB` | Dropdown avatar background | Same chip background color |

## Chip dimensions

- Chip height: ~26px (py-0.5 + 12px text line)
- Avatar (chip): 18x18px, circular, `#C8CDD6` background, `9px` `font-weight:500` initials, `#1F3148` text
- Avatar (dropdown item): 22x22px, circular, `#E5E7EB` background, `10px` `font-weight:500` initials
- Chip name: `12px`, `#1F3148`
- Remove X: `&times;` HTML entity, `12px`, `#6B7280`, hover `#EF4444`
- Add chip border: `0.5px dashed #9CA3AF`
- Dropdown width: 220px fixed
- Dropdown list max-height: 180px

## Initials derivation

Established convention from `firm-chat/page.tsx` line 568:
```
name.split(' ').map(p => p[0]).join('').slice(0, 2).toUpperCase()
```
First letter of each word, first two, uppercase. Fallback `?` if name is null/empty.

## Dropdown positioning fix

Previous issue: `absolute left-0 top-full` on the Add button's inner container. When the parent column is narrow and near the left edge, the dropdown was in the right place but the containing `relative` div was only as wide as the button, so the dropdown overflowed it unexpectedly in some renders.

Mock fix: `relative` is on the entire chip row container. Dropdown is a direct child, `top-full mt-1 left-0 w-[220px]`. The chip row is always at least as wide as the card column, so the dropdown drops cleanly below it.
