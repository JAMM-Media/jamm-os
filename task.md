STANDING RULES:
- Never use passlib. Use bcrypt directly.

TASK: Fix @mention — full name completion and full name highlighting

FILE TO EDIT: frontend/src/app/(dashboard)/firm-chat/page.tsx

PROBLEM 1 — getMentionQuery closes popover when name has a space:
The function returns null when afterAt contains a space, so typing
@Sarah Chen closes the popover after the space.

Find:
function getMentionQuery(value: string, cursor: number): string | null {
  const before = value.slice(0, cursor)
  const lastAt = before.lastIndexOf('@')
  if (lastAt === -1) return null
  const afterAt = before.slice(lastAt + 1)
  if (/\s/.test(afterAt)) return null
  return afterAt
}

Replace with:
function getMentionQuery(value: string, cursor: number): string | null {
  const before = value.slice(0, cursor)
  const lastAt = before.lastIndexOf('@')
  if (lastAt === -1) return null
  const afterAt = before.slice(lastAt + 1)
  // Allow spaces within the query so full names like "Sarah Chen" work
  // But stop if there are two consecutive spaces or a newline
  if (/\n/.test(afterAt) || /\s{2}/.test(afterAt)) return null
  return afterAt
}

PROBLEM 2 — filteredStaff uses startsWith which breaks on partial
full names with spaces:
  s.name.toLowerCase().startsWith(mentionQuery.toLowerCase())

Change to includes so "Sarah Chen" matches when query is "sarah" or
"chen" or "sarah c":
  s.name.toLowerCase().includes(mentionQuery.trim().toLowerCase())

Find:
  const filteredStaff = staffList.filter((s) =>
    s.name.toLowerCase().startsWith(mentionQuery.toLowerCase())
  )

Change to:
  const filteredStaff = staffList.filter((s) =>
    s.name.toLowerCase().includes(mentionQuery.trim().toLowerCase())
  )

PROBLEM 3 — handleMentionSelect replaces from lastAt to cursor,
but cursor is at the end of first name — so "Chen" gets left in
the compose box after selection:

Find handleMentionSelect:
  const handleMentionSelect = (staff: StaffMember) => {
    const cursor = textareaRef.current?.selectionStart ?? composeValue.length
    const lastAt = composeValue.slice(0, cursor).lastIndexOf('@')
    if (lastAt !== -1) {
      const before = composeValue.slice(0, lastAt)
      const after = composeValue.slice(cursor)
      setComposeValue(`${before}@${staff.name} ${after}`)
      setComposeMentions((prev) => [...prev, staff.name])
      setComposeMentionIds((prev) => [...prev, staff.id])
    }
    setShowMentionPopover(false)
    setTimeout(() => textareaRef.current?.focus(), 0)
  }

Replace with:
  const handleMentionSelect = (staff: StaffMember) => {
    const cursor = textareaRef.current?.selectionStart ?? composeValue.length
    const beforeCursor = composeValue.slice(0, cursor)
    const lastAt = beforeCursor.lastIndexOf('@')
    if (lastAt !== -1) {
      const before = composeValue.slice(0, lastAt)
      // Skip past everything the user typed after @ (the partial query)
      const after = composeValue.slice(cursor)
      setComposeValue(`${before}@${staff.name} ${after}`)
      setComposeMentions((prev) => [...prev, staff.name])
      setComposeMentionIds((prev) => [...prev, staff.id])
    }
    setShowMentionPopover(false)
    setTimeout(() => textareaRef.current?.focus(), 0)
  }

Note: the core logic is the same but make sure `after` uses `cursor`
not `lastAt + 1` — cursor is where the user stopped typing, so
everything after cursor is preserved and the partial query is replaced.

PROBLEM 4 — renderBody only matches first word of @mention:
The regex /@(\S+)/g stops at spaces, so @Sarah Chen only highlights
@Sarah. Fix by matching the full name from the staffMap.

The current namePatterns loop in renderBody already uses the full name
from staffMap, so the pattern `@Sarah Chen` is searched for. This
should work. But also fix the fallback regex to match multi-word names:

In the fallback section find:
  const regex = /@(\S+)/g

This only matches one word. Since we now have staffMap available,
the fallback should not be needed for new messages. Leave it as-is
for old messages — it will at least bold the first word.

After making changes show:
1. Updated getMentionQuery
2. Updated filteredStaff filter
3. Updated handleMentionSelect