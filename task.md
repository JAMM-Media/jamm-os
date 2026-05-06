STANDING RULES:
- Never use passlib. Use bcrypt directly.
- Background tasks must create their own SessionLocal() in try/finally.

TASK: Fix @mention system in firm chat — staff fetch, popover, and
      send mentions as UUIDs

FILE TO EDIT: frontend/src/app/(dashboard)/firm-chat/page.tsx

═══════════════════════════════════════════════════════════
FIX 1 — Fix staff list fetch for @mention popover
═══════════════════════════════════════════════════════════

The current fetch calls /staff which does not exist. It also expects
a plain array but /users/ returns a paginated object.

Find this useEffect:
  useEffect(() => {
    if (showMentionPopover && staffList.length === 0) {
      api.get<StaffMember[]>('/staff').then((res) => setStaffList(res.data)).catch(() => {})
    }
  }, [showMentionPopover, staffList.length])

Replace with:
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

This fetches staff once on mount rather than waiting for the popover
to open, so results are instant when @ is typed.

═══════════════════════════════════════════════════════════
FIX 2 — Store mention UUIDs separately from display names
═══════════════════════════════════════════════════════════

Currently composeMentions stores name strings. The backend expects
UUID arrays for mention validation and notification creation.

Add a new state alongside composeMentions:
  const [composeMentionIds, setComposeMentionIds] = useState<string[]>([])

Update handleMentionSelect to store both the name (for display in
compose) and the id (for sending to backend):

Find handleMentionSelect:
  const handleMentionSelect = (staff: StaffMember) => {
    const cursor = textareaRef.current?.selectionStart ?? composeValue.length
    const lastAt = composeValue.slice(0, cursor).lastIndexOf('@')
    if (lastAt !== -1) {
      const before = composeValue.slice(0, lastAt)
      const after = composeValue.slice(cursor)
      setComposeValue(`${before}@${staff.name} ${after}`)
      setComposeMentions((prev) => [...prev, staff.name])
    }
    setShowMentionPopover(false)
  }

Replace with:
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

═══════════════════════════════════════════════════════════
FIX 3 — Send mention IDs to backend, clear on send
═══════════════════════════════════════════════════════════

Update handleSend to pass composeMentionIds instead of composeMentions:

Find:
  const handleSend = () => {
    if (!composeValue.trim() || !activeChannelId) return
    sendMessage(composeValue.trim(), composeMentions)
    setComposeValue('')
    setComposeMentions([])
    setShowMentionPopover(false)
    if (textareaRef.current) textareaRef.current.style.height = '40px'
  }

Replace with:
  const handleSend = () => {
    if (!composeValue.trim() || !activeChannelId) return
    sendMessage(composeValue.trim(), composeMentionIds)
    setComposeValue('')
    setComposeMentions([])
    setComposeMentionIds([])
    setShowMentionPopover(false)
    if (textareaRef.current) textareaRef.current.style.height = '40px'
  }

Also update handleSelectChannel to clear composeMentionIds:
  Find setComposeMentions([]) in handleSelectChannel and add
  setComposeMentionIds([]) on the next line.

═══════════════════════════════════════════════════════════
FIX 4 — Add keyboard navigation to mention popover
═══════════════════════════════════════════════════════════

Add a mentionIndex state to track which item is highlighted:
  const [mentionIndex, setMentionIndex] = useState(0)

Reset it when popover opens — in handleComposeChange where
setShowMentionPopover(true) is called, also add setMentionIndex(0).

Update handleKeyDown to handle ArrowUp, ArrowDown, and Enter
when the popover is open:

Find:
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

Replace with:
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
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
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

Update the mention popover rendering to highlight the selected item.
Find the filteredStaff.map inside the popover and add a highlighted
background to the item at mentionIndex:

  filteredStaff.map((staff, idx) => (
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
  ))

After making all changes show:
1. The updated useEffect for staff fetch
2. The updated handleSend
3. The updated handleKeyDown