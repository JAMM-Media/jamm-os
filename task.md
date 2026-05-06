STANDING RULES:
- Never use passlib. Use bcrypt directly.
- Background tasks must create their own SessionLocal() in try/finally.

TASK: Fix firm chat Manage Members modal — reliability + better UI

FILE TO EDIT: frontend/src/app/(dashboard)/firm-chat/page.tsx

PROBLEM 1 — Modal may not open reliably:
The openMembersModal function is called from a dropdown button. The
global mousedown handler closes the dropdown, which may interfere with
the modal opening. Additionally the overlay div inside the modal uses
onClick which may fire on the same event that opened the modal.

FIX: Add e.stopPropagation() to the Manage Members button click handler
in the dropdown so the global mousedown handler does not interfere.

Find this button:
  <button
    onClick={() => openMembersModal(ch.id)}
    className="block w-full text-left px-3 py-2 ...whitespace-nowrap"
  >
    Manage Members
  </button>

Change to:
  <button
    onClick={(e) => { e.stopPropagation(); openMembersModal(ch.id) }}
    className="block w-full text-left px-3 py-2 ...whitespace-nowrap"
  >
    Manage Members
  </button>

PROBLEM 2 — Member search still uses old staffList state:
The modal search section still references staffList instead of
memberSearchResults. This is the core bug — staffList is never
populated in this context so no results ever show.

Find this block in the modal:
  {addMemberSearch && staffList.length > 0 && (
    <div className="absolute top-full ...">
      {staffList
        .filter((s) =>
          s.name.toLowerCase().includes(addMemberSearch.toLowerCase()) &&
          !channelMembers.some((m) => m.userId === s.id)
        )
        .map((s) => (
          <button
            key={s.id}
            onClick={() => handleAddMember(s.id)}
            disabled={addMemberLoading}
            className="w-full text-left px-3 py-2 ..."
          >
            {s.name}
          </button>
        ))}
    </div>
  )}

Replace the entire block with:
  {addMemberSearch && (
    <div className="absolute top-full left-0 right-0 mt-1 bg-surface-card dark:bg-dark-card border border-[#C8CDD6] dark:border-[#484848] rounded-lg shadow-lg z-10 max-h-[160px] overflow-y-auto">
      {memberSearchLoading ? (
        <div className="px-3 py-2 text-[13px] text-[#6B7280]">Loading...</div>
      ) : memberSearchResults.filter((s) =>
          s.name.toLowerCase().includes(addMemberSearch.toLowerCase()) &&
          !channelMembers.some((m) => m.userId === s.id)
        ).length === 0 ? (
        <div className="px-3 py-2 text-[13px] text-[#6B7280]">No staff found</div>
      ) : (
        memberSearchResults
          .filter((s) =>
            s.name.toLowerCase().includes(addMemberSearch.toLowerCase()) &&
            !channelMembers.some((m) => m.userId === s.id)
          )
          .map((s) => (
            <button
              key={s.id}
              onClick={() => handleAddMember(s.id)}
              disabled={addMemberLoading}
              className="w-full text-left px-3 py-2 text-[13px] text-[#374151] dark:text-[#9CA3AF] hover:bg-[#D5D8DE] dark:hover:bg-[#444444] transition-colors disabled:opacity-50 flex items-center gap-2"
            >
              <div
                className="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 text-white text-[10px] font-medium"
                style={{ backgroundColor: '#4A7FA5' }}
              >
                {s.initials}
              </div>
              {s.name}
            </button>
          ))
      )}
    </div>
  )}

PROBLEM 3 — Also ensure openMembersModal fetches staff list.
The function should fetch the staff list when the modal opens.
Find openMembersModal and confirm it contains the staff fetch block.
If it does NOT contain this block, add it after the finally block:

  if (memberSearchResults.length === 0) {
    setMemberSearchLoading(true)
    api.get('/users/').then((res) => {
      const items = Array.isArray(res.data) ? res.data : (res.data.items ?? [])
      setMemberSearchResults(items.map((u: Record<string, unknown>) => ({
        id: String(u.id),
        name: String(u.full_name ?? u.name ?? ''),
        initials: String(u.full_name ?? u.name ?? '')
          .split(' ')
          .map((p: string) => p[0])
          .join('')
          .slice(0, 2)
          .toUpperCase(),
      })))
    }).catch(() => {}).finally(() => setMemberSearchLoading(false))
  }

If it already contains this block, do not add it again.

After making changes show:
1. The updated Manage Members button with stopPropagation
2. The updated member search block
3. Confirm whether the staff fetch was already in openMembersModal or was added