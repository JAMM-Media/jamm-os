# JAMM PX — Task Batch

Read every instruction in this file before writing a single line of code. Execute in the order listed. Do not skip steps or reorder them.

---

## STANDING RULES

- Backend: FastAPI, PostgreSQL, SQLAlchemy ORM 2.0, Pydantic v2. Never deviate from existing patterns.
- Frontend: Next.js 14 App Router, TypeScript always, Tailwind CSS, shadcn/ui.
- Every file must begin with its path comment.
- Never touch files not listed in a task's scope.
- Never add new npm or pip packages unless explicitly instructed.
- Domain language: Engagement not Project. Staff not Employee. Firm not Company. Client not Customer.

---

## TASK 1 — Fix Send Reminder: improve error visibility

**Files to edit:**
- `app/api/esign.py`
- `app/services/dropbox_sign.py`

The reminder endpoint exists and is wired correctly. The "Failed to send reminder" error means Dropbox Sign is returning a non-2xx response. The current error swallows the upstream detail. Fix it so the actual reason surfaces in the backend logs so we can diagnose it.

In `app/services/dropbox_sign.py`, find the `send_reminder` function. Update the error raise to log the full response body before raising:

```python
if not r.ok:
    import logging
    logging.getLogger(__name__).error(
        "Dropbox Sign remind failed: status=%s body=%s",
        r.status_code,
        r.text,
    )
    raise HTTPException(
        status_code=502,
        detail=f"Dropbox Sign reminder failed: {r.status_code} — {r.text}",
    )
```

In `app/api/esign.py`, find the `send_envelope_reminder` endpoint. Add a guard: if `DROPBOX_SIGN_API_KEY` is empty, return a clear 503 immediately instead of calling Dropbox Sign and getting a cryptic 401 back:

```python
from app.core.config import get_settings as _get_settings

@router.post("/envelopes/{envelope_id}/remind")
def send_envelope_reminder(
    envelope_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_manager_or_above),
):
    if not _get_settings().DROPBOX_SIGN_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Dropbox Sign is not configured. Set DROPBOX_SIGN_API_KEY in the environment."
        )
    # ... rest of the function unchanged
```

Add only the guard block at the top of the existing function. Do not rewrite the rest of it.

---

## TASK 2 — @mention text bolder and darker

**Files to edit:**
- `frontend/src/components/firm-chat/FirmChatPage.tsx` — in `renderBody`
- `frontend/src/components/notes/NotesPanel.tsx` — in `renderNoteBody`

Both currently use `className="font-semibold"` for mention spans. Update both to use a darker color as well:

```tsx
<span key={match.index} className="font-semibold text-[#1F3148] dark:text-[#EDEEF0]">
  {match[0]}
</span>
```

This makes the mention stand out with brand-blue in light mode and near-white in dark mode, on top of the semibold weight. Find all instances of the mention span in both files (there are two in `renderBody` in FirmChatPage, and one in `renderNoteBody` in NotesPanel) and apply this className to all of them.

---

## TASK 3 — @mention popover in the Notes panel compose box

**File to edit:** `frontend/src/components/notes/NotesPanel.tsx`

Add a full @mention popover to the Notes panel compose box — the same behavior as firm chat. When the user types `@` in the note textarea, a popover appears above the compose box listing staff members to select from. Selecting a name inserts `@Name ` at the cursor position.

### Step 1 — Add imports

At the top of the file, add these imports if not already present:
```tsx
import { useState, useRef, useEffect, useCallback } from 'react'
import api from '@/lib/api'
```

Check the existing import of `useState`, `useRef`, `useEffect` — they may already be imported. Only add what is missing.

### Step 2 — Add StaffMember type

Add this type near the top of the file, after the imports:
```tsx
interface StaffMember {
  id: string
  name: string
  initials: string
}
```

### Step 3 — Add getMentionQuery helper

Add this function near the top of the file, before the `renderNoteBody` function:
```tsx
function getMentionQuery(value: string, cursor: number): string | null {
  const before = value.slice(0, cursor)
  const lastAt = before.lastIndexOf('@')
  if (lastAt === -1) return null
  const afterAt = before.slice(lastAt + 1)
  if (/\n/.test(afterAt) || /\s{2}/.test(afterAt)) return null
  return afterAt
}
```

### Step 4 — Add state to NotesPanel

Inside the `NotesPanel` function body, add these state variables and refs after the existing `const textareaRef = useRef<HTMLTextAreaElement>(null)` line:

```tsx
const [showMentionPopover, setShowMentionPopover] = useState(false)
const [mentionQuery, setMentionQuery] = useState('')
const [mentionIndex, setMentionIndex] = useState(0)
const [staffList, setStaffList] = useState<StaffMember[]>([])

useEffect(() => {
  if (staffList.length === 0) {
    api.get('/users/').then((res) => {
      const items = Array.isArray(res.data) ? res.data : (res.data.items ?? [])
      setStaffList(items.map((u: Record<string, unknown>) => ({
        id: String(u.id),
        name: String(u.full_name ?? u.name ?? ''),
        initials: String(u.full_name ?? u.name ?? '')
          .split(' ')
          .map((p: string) => p[0] ?? '')
          .join('')
          .slice(0, 2)
          .toUpperCase(),
      })))
    }).catch(() => {})
  }
}, [staffList.length])

const filteredStaff = staffList.filter((s) =>
  s.name.toLowerCase().includes(mentionQuery.trim().toLowerCase())
)
```

### Step 5 — Replace onChange and onKeyDown handlers

Replace the existing `onChange` and `onKeyDown` on the textarea, and update `handleSubmit` to clear the popover state.

Replace the existing `handleKeyDown` function with:
```tsx
function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
  if (showMentionPopover && filteredStaff.length > 0) {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setMentionIndex((prev) => (prev + 1) % filteredStaff.length)
      return
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault()
      setMentionIndex((prev) => (prev - 1 + filteredStaff.length) % filteredStaff.length)
      return
    }
    if (e.key === 'Enter') {
      e.preventDefault()
      handleMentionSelect(filteredStaff[mentionIndex])
      return
    }
    if (e.key === 'Escape') {
      setShowMentionPopover(false)
      return
    }
  }
  if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
    handleSubmit()
  }
}
```

Add a new `handleBodyChange` function:
```tsx
function handleBodyChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
  const value = e.target.value
  setBody(value)
  const cursor = e.currentTarget.selectionStart
  const query = getMentionQuery(value, cursor)
  if (query !== null) {
    setMentionQuery(query)
    setShowMentionPopover(true)
    setMentionIndex(0)
  } else {
    setShowMentionPopover(false)
  }
}
```

Add a `handleMentionSelect` function:
```tsx
function handleMentionSelect(staff: StaffMember) {
  const cursor = textareaRef.current?.selectionStart ?? body.length
  const beforeCursor = body.slice(0, cursor)
  const lastAt = beforeCursor.lastIndexOf('@')
  if (lastAt !== -1) {
    const before = body.slice(0, lastAt)
    const after = body.slice(cursor)
    setBody(`${before}@${staff.name} ${after}`)
  }
  setShowMentionPopover(false)
  setTimeout(() => textareaRef.current?.focus(), 0)
}
```

Update `handleSubmit` to clear the popover on submit:
```tsx
function handleSubmit() {
  if (!body.trim()) return
  addNote(body.trim(), isPrivate)
  setBody('')
  setIsPrivate(false)
  setShowMentionPopover(false)
}
```

### Step 6 — Update the compose box JSX

Find the compose box `<div>` (the one with `className="p-4 border-t ..."`). Wrap the textarea in a relative-positioned container and add the popover above it.

Replace the existing compose box content with:

```tsx
{/* Compose box */}
<div
  className="p-4 border-t border-[0.5px] border-[#C8CDD6] dark:border-[#484848]"
  style={{ flexShrink: 0 }}
>
  <div className="relative">
    {/* @mention popover */}
    {showMentionPopover && filteredStaff.length > 0 && (
      <div
        className="absolute bottom-full left-0 right-0 mb-1 bg-surface-card dark:bg-dark-card border border-[#C8CDD6] dark:border-[#484848] rounded-lg overflow-y-auto shadow-md z-10"
        style={{ maxHeight: '200px' }}
      >
        {filteredStaff.map((staff, idx) => (
          <button
            key={staff.id}
            onMouseDown={(e) => {
              e.preventDefault()
              handleMentionSelect(staff)
            }}
            onMouseEnter={() => setMentionIndex(idx)}
            className={`flex items-center gap-2 w-full px-3 py-2 text-[13px] text-[#374151] dark:text-[#9CA3AF] transition-colors text-left ${
              idx === mentionIndex
                ? 'bg-[#D5D8DE] dark:bg-[#444444]'
                : 'hover:bg-[#D5D8DE] dark:hover:bg-[#444444]'
            }`}
          >
            <div
              className="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0"
              style={{ backgroundColor: '#4A7FA5' }}
            >
              <span className="text-white text-[10px] font-medium">{staff.initials}</span>
            </div>
            {staff.name}
          </button>
        ))}
      </div>
    )}

    <textarea
      ref={textareaRef}
      value={body}
      onChange={handleBodyChange}
      onKeyDown={handleKeyDown}
      placeholder="Add a note..."
      className="w-full rounded-[6px] border border-[0.5px] border-[#C8CDD6] focus:border-[#4A7FA5] focus:outline-none bg-[#F7F7F8] dark:bg-[#2D2D2D] text-[13px] text-[#374151] dark:text-[#9CA3AF] placeholder:text-[#9CA3AF] p-2.5 resize-none transition-colors"
      style={{ minHeight: 72 }}
    />
  </div>

  <div className="flex items-center justify-between mt-2.5">
    <label className="flex items-center gap-1.5 cursor-pointer">
      <input
        type="checkbox"
        checked={isPrivate}
        onChange={(e) => setIsPrivate(e.target.checked)}
        className="rounded border-[#C8CDD6]"
      />
      <span className="text-[11px] text-[#6B7280]">Private note</span>
    </label>
    <button
      onClick={handleSubmit}
      disabled={!body.trim()}
      className="h-8 px-3 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[12px] font-medium transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
    >
      Add Note
    </button>
  </div>
</div>
```

---

## EXECUTION ORDER

1. Task 1 — backend: dropbox_sign.py then esign.py
2. Task 2 — frontend: FirmChatPage.tsx then NotesPanel.tsx (mention color)
3. Task 3 — frontend: NotesPanel.tsx (mention popover)

After all tasks: report every file modified and confirm no TypeScript errors.
