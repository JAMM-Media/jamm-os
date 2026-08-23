# Documents Page Visual Analysis

Source: docs/design-reference/documents-mock.png
Session: 2026-08-21

---

## Layout Overview

The mock uses a full-width content area (no right sidebar in this build -- the
Filters panel and Storage gauge visible in the mock are explicitly out of scope):

- Page title "Documents" (~22-24px bold, #1F3148 navy)
- Subtitle: "Securely store, view, and share documents with your accounting team."
  (~13px muted, #6B7280)
- 4-column stat strip (same pattern as PortalTodo)
- Controls row: wide search bar (left) + Upload button (right, no New Folder -- see note)
- Tab row: All Documents | Uploaded by you | Shared with you | Favorites
- Folder grid (when no folder is active): folder cards in a grid
- Document table (white card, full width)

---

## Stat Strip (4 cards)

Same single-container pattern as PortalTodo (divide-x, no separate card borders).

| Position | Label | Value source | Subtext |
|----------|-------|-------------|---------|
| 1 | Folders | folders.length | Active folders |
| 2 | Documents | allDocuments active count | All files |
| 3 | Shared with you | count where uploaded_by === 'firm' | From your firm |
| 4 | Uploaded by you | count where uploaded_by === 'client' | Your uploads |

Value colors: navy #1F3148 for all four (no semantic color needed here).

---

## Controls Row

- Left: Search bar, placeholder "Search documents by keyword", with a search icon
  (~13px, white card, border-gray-100, rounded-lg). Width: flex-1 or fixed ~280px.
- Right: Upload button (accent color, white text, Upload icon, rounded-lg)
- NEW FOLDER BUTTON IS INTENTIONALLY OMITTED: portal clients have no folder-creation
  rights per the explicit product decision (firm-controlled folder structure).
  TaxDome/SmartVault/Financial Cents research confirmed this is the correct
  practice-management pattern. Do not add a New Folder button, even disabled.

---

## Tab Row

Active tab: underline style, #1F3148 text, 2px solid #1F3148 underline.
Inactive tabs: #6B7280 text, no underline, hover darken.

Tabs:
1. All Documents -- show all non-superseded docs
2. Uploaded by you -- filter uploaded_by === 'client'
3. Shared with you -- filter uploaded_by === 'firm'
4. Favorites -- honest placeholder: no real backend concept in this session.
   Render "No favorites yet." empty state with a note that it is coming soon.
   Do not fake functionality.

---

## Folder Grid

Shown only when no folder is active. Omitted when a folder is selected (show
breadcrumb instead). Each folder renders as a small card:
- Folder icon (Lucide Folder, #D97706 amber or #9CA3AF gray)
- Folder name (13px, #1F3148)
- Subtle white card, border-gray-100, rounded-xl
- Clickable (onClick triggers folder navigation)

Empty state if no folders: omit the folder grid section entirely.

---

## Folder Breadcrumb (when folder active)

Single bar above the document table:
- Back arrow (ChevronLeft) + "All documents" link (clickable, exits folder)
- Separator " / "
- Current folder name (non-clickable, bold)

---

## Document Table

White card, border-gray-100, overflow-hidden, rounded-xl.

Column headers (same pattern as PortalTodo "Recent documents"):
- text-[11px] font-medium, #9CA3AF, NO uppercase, NO tracking-wider
- Columns: Name | Type | Uploaded | Uploaded by | Size

Data rows:
- Name: colored file-type icon + filename (13px semibold, #1F3148, truncate)
  - PDF: red #EF4444
  - XLS/XLSX/CSV: green #10B981
  - DOC/DOCX: blue #3B82F6
  - Default: gray #9CA3AF
- Type: small pill or plain text, the file_type value (PDF, DOCX, etc.), #6B7280
- Uploaded: formatted date, #6B7280
- Uploaded by: firm name (if uploaded_by === 'firm') or "You" (if === 'client'), #6B7280
- Size: formatted file size, #6B7280
- Row bottom border: border-gray-50

---

## Empty States

- No documents at all: centered message "No documents yet. Your firm will share documents here."
- Filtered to zero: "No documents match your search." with a clear-search link
- Favorites tab: "No favorites yet. Favoriting documents is coming soon."

---

## Colors Not in Existing Tokens

- File type icon red (PDF): #EF4444 -- adding to tokens
- File type icon green (spreadsheet): #10B981 -- already exists as success-family
- File type icon blue (document): #3B82F6 -- standard blue, adding to tokens
- Folder icon amber: #D97706 -- already in tokens as "Amber warning text"

---

## What Is Explicitly Out of Scope

- New Folder button (confirmed design decision: firm-controlled folder structure)
- Favorites tab real functionality (no backend concept; honest placeholder only)
- Storage quota indicator (no confirmed product scope)
- Right sidebar Filters panel (not in CHANGE INSTRUCTIONS)
- Folder creation, rename, or delete UI of any kind
