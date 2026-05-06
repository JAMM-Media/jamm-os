STANDING RULES:
- Never use passlib. Use bcrypt directly.
- Background tasks must create their own SessionLocal() in try/finally.

TASK: Fix firm chat dropdown — Rename, Manage Members, Delete all broken

FILE TO EDIT: frontend/src/app/(dashboard)/firm-chat/page.tsx

PROBLEM: The global mousedown handler fires on document before React's
synthetic event system processes stopPropagation. So clicking any
dropdown item closes the dropdown before the click handler fires.

FIX — 3 changes:

CHANGE 1: Add a dropdownRef near the other refs (around line 832
where textareaRef is declared):

  const dropdownRef = useRef<HTMLDivElement>(null)

CHANGE 2: Replace the existing useEffect that listens for mousedown:

Find this exact block:
  useEffect(() => {
    if (!openDropdownId) return
    const handler = () => setOpenDropdownId(null)
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [openDropdownId])

Replace it with:
  useEffect(() => {
    if (!openDropdownId) return
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && dropdownRef.current.contains(e.target as Node)) return
      setOpenDropdownId(null)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [openDropdownId])

CHANGE 3: Attach the ref to the dropdown div and remove the
onMouseDown from it.

Find this exact block:
  <div
    className="absolute right-2 top-full mt-1 z-20 bg-surface-card dark:bg-dark-card border border-[#C8CDD6] dark:border-[#484848] rounded-lg shadow-md overflow-hidden"
    onMouseDown={(e) => e.stopPropagation()}
  >

Replace with:
  <div
    ref={dropdownRef}
    className="absolute right-2 top-full mt-1 z-20 bg-surface-card dark:bg-dark-card border border-[#C8CDD6] dark:border-[#484848] rounded-lg shadow-md overflow-hidden"
  >

Do NOT change any of the buttons inside the dropdown.
Do NOT change any other onMouseDown handlers elsewhere in the file.

After making changes show:
1. The dropdownRef declaration
2. The updated useEffect
3. The dropdown div with ref