# Recent Documents Strip -- Visual Analysis

Source: `docs/design-reference/recent-documents-mock.html`

## Position

Renders directly above `<FolderBrowser>`, which is the first element in the
Documents tab. Label + card row + 16px bottom margin, then FolderBrowser starts.

## Label

`.label` in the mock:
- `font-size: 11px; font-weight: 500; letter-spacing: 0.05em; color: #6B7280; text-transform: uppercase; margin-bottom: 8px`
- Exact match to `labelClass` already defined on this page:
  `text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em]`
- Tailwind: `{labelClass}` + `mb-2` (8px)

## Card row

`.recent-row`:
- `display: flex; gap: 8px; margin-bottom: 16px`
- Tailwind: `flex gap-2 mb-4`

## Cards

`.recent-card`:
- `flex: 1; min-width: 0` -- equal width, no overflow
- `background: #EDEEF0` -- matches `bg-[#EDEEF0]` (surface-card in light mode)
- `border: 0.5px solid #C8CDD6`
- `border-radius: 8px`
- `padding: 8px 10px` -- Tailwind: `px-2.5 py-2`
- `cursor: pointer`
- Tailwind: `flex-1 min-w-0 bg-[#EDEEF0] dark:bg-dark-card border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] rounded-[8px] px-2.5 py-2 cursor-pointer`

## Card inner -- top row

`.recent-card-top`:
- `display: flex; align-items: center; gap: 5px; margin-bottom: 4px`
- Tailwind: `flex items-center gap-[5px] mb-1`

Icon: mock uses 13x13. `fileIconFromContentType` returns `size={15}`. Use `size={13}` via
a local variant to match the card's compact height.

Filename: `font-size: 11.5px; font-weight: 500; color: #1F3148; white-space: nowrap; overflow: hidden; text-overflow: ellipsis`
- Tailwind: `text-[11.5px] font-medium text-[#1F3148] dark:text-[#EDEEF0] truncate`

## Card inner -- time

`.recent-time`:
- `font-size: 10px; color: #9CA3AF`
- Tailwind: `text-[10px] text-[#9CA3AF]`

## Icon color mapping -- confirmed against real fileIconFromContentType

Mock comment matches the real function (lines 64-83 of engagement detail page):

| Content type | Icon | Color |
|---|---|---|
| `application/pdf` | FileText | `#EF4444` red |
| spreadsheet / csv / xls / xlsx | FileSpreadsheet | `#10B981` green |
| `image/*` | FileImage | `#8B5CF6` purple |
| word / document | FileGeneric | `#3B82F6` blue |
| fallback | FileGeneric | `#9CA3AF` gray |

All five mappings confirmed identical between mock comment and real function.

## content_type gap (reported finding)

The backend `RecentDocumentItem` schema (`app/schemas/engagement.py`) returns only
`document_id`, `filename`, `engagement_id`, `last_viewed_at` -- no `content_type`.
A `contentTypeFromFilename(filename)` helper is added to the page to derive a
best-effort content type from the file extension for icon selection only.
This is a fallback for this task only. The backend schema should be extended in a
future task if accurate icon rendering for ambiguous extensions is required.

## relativeTime

The existing `relativeTime` helper (page lines 48-62) is reused directly. Output
matches the mock format ("4m ago", "1h ago", "X days ago") except it outputs
lowercase "yesterday" where the mock shows "Yesterday". The existing function is
reused as-is per task instructions; capitalizing "Yesterday" is a deferred
cosmetic cleanup.
