// frontend/src/app/(app)/cooperative/page.tsx
// Deliberately separate component tree from firm-chat per spec section 3.
// No imports from firm-chat hooks, API client, or utilities.
'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { Sprout } from 'lucide-react'
import { useAuth } from '@/lib/hooks/useAuth'
import { cooperativeApi, type CooperativeMessage } from '@/lib/api/cooperative'

// ---------------------------------------------------------------------------
// Utilities (fresh, not imported from firm-chat)
// ---------------------------------------------------------------------------

const AVATAR_PALETTE = [
  '#6366F1', '#8B5CF6', '#EC4899', '#F59E0B',
  '#10B981', '#3B82F6', '#EF4444', '#F97316',
]

function handleColor(handle: string): string {
  let hash = 0
  for (let i = 0; i < handle.length; i++) {
    hash = (hash * 31 + handle.charCodeAt(i)) & 0x7fffffff
  }
  return AVATAR_PALETTE[hash % AVATAR_PALETTE.length]
}

function formatTimestamp(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true })
}

function formatDateLabel(iso: string): string {
  const d = new Date(iso)
  const today = new Date()
  const yesterday = new Date(today)
  yesterday.setDate(today.getDate() - 1)

  const sameDay = (a: Date, b: Date) =>
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()

  if (sameDay(d, today)) return 'Today'
  if (sameDay(d, yesterday)) return 'Yesterday'
  return d.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })
}

function isSameDay(a: string, b: string): boolean {
  const da = new Date(a)
  const db = new Date(b)
  return (
    da.getFullYear() === db.getFullYear() &&
    da.getMonth() === db.getMonth() &&
    da.getDate() === db.getDate()
  )
}

const GROUP_WINDOW_MS = 5 * 60 * 1000

// isGrouped uses author_handle, not author_display, so grouping is never affected by aliases.
function isGrouped(prev: CooperativeMessage, curr: CooperativeMessage): boolean {
  if (prev.author_handle !== curr.author_handle) return false
  return new Date(curr.created_at).getTime() - new Date(prev.created_at).getTime() < GROUP_WINDOW_MS
}

// ---------------------------------------------------------------------------
// Label modal
// ---------------------------------------------------------------------------

function LabelModal({
  memberId,
  currentLabel,
  onSave,
  onClose,
}: {
  memberId: string
  currentLabel: string
  onSave: (memberId: string, label: string) => Promise<void>
  onClose: () => void
}) {
  const [value, setValue] = useState(currentLabel)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    inputRef.current?.focus()
    inputRef.current?.select()
  }, [])

  const handleSave = async () => {
    if (!value.trim()) return
    setSaving(true)
    setError(null)
    try {
      await onSave(memberId, value.trim())
      onClose()
    } catch {
      setError('Failed to save label.')
      setSaving(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="bg-white dark:bg-[#2D2D2D] rounded-[10px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] shadow-lg w-[300px] p-4 flex flex-col gap-3">
        <p className="text-[13px] font-medium text-[#1F3148] dark:text-[#EDEEF0]">Label this member</p>
        <input
          ref={inputRef}
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') handleSave(); if (e.key === 'Escape') onClose() }}
          placeholder="Enter a label..."
          className="h-9 px-3 rounded-[6px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] bg-[#F7F7F8] dark:bg-[#383838] text-[13px] text-[#1F3148] dark:text-[#EDEEF0] placeholder:text-[#6B7280] focus:outline-none focus:border-[#4A7FA5] transition-colors"
        />
        {error && <p className="text-[11px] text-red-500">{error}</p>}
        <div className="flex items-center gap-2 justify-end">
          <button
            onClick={onClose}
            className="px-3 h-8 rounded-[6px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] text-[12px] text-[#6B7280] hover:bg-[#F7F7F8] dark:hover:bg-[#383838] transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !value.trim()}
            className="px-3 h-8 rounded-[6px] bg-[#3A6A94] text-white text-[12px] font-medium hover:opacity-90 transition-opacity disabled:opacity-40"
          >
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function DateDivider({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3 my-3 px-3">
      <div className="flex-1 h-px bg-[#C8CDD6] dark:bg-[#484848]" />
      <span className="text-[11px] text-[#6B7280] font-medium">{label}</span>
      <div className="flex-1 h-px bg-[#C8CDD6] dark:bg-[#484848]" />
    </div>
  )
}

function Avatar({ handle, size = 26 }: { handle: string; size?: number }) {
  return (
    <div
      style={{ width: size, height: size, backgroundColor: handleColor(handle), flexShrink: 0 }}
      className="rounded-full"
    />
  )
}

function MessageBubble({
  message,
  grouped,
  isOwn,
  displayLabel,
  onLabelClick,
}: {
  message: CooperativeMessage
  grouped: boolean
  isOwn: boolean
  displayLabel: string
  onLabelClick?: () => void
}) {
  if (isOwn) {
    return (
      <div className="flex justify-end px-3 py-[2px]">
        <div className="flex flex-col items-end max-w-[70%]">
          <div className="bg-[#3A6A94] text-white rounded-[18px] px-4 py-2 text-[14px] leading-relaxed whitespace-pre-wrap break-words">
            {message.body}
          </div>
          {!grouped && (
            <span className="text-[11px] text-[#6B7280] mt-0.5 mr-1">{formatTimestamp(message.created_at)}</span>
          )}
        </div>
      </div>
    )
  }

  // Other person's message.
  const authorElement = !grouped && (
    <button
      onClick={onLabelClick}
      className="text-[11px] text-[#6B7280] font-medium mb-0.5 ml-1 hover:text-[#4A7FA5] transition-colors text-left"
      title="Label this member"
    >
      {displayLabel}
    </button>
  )

  const avatarElement = grouped
    ? <div style={{ width: 26, flexShrink: 0 }} />
    : (
      <button
        onClick={onLabelClick}
        className="rounded-full hover:opacity-80 transition-opacity flex-shrink-0"
        title="Label this member"
      >
        <Avatar handle={message.author_handle} size={26} />
      </button>
    )

  return (
    <div className="flex items-end gap-2 px-3 py-[2px]">
      {avatarElement}
      <div className="flex flex-col max-w-[70%]">
        {authorElement}
        <div className="bg-white dark:bg-[#444444] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] text-[#1F3148] dark:text-[#EDEEF0] rounded-[18px] px-4 py-2 text-[14px] leading-relaxed whitespace-pre-wrap break-words">
          {message.body}
        </div>
        {!grouped && (
          <span className="text-[11px] text-[#6B7280] mt-0.5 ml-1">{formatTimestamp(message.created_at)}</span>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Access gate states
// ---------------------------------------------------------------------------

function OwnerGate({ onOptIn }: { onOptIn: () => Promise<void> }) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleOptIn = async () => {
    setLoading(true)
    setError(null)
    try {
      await onOptIn()
    } catch {
      setError('Failed to opt in. Please try again.')
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col items-center justify-center flex-1 py-24 gap-4">
      <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-surface-card dark:bg-dark-card border border-[0.5px] border-surface-border dark:border-dark-border">
        <Sprout className="h-5 w-5 text-[#6B7280]" />
      </div>
      <div className="text-center max-w-sm">
        <p className="text-[14px] font-medium text-brand dark:text-[#EDEEF0] mb-2">
          Join the Growth Cooperative
        </p>
        <p className="text-[12px] text-[#6B7280] mb-4">
          Connect and collaborate with accountants and firm owners across the JAMM PX community.
        </p>
        {error && <p className="text-[12px] text-red-500 mb-3">{error}</p>}
        <button
          onClick={handleOptIn}
          disabled={loading}
          className="px-4 h-9 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[13px] font-medium hover:opacity-90 transition-opacity disabled:opacity-60"
        >
          {loading ? 'Enabling...' : 'Enable Growth Cooperative'}
        </button>
      </div>
    </div>
  )
}

function MemberGate() {
  return (
    <div className="flex flex-col items-center justify-center flex-1 py-24 gap-4">
      <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-surface-card dark:bg-dark-card border border-[0.5px] border-surface-border dark:border-dark-border">
        <Sprout className="h-5 w-5 text-[#6B7280]" />
      </div>
      <div className="text-center max-w-sm">
        <p className="text-[14px] font-medium text-brand dark:text-[#EDEEF0] mb-2">
          Growth Cooperative
        </p>
        <p className="text-[12px] text-[#6B7280]">
          Your firm owner can grant you access to the Growth Cooperative. Reach out to them to request access.
        </p>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

type PageState = 'loading' | 'no-access' | 'ready'

export default function CooperativePage() {
  const { user } = useAuth()

  const [pageState, setPageState] = useState<PageState>('loading')
  const [mainRoomId, setMainRoomId] = useState<string | null>(null)
  const [myHandle, setMyHandle] = useState<string | null>(null)
  const [messages, setMessages] = useState<CooperativeMessage[]>([])
  const [compose, setCompose] = useState('')
  const [sending, setSending] = useState(false)
  const [displayOverrides, setDisplayOverrides] = useState<Record<string, string>>({})
  const [aliasTarget, setAliasTarget] = useState<{ memberId: string; currentLabel: string } | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  const loadRoom = useCallback(async () => {
    try {
      const { items, my_handle } = await cooperativeApi.getRooms()
      const main = items.find((r) => r.room_type === 'main')
      if (!main) return
      setMainRoomId(main.id)
      setMyHandle(my_handle)
      const { items: msgs } = await cooperativeApi.getMessages(main.id)
      setMessages(msgs)
      setPageState('ready')
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status
      if (status === 403) {
        setPageState('no-access')
      }
    }
  }, [])

  useEffect(() => {
    if (user) loadRoom()
  }, [user, loadRoom])

  useEffect(() => {
    if (pageState === 'ready') {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, pageState])

  const handleOptIn = async () => {
    await cooperativeApi.optIn()
    await loadRoom()
  }

  const handleSend = async () => {
    if (!compose.trim() || !mainRoomId || sending) return
    setSending(true)
    try {
      const msg = await cooperativeApi.postMessage(mainRoomId, compose.trim())
      setMessages((prev) => [...prev, msg])
      setCompose('')
    } finally {
      setSending(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleSaveAlias = async (memberId: string, label: string) => {
    await cooperativeApi.setAlias(memberId, label)
    setDisplayOverrides((prev) => ({ ...prev, [memberId]: label }))
  }

  if (!user) return null

  if (pageState === 'loading') {
    return (
      <div className="flex flex-col h-full p-4 gap-3">
        <div className="flex items-center gap-2">
          <Sprout className="h-4 w-4 text-[#6B7280]" />
          <span className="font-medium text-[15px] text-brand dark:text-[#EDEEF0]">Growth Cooperative</span>
          <span className="text-[12px] text-[#6B7280]">Main Room</span>
        </div>
        <div className="flex-1 rounded-[10px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] bg-[#E4E6EA] dark:bg-[#2D2D2D] p-4 flex flex-col gap-4">
          {[120, 200, 80, 160, 100].map((w, i) => (
            <div key={i} className={`flex items-end gap-2 ${i % 2 === 0 ? '' : 'flex-row-reverse'}`}>
              <div className="w-6 h-6 rounded-full bg-[#C8CDD6] dark:bg-[#484848] animate-pulse flex-shrink-0" />
              <div className="h-8 rounded-[16px] bg-[#C8CDD6] dark:bg-[#484848] animate-pulse" style={{ width: w }} />
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (pageState === 'no-access') {
    return (
      <div className="flex flex-col h-full">
        <div className="flex items-center gap-2 px-4 h-14 border-b border-[#C8CDD6] dark:border-[#484848]">
          <Sprout className="h-4 w-4 text-[#6B7280]" />
          <span className="font-medium text-[15px] text-brand dark:text-[#EDEEF0]">Growth Cooperative</span>
        </div>
        <div className="flex-1 flex">
          {user.role === 'firm_owner'
            ? <OwnerGate onOptIn={handleOptIn} />
            : <MemberGate />
          }
        </div>
      </div>
    )
  }

  // Build grouped bubble list with date dividers.
  const renderedRows: React.ReactNode[] = []
  messages.forEach((msg, i) => {
    const prev = messages[i - 1]
    // isOwn uses author_handle, unchanged.
    const isOwn = msg.author_handle === myHandle

    if (!prev || !isSameDay(prev.created_at, msg.created_at)) {
      renderedRows.push(<DateDivider key={`divider-${msg.id}`} label={formatDateLabel(msg.created_at)} />)
    }

    // isGrouped uses author_handle, unchanged.
    const grouped = !!prev && isSameDay(prev.created_at, msg.created_at) && isGrouped(prev, msg)

    // Effective display: override takes priority, then server-resolved author_display.
    const effectiveDisplay = msg.author_member_id && displayOverrides[msg.author_member_id]
      ? displayOverrides[msg.author_member_id]
      : (msg.author_display ?? msg.author_handle)

    renderedRows.push(
      <MessageBubble
        key={msg.id}
        message={msg}
        grouped={grouped}
        isOwn={isOwn}
        displayLabel={effectiveDisplay}
        onLabelClick={!isOwn && msg.author_member_id ? () => {
          console.log('[label click]', 'member:', msg.author_member_id)
          console.log('[label modal]', 'opening for:', msg.author_member_id!)
          setAliasTarget({ memberId: msg.author_member_id!, currentLabel: effectiveDisplay })
        } : undefined}
      />
    )
  })

  return (
    <>
      {aliasTarget && (
        <LabelModal
          memberId={aliasTarget.memberId}
          currentLabel={aliasTarget.currentLabel}
          onSave={handleSaveAlias}
          onClose={() => setAliasTarget(null)}
        />
      )}

      <div className="flex flex-col h-full p-4 gap-3">
        {/* Header */}
        <div className="flex items-center gap-2 flex-shrink-0">
          <Sprout className="h-4 w-4 text-[#6B7280]" />
          <span className="font-medium text-[15px] text-[#1F3148] dark:text-[#EDEEF0]">Growth Cooperative</span>
          <span className="text-[12px] text-[#6B7280]">Main Room</span>
        </div>

        {/* Feed card */}
        <div className="flex-1 rounded-[10px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] bg-[#E4E6EA] dark:bg-[#2D2D2D] overflow-hidden flex flex-col min-h-0">
          <div className="flex-1 overflow-y-auto py-3">
            {messages.length === 0 ? (
              <div className="flex items-center justify-center h-full text-[13px] text-[#6B7280]">
                No messages yet. Be the first to post.
              </div>
            ) : (
              renderedRows
            )}
            <div ref={bottomRef} />
          </div>
        </div>

        {/* Compose */}
        <div className="flex-shrink-0">
          <div className="flex items-end gap-2 rounded-[6px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] bg-[#F7F7F8] dark:bg-[#383838] px-3 py-2 focus-within:border-[#4A7FA5] transition-colors">
            <textarea
              className="flex-1 bg-transparent resize-none text-[14px] text-[#1F3148] dark:text-[#EDEEF0] placeholder:text-[#6B7280] focus:outline-none min-h-[20px] max-h-[120px]"
              placeholder="Message Growth Cooperative..."
              rows={1}
              value={compose}
              onChange={(e) => setCompose(e.target.value)}
              onKeyDown={handleKeyDown}
            />
            <button
              onClick={handleSend}
              disabled={!compose.trim() || sending}
              className="px-3 h-7 rounded-[6px] bg-[#3A6A94] text-white text-[12px] font-medium hover:opacity-90 transition-opacity disabled:opacity-40"
            >
              Send
            </button>
          </div>
          <p className="text-[11px] text-[#9CA3AF] mt-1 px-1">Enter to send, Shift+Enter for new line</p>
        </div>
      </div>
    </>
  )
}
