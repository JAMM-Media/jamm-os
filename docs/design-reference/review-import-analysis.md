# Review Import Page -- Design Analysis

**Source**: docs/design-reference/review-import-mock.png (viewed directly, 1.4 MB file)
**Cross-reference**: tailwind.config.ts, portal-design-tokens.md (standing token set)

---

## Layout Structure

The page uses the real app shell (sidebar + top bar) unchanged. The content area contains:

1. Breadcrumb row ("Back to Import" link)
2. Page title "Review Import" (H1, brand navy)
3. Destination line (folder icon + destination name + "Change" link, though "Change" has no backend support -- omitted in build)
4. Five-stat summary strip (horizontal row of stat cards)
5. Conflict-policy display row ("If a file already exists:")
6. Plain-language consequence sentence
7. Filter chip row + search input
8. Two-panel main content: tree-table (left, 60-65%) | details drawer (right, 35-40%)
9. Sticky footer: consequence restatement + Cancel + "Import N Files" button

---

## Color Mapping (all values mapped to established tokens)

| Mock element | Observed value | Token used |
|---|---|---|
| Page background | White card on surface-page | bg-white dark:bg-dark-card |
| Page heading | Dark navy | text-brand (#1F3148) |
| Secondary text | Medium gray | text-[#6B7280] |
| Tertiary / label text | Light gray | text-[#9CA3AF] |
| "Will skip" status dot | Amber/orange dot | #F59E0B (amber-400) |
| "Excluded" status dot | Gray dot | #9CA3AF |
| "Ready" status | No dot | text-[#6B7280] muted |
| Folder rollup "Will skip, N issues" | Amber text | text-[#92400E] (status.amber-text) |
| Selected item highlight | Subtle blue-tinted row | bg-[#EEF2F7] |
| Conflict badge in drawer | Amber background | status.amber + status.amber-text |
| Stat strip -- files scanned | Blue badge chip | bg-[#DBEAFE] icon #3B82F6 |
| Stat strip -- folders | Yellow badge chip | bg-[#FEF3C7] icon #FBBF24 |
| Stat strip -- total size | Green badge chip | bg-[#D1FAE5] icon #10B981 |
| Stat strip -- will skip | Amber badge chip | bg-[#FEF3C7] icon #D97706 |
| Stat strip -- excluded | Gray badge chip | bg-[#E5E7EB] icon #6B7280 |
| Footer | White sticky bar, top border | bg-white border-t border-surface-border |
| Import button | Brand filled | bg-brand text-white |
| Cancel button | Outline | border + text-[#6B7280] |
| Filter chip (active) | Brand filled | bg-brand text-white |
| Filter chip (inactive) | Outlined | border border-surface-border text-[#6B7280] |

No new hex values introduced. All map to existing tailwind config tokens.

---

## Summary Strip

Five stat cards in a horizontal row, using the design-tokens stat card standard:
- `w-10 h-10 rounded-lg` icon badge
- `text-[11px] font-medium text-[#9CA3AF]` label
- `text-[24px] font-semibold text-brand` value

Cards:
1. Files scanned (blue chip, Files icon) -- `batch.totalFiles`
2. Folders (yellow chip, Folder icon) -- computed client-side from path components
3. Total size (green chip, HardDrive icon) -- `batch.totalBytes` formatted
4. Will skip (amber chip, AlertTriangle icon) -- count of `hasConflict=true` items
5. Excluded (gray chip, X icon) -- count of `resolved=false` items

---

## Conflict Policy Display

The mock shows three radio-style choices: Skip (Default), Replace, Keep both. There is no backend endpoint to change the conflict policy after a batch is created. Rendering these as an interactive control that silently does nothing is prohibited. Implementation: display as read-only indicator chips with the current value highlighted and a "(set at creation)" label. Not clickable.

---

## Filter Chips

"All | Will skip | Excluded | Ready" with item counts. Active chip: brand fill. Clicking a chip filters the tree to show only branches containing items of that status type (a folder appears if any descendant matches the active filter).

---

## Tree Table

**Confirmed backend data shape**: `ImportBatchOut.items` is a flat `ImportItemOut[]`. Each item has `normalizedRelativePath` (e.g. "Tax Documents/2025_1040_Draft.pdf"). There is no server-side folder-tree endpoint.

**Frontend responsibility (confirmed, not a gap to leave unaddressed)**: The folder tree structure, parent rollup aggregation, and folder status computation are entirely client-side responsibilities. The build derives them from `normalizedRelativePath` values combined with the parallel preview response.

**Tree building**:
- Parse `normalizedRelativePath` to extract directory components
- Build tree nodes: folder nodes and file nodes
- Merge each item's preview data (`resolved`, `hasConflict`)
- Compute folder rollup recursively: worst status among all descendants
- Status priority: `excluded` > `willSkip` > `ready`

**Column layout**: Name (with tree indent + expand/collapse chevron for folders) | Status | Size
**Row height**: ~36px

**Status rendering per row**:
- `ready`: "Ready" in `#9CA3AF`, no dot
- `willSkip`: small amber dot + "Will skip" in `#92400E`
- `excluded`: small gray dot + "Excluded" in `#6B7280`
- Folder rollup (worst=willSkip): amber dot + "Will skip, N issue(s)" in `#92400E`
- Folder rollup (worst=excluded): gray dot + "Excluded, N issue(s)"
- Folder rollup (worst=ready): "Ready" in `#9CA3AF`, no dot

---

## Details Drawer

Right panel, shown when a file row is clicked. Shows:
- Filename (drawer heading)
- "From:" `item.relativePath` (the original browser path)
- "To:" `item.normalizedRelativePath` within the destination (see note below)
- "Size:" `item.expectedBytes` formatted
- (Last modified is NOT in the backend response -- field omitted, not faked)
- If `hasConflict`: amber badge "Batch default: Skip this file" (or Replace/Keep both) + "Override for this file only" note

**Real data gap disclosed**: `batch.destinationFolderId` is a UUID. The folder name is not returned by the batch endpoint. The "To:" path shows only the item's path within the destination (i.e. `normalizedRelativePath`), not the full absolute path including the destination folder name. This is honest -- faking the folder name is prohibited.

**"Override for this file only"**: The backend's `ImportItemCreate.conflict_override` is per-item. However, overrides are set at batch-creation time, not editable after. This link is rendered but shows an explanatory tooltip/note that per-item overrides must be set before creating the batch. It does not open a modal that silently does nothing.

---

## Footer

Sticky bottom bar. Contains:
- Left text: "N files will import -- X excluded -- [policy consequence]"
- Right: Cancel button (outline) + "Import N Files" button (brand fill)
- Import count = `batch.totalFiles - excludedCount` (files that will actually land)
- Cancel navigates back to the batch's source page (derived from `batch.scope` + `batch.engagementId`/`batch.clientId`)
- Import calls `importBatchesApi.confirm(batchId)`, surfaces real detail on failure, navigates to source on success

---

## Top 3 Remaining Discrepancies (Honest)

1. **Destination folder name**: Mock shows a real folder name in the destination line and in the "To:" drawer field. The backend returns only `destinationFolderId` (UUID). Without a folder-fetch call, the name cannot be shown. Implementation shows UUID or "root level" rather than faking a name.

2. **Last modified date**: Mock drawer shows "Last modified: [date]". `ImportItemOut` has no last-modified field (has `created_at` and `completed_at` but those are backend row timestamps, not the original file's mtime). Field omitted.

3. **Conflict-policy control interactive behavior**: Mock shows three clickable radio-style options. Since no edit endpoint exists, the implementation renders them as read-only display with a label. The visual appearance differs from the mock's interactive intent, but this is the honest version.
