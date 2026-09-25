# Folder Table Redesign Analysis
# docs/design-reference/folder-table-redesign-analysis.md

## 1. Visual Specification (from mock)

### Layout
- Table card: background #FFFFFF, border 1px solid #E5E7EB, border-radius 12px, box-shadow 0 1px 3px rgba(0,0,0,0.05), overflow hidden
- Header row: padding 10px 18px, border-bottom 1px solid #F3F4F6
- Data rows: padding 11px top/bottom, 18px left base (left varies by depth)
- Row dividers: height 1px, background #F9FAFB, margin 0 18px -- very subtle
- Nested (depth-1) row: padding-left 40px (18 base + 22 per level)

### Columns
- Name column: flex 1, contains chevron/spacer + icon + text
- Updated column: fixed width 130px, 12.5px, color #9CA3AF
- Menu column: fixed width 24px
- Column header: 11px, semibold, tracking 0.04em, color #9CA3AF, uppercase

### Item names
- font-size 13.5px, font-weight 500, color #111827 (dark: #EDEEF0)

### Folder icon
- Filled amber SVG: fill #F5B942, 17x17px
- Must use inline SVG (not lucide Folder which is stroke-only)
- No colored badge or box background -- plain icon on white row

### File icon
- Red stroke SVG: stroke #EF4444, fill none, stroke-width 2, 15x15px

### Chevron
- Only on folders that have children (subfolders or docs)
- Color #9CA3AF, 13x13px
- ChevronRight = collapsed, ChevronDown = expanded
- Folders without children get a 13px width spacer instead

### Three-dot menu button
- Color #D1D5DB, hover to #6B7280
- Opacity-0, visible on group-hover

### Action buttons
- Upload and New Folder: bg white, border 1px #E5E7EB, radius 8px, color #374151, 12.5px, 500 weight, padding 7px 14px, shadow 0 1px 2px rgba(0,0,0,0.04)
- Bulk Import (accent): bg #1F3148, no border, white text, same size/radius/padding
- All icons are h-3.5 w-3.5 with gap-[5px]

### Confirmed direction (from HTML comment in mock)
- Plain folder icon, no colored badge/box background
- White card with real shadow and border
- Tight single-pixel row dividers instead of heavy borders
- One filled navy accent button (Bulk Import)
- Files and folders in one flat table, not separate tree-plus-panel

---

## 2. Interaction Model Change Summary

Current: left-pane folder tree (FolderNode recursive, per-node expand state) + right-pane file panel (renderFilePanel, shows selected folder's files only). Selected folder drives which files are visible.

New: single flat table. expandedFolderIds: Set<string> at FolderBrowser level. A computeVisibleRows useMemo produces a flat ordered array of { kind: 'folder'|'doc', depth, ... } rows. Folders and their docs appear in one unified list.

---

## 3. Six At-Risk Features -- Preservation Plan

### Feature 1: Folder move with cycle/depth checking

Current: getDescendantFolderIds(folderId, childrenOf) is a standalone function (lines 69-80). FolderNode calls it to build validDestinations, excluding self and all descendants.

New structure: getDescendantFolderIds is unchanged. FlatFolderRow receives childrenOf (same map) as a prop and calls the same function. Destination list built identically: folders.filter(f => f.id !== folder.id && !descendantIds.has(f.id)).

Regression risk: None. Function and input data are identical.

---

### Feature 2: Drag-and-drop with per-node drop targets

Current (bug fixed earlier tonight): Each FolderNode's onDrop handler calls onDropDoc(docId, folder.id, folder.name) -- closing over its own folder prop directly, not a shared ancestor closure.

New structure: Each FlatFolderRow receives onDropDoc as a prop AND its own folder prop. The onDrop handler is: if (docId) onDropDoc(docId, folder.id, folder.name). Same per-row closure pattern. Flat rows are independent siblings, making the per-identity binding even cleaner.

Regression risk: None. Same per-node binding pattern preserved.

---

### Feature 3: Three-dot menu fixed-position dropdown

Current: Both FolderNode and DocRow use:
- triggerRef on the button
- useLayoutEffect measuring getBoundingClientRect() to compute coords
- createPortal(dropdown, document.body) with position fixed at coords
- useEffect outside-click handler

This is DOM-position-independent: getBoundingClientRect() returns screen-space coords regardless of DOM depth; portal renders at document.body.

New structure: FlatFolderRow and FlatDocRow use the identical pattern. The DOM position of the button changes (flat row vs. tree node) but the positioning calculation is unaffected.

Regression risk: None. Pattern is explicitly DOM-position-independent.

---

### Feature 4: Finalize-lock drag-over suppression

Current enforcement points:
1. FolderNode's onDrop: calls onDropDoc which calls moveDocument which checks isFinalized
2. moveDocument() function: if (isFinalized) toast + return before any API call
3. FolderNode and DocRow destructive buttons: disabled={isFinalized}

New structure:
- FlatFolderRow onDrop: adds explicit if (isFinalized) return check
- moveDocument() unchanged -- still the ultimate guard
- FlatFolderRow and FlatDocRow buttons: disabled={isFinalized} preserved

Regression risk: Low. moveDocument is the backstop and is unchanged.

---

### Feature 5: Multi-file upload (tonight's fix)

Current: UploadModal (lines 460-667) is entirely self-contained. Receives currentFolderId from FolderBrowser.

New structure: UploadModal is NOT changed. currentFolderId is passed as null (no selected-folder concept in flat table). Uploads go to root level; user can move after. The multi-file upload logic (FileEntry type, per-file loop, partial failure/retry handling) is fully preserved.

Regression risk: None for logic. Behavior change: uploads target root level, not a selected folder.

---

### Feature 6: Recently Viewed strip click-to-open handler

Current: Strip is rendered by the parent page component (e.g., engagements/[id]/page.tsx), not inside FolderBrowser. FolderBrowser is a child rendered below the strip.

New structure: FolderBrowserProps interface is unchanged. Parent page renders FolderBrowser exactly as before. Strip sits above FolderBrowser in page layout and is unaffected.

Regression risk: None. Strip and FolderBrowser are independent components.

---

## 4. Additional Design Decisions

### updated_at field
Backend document_folder model has both created_at (line 103) and updated_at (line 108). BrowserFolder gains updated_at?: string; created_at?: string. Display: updated_at ?? created_at ?? ''.

### expandedFolderIds initial state
Starts empty (new Set<string>()) -- all folders collapsed by default.

### NewFolderModal parentFolderId
Always null (root level); no selected-folder concept.

### Archived docs
When showArchivedToggle is true and showArchived is toggled on, archived docs appear inline in the flat table under their folder with opacity-60. Toggle sits at bottom of card.

### Upload and bulk import destination
Both pass null (root level), consistent with removal of selected-folder concept.

### FolderNode removal
Replaced entirely by FlatFolderRow. FolderOpen lucide icon removed from imports.

### DocRow replacement
Replaced by FlatDocRow with flat table column layout. All business logic preserved verbatim.

---

## 5. Step 2 Sign-off

All six at-risk features have been explicitly mapped to their preservation strategy above. None requires guessing; each has a concrete answer grounded in the actual code. The implementation may proceed.
