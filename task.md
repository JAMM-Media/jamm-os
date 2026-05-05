TASK: Add channel member management to firm chat

This task updates the firmChatApi, adds a members modal, and 
wires it into the channel dropdown.

═══════════════════════════════════════════════
PART 1 — Add member API methods to firmChatApi.ts
═══════════════════════════════════════════════

FILE: frontend/src/lib/api/firmChat.ts

STEP 1A — Add ChannelMember interface after FirmMessage interface.

Find:
  export interface FirmMessage {

Replace with:
  export interface ChannelMember {
    id: string
    channelId: string
    userId: string
    userFullName: string
    userEmail: string
    addedAt: string
  }

  export interface FirmMessage {

STEP 1B — Add mapChannelMember function after mapMessage function.

Find:
  export const firmChatApi = {

Replace with:
  function mapChannelMember(raw: Record<string, unknown>): ChannelMember {
    return {
      id: String(raw.id),
      channelId: String(raw.channel_id ?? raw.channelId ?? ''),
      userId: String(raw.user_id ?? raw.userId ?? ''),
      userFullName: String(raw.user_full_name ?? raw.userFullName ?? ''),
      userEmail: String(raw.user_email ?? raw.userEmail ?? ''),
      addedAt: String(raw.added_at ?? raw.addedAt ?? ''),
    }
  }

  export const firmChatApi = {

STEP 1C — Add three new methods at the end of the firmChatApi 
object, before the closing }

Find:
  postMessage: async (channelId: string, body: string, mentions?: string[]): Promise<FirmMessage> => {
    const { data } = await api.post(`/firm-chat/channels/${channelId}/messages`, { body, mentions })
    return mapMessage(data)
  },
}

Replace with:
  postMessage: async (channelId: string, body: string, mentions?: string[]): Promise<FirmMessage> => {
    const { data } = await api.post(`/firm-chat/channels/${channelId}/messages`, { body, mentions })
    return mapMessage(data)
  },

  listMembers: async (channelId: string): Promise<ChannelMember[]> => {
    const { data } = await api.get(`/firm-chat/channels/${channelId}/members`)
    const items = Array.isArray(data) ? data : (data.items ?? [])
    return items.map(mapChannelMember)
  },

  addMember: async (channelId: string, userId: string): Promise<ChannelMember> => {
    const { data } = await api.post(
      `/firm-chat/channels/${channelId}/members`,
      null,
      { params: { user_id: userId } }
    )
    return mapChannelMember(data)
  },

  removeMember: async (channelId: string, userId: string): Promise<void> => {
    await api.delete(`/firm-chat/channels/${channelId}/members/${userId}`)
  },
}

═══════════════════════════════════════════════
PART 2 — Add member management to firm chat page
═══════════════════════════════════════════════

FILE: frontend/src/app/(dashboard)/firm-chat/page.tsx

STEP 2A — Add Users icon to the lucide-react import.

Find:
  import { MessageSquare, MoreHorizontal } from 'lucide-react'

Replace with:
  import { MessageSquare, MoreHorizontal, Users, X, UserMinus } from 'lucide-react'

STEP 2B — Add firmChatApi import.

Find:
  import api from '@/lib/api'

Replace with:
  import api from '@/lib/api'
  import { firmChatApi, type ChannelMember } from '@/lib/api/firmChat'

STEP 2C — Add members modal state after the delete modal state 
declarations.

Find:
  const [openDropdownId, setOpenDropdownId] = useState<string | null>(null)

Replace with:
  const [showMembersModal, setShowMembersModal] = useState(false)
  const [membersChannelId, setMembersChannelId] = useState('')
  const [channelMembers, setChannelMembers] = useState<ChannelMember[]>([])
  const [membersLoading, setMembersLoading] = useState(false)
  const [addMemberSearch, setAddMemberSearch] = useState('')
  const [addMemberLoading, setAddMemberLoading] = useState(false)
  const [openDropdownId, setOpenDropdownId] = useState<string | null>(null)

STEP 2D — Add openMembersModal handler after openDeleteModal handler.

Find:
  // ─── Message rendering ───────────────────────────────────────────────────

Replace with:
  const openMembersModal = async (channelId: string) => {
    setMembersChannelId(channelId)
    setShowMembersModal(true)
    setOpenDropdownId(null)
    setAddMemberSearch('')
    setMembersLoading(true)
    try {
      const members = await firmChatApi.listMembers(channelId)
      setChannelMembers(members)
    } catch {
      setChannelMembers([])
    } finally {
      setMembersLoading(false)
    }
  }

  const handleAddMember = async (userId: string) => {
    if (!membersChannelId) return
    setAddMemberLoading(true)
    try {
      const member = await firmChatApi.addMember(membersChannelId, userId)
      setChannelMembers((prev) => [...prev, member])
      setAddMemberSearch('')
    } catch {
      // silently fail — member may already exist
    } finally {
      setAddMemberLoading(false)
    }
  }

  const handleRemoveMember = async (userId: string) => {
    if (!membersChannelId) return
    try {
      await firmChatApi.removeMember(membersChannelId, userId)
      setChannelMembers((prev) => prev.filter((m) => m.userId !== userId))
    } catch {
      // silently fail
    }
  }

  // ─── Message rendering ───────────────────────────────────────────────────

STEP 2E — Add "Manage Members" option to the channel dropdown,
after the Rename button and before the Delete button.

Find:
                        <button
                          onClick={() => openRenameModal(ch.id, ch.name)}
                          className="block w-full text-left px-3 py-2 text-[13px] text-[#374151] dark:text-[#9CA3AF] hover:bg-[#D5D8DE] dark:hover:bg-[#444444] transition-colors whitespace-nowrap"
                        >
                          Rename
                        </button>

Replace with:
                        <button
                          onClick={() => openRenameModal(ch.id, ch.name)}
                          className="block w-full text-left px-3 py-2 text-[13px] text-[#374151] dark:text-[#9CA3AF] hover:bg-[#D5D8DE] dark:hover:bg-[#444444] transition-colors whitespace-nowrap"
                        >
                          Rename
                        </button>
                        <button
                          onClick={() => openMembersModal(ch.id)}
                          className="block w-full text-left px-3 py-2 text-[13px] text-[#374151] dark:text-[#9CA3AF] hover:bg-[#D5D8DE] dark:hover:bg-[#444444] transition-colors whitespace-nowrap"
                        >
                          Manage Members
                        </button>

STEP 2F — Add the Members modal JSX before the closing </AppShell> tag.

Find:
    </AppShell>

Replace with:
        {/* ── Manage Members Modal ─────────────────────────────────────── */}
        {showMembersModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center">
            <div
              className="absolute inset-0 bg-black/35"
              onClick={() => setShowMembersModal(false)}
            />
            <div className="relative z-10 w-[420px] bg-surface-card dark:bg-dark-card rounded-[10px] border border-[#C8CDD6] dark:border-[#484848] shadow-xl">
              {/* Header */}
              <div className="flex items-center justify-between px-4 py-3 border-b border-[#C8CDD6] dark:border-[#484848]">
                <div className="flex items-center gap-2">
                  <Users className="w-[14px] h-[14px] text-[#6B7280]" />
                  <span className="text-[13px] font-medium text-[#1F3148] dark:text-[#EDEEF0]">
                    Manage Members
                  </span>
                </div>
                <button
                  onClick={() => setShowMembersModal(false)}
                  className="text-[#6B7280] hover:text-[#1F3148] dark:hover:text-[#EDEEF0] transition-colors"
                >
                  <X className="w-[14px] h-[14px]" />
                </button>
              </div>

              {/* Add member search */}
              <div className="px-4 pt-3 pb-2">
                <label className={labelClass}>Add staff member</label>
                <div className="relative">
                  <input
                    type="text"
                    value={addMemberSearch}
                    onChange={(e) => setAddMemberSearch(e.target.value)}
                    placeholder="Search by name..."
                    className={inputClass}
                  />
                  {addMemberSearch && staffList.length > 0 && (
                    <div className="absolute top-full left-0 right-0 mt-1 bg-surface-card dark:bg-dark-card border border-[#C8CDD6] dark:border-[#484848] rounded-lg shadow-lg z-10 max-h-[160px] overflow-y-auto">
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
                            className="w-full text-left px-3 py-2 text-[13px] text-[#374151] dark:text-[#9CA3AF] hover:bg-[#D5D8DE] dark:hover:bg-[#444444] transition-colors disabled:opacity-50"
                          >
                            {s.name}
                          </button>
                        ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Current members list */}
              <div className="px-4 pb-4">
                <p className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] mb-2 mt-2">
                  Current Members
                </p>
                {membersLoading ? (
                  <div className="space-y-2">
                    {[...Array(3)].map((_, i) => (
                      <div key={i} className="h-8 bg-[#D5D8DE] dark:bg-[#444444] rounded animate-pulse" />
                    ))}
                  </div>
                ) : channelMembers.length === 0 ? (
                  <p className="text-[12px] text-[#6B7280] text-center py-4">
                    No members yet. Add staff above.
                  </p>
                ) : (
                  <div className="space-y-1">
                    {channelMembers.map((m) => (
                      <div
                        key={m.id}
                        className="flex items-center justify-between px-2 py-1.5 rounded-md hover:bg-[#F3F4F6] dark:hover:bg-[#333333]"
                      >
                        <div>
                          <p className="text-[13px] font-medium text-[#1F3148] dark:text-[#EDEEF0]">
                            {m.userFullName}
                          </p>
                          <p className="text-[11px] text-[#6B7280]">{m.userEmail}</p>
                        </div>
                        <button
                          onClick={() => handleRemoveMember(m.userId)}
                          className="text-[#6B7280] hover:text-[#DC2626] transition-colors p-1"
                          title="Remove member"
                        >
                          <UserMinus className="w-[13px] h-[13px]" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

    </AppShell>

No other files need to be changed.