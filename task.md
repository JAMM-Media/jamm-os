STANDING RULES:
- Never use passlib. Use bcrypt directly.
- Background tasks must create their own SessionLocal() in try/finally.

TASK: Fix firm chat member search — dynamic typeahead when adding members

FILE TO EDIT: frontend/src/app/(dashboard)/firm-chat/page.tsx

PROBLEM: The Manage Members modal has a search input for adding staff,
but staffList is only populated when showMentionPopover is true. When
the members modal opens, staffList is empty so no results ever appear.

FIX — Step 1: Add a separate state for the members modal staff list:

Add this state near the other modal state declarations (around line 830):
  const [memberSearchResults, setMemberSearchResults] = useState<StaffMember[]>([])
  const [memberSearchLoading, setMemberSearchLoading] = useState(false)

FIX — Step 2: Load staff when the members modal opens.

In the openMembersModal function, after setting setShowMembersModal(true),
add a fetch for the staff list if not already loaded:

  // Fetch staff list for member search
  if (memberSearchResults.length === 0) {
    setMemberSearchLoading(true)
    api.get('/users/').then((res) => {
      const items = Array.isArray(res.data) ? res.data : (res.data.items ?? [])
      setMemberSearchResults(items.map((u: Record<string, unknown>) => ({
        id: String(u.id),
        name: String(u.full_name ?? u.name ?? ''),
        initials: String(u.full_name ?? u.name ?? '').split(' ').map((p: string) => p[0]).join('').slice(0, 2).toUpperCase(),
      })))
    }).catch(() => {}).finally(() => setMemberSearchLoading(false))
  }

FIX — Step 3: Update the members modal search UI to use memberSearchResults
instead of staffList, and show results as soon as the input has any value
(not requiring staffList.length > 0).

Find this section in the members modal:
  {addMemberSearch && staffList.length > 0 && (
    <div ...>
      {staffList
        .filter((s) =>
          s.name.toLowerCase().includes(addMemberSearch.toLowerCase()) &&
          !channelMembers.some((m) => m.userId === s.id)
        )

Change it to:
  {addMemberSearch && (
    <div className="absolute top-full left-0 right-0 mt-1 bg-surface-card dark:bg-dark-card border border-[#C8CDD6] dark:border-[#484848] rounded-lg shadow-lg z-10 max-h-[160px] overflow-y-auto">
      {memberSearchLoading ? (
        <div className="px-3 py-2 text-[13px] text-[#6B7280]">Loading...</div>
      ) : memberSearchResults
          .filter((s) =>
            s.name.toLowerCase().includes(addMemberSearch.toLowerCase()) &&
            !channelMembers.some((m) => m.userId === s.id)
          )
          .length === 0 ? (
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
              className="w-full text-left px-3 py-2 text-[13px] text-[#374151] dark:text-[#9CA3AF] hover:bg-[#D5D8DE] dark:hover:bg-[#444444] transition-colors disabled:opacity-50"
            >
              {s.name}
            </button>
          ))
      )}
    </div>
  )}

FIX — Step 4: After a member is successfully added via handleAddMember,
clear the addMemberSearch input. The existing code already does
setAddMemberSearch('') in handleAddMember on success — confirm this is
still there, add it if not.

After making all changes, show the updated openMembersModal function
and the updated members modal search section so I can verify.