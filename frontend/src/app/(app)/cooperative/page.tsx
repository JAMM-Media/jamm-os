// frontend/src/app/(app)/cooperative/page.tsx
// Deliberately separate component tree from firm-chat per spec section 3.
// No imports from firm-chat hooks, API client, or utilities.
'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { Network } from 'lucide-react'
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

function isGrouped(prev: CooperativeMessage, curr: CooperativeMessage): boolean {
  if (prev.author_handle !== curr.author_handle) return false
  return new Date(curr.created_at).getTime() - new Date(prev.created_at).getTime() < GROUP_WINDOW_MS
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function DateDivider({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3 my-4">
      <div className="flex-1 h-px bg-surface-border dark:bg-dark-border" />
      <span className="text-[11px] text-[#6B7280] font-medium">{label}</span>
      <div className="flex-1 h-px bg-surface-border dark:bg-dark-border" />
    </div>
  )
}

function Avatar({ handle, size = 28 }: { handle: string; size?: number }) {
  const color = handleColor(handle)
  return (
    <div
      style={{ width: size, height: size, backgroundColor: color, flexShrink: 0 }}
      className="rounded-full"
    />
  )
}

function MessageRow({
  message,
  grouped,
}: {
  message: CooperativeMessage
  grouped: boolean
}) {
  if (grouped) {
    return (
      <div className="pl-[44px] pr-4 py-0.5 hover:bg-[#F5F5F5] dark:hover:bg-[#222222] group">
        <p className="text-[13px] text-[#374151] dark:text-[#D1D5DB] leading-relaxed whitespace-pre-wrap break-words">
          {message.body}
        </p>
      </div>
    )
  }

  return (
    <div className="flex items-start gap-3 px-4 py-1.5 hover:bg-[#F5F5F5] dark:hover:bg-[#222222] group">
      <Avatar handle={message.author_handle} size={28} />
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline gap-2 mb-0.5">
          <span className="text-[13px] font-semibold text-[#1F3148] dark:text-[#EDEEF0]">
            {message.author_handle}
          </span>
          <span className="text-[11px] text-[#6B7280]">{formatTimestamp(message.created_at)}</span>
        </div>
        <p className="text-[13px] text-[#374151] dark:text-[#D1D5DB] leading-relaxed whitespace-pre-wrap break-words">
          {message.body}
        </p>
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
        <Network className="h-5 w-5 text-[#6B7280]" />
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
        <Network className="h-5 w-5 text-[#6B7280]" />
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
  const [messages, setMessages] = useState<CooperativeMessage[]>([])
  const [compose, setCompose] = useState('')
  const [sending, setSending] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  const loadRoom = useCallback(async () => {
    try {
      const { items } = await cooperativeApi.getRooms()
      const main = items.find((r) => r.room_type === 'main')
      if (!main) return
      setMainRoomId(main.id)
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

  if (!user) return null

  if (pageState === 'loading') {
    return (
      <div className="flex flex-col h-full">
        <div className="flex items-center px-4 h-14 border-b border-surface-border dark:border-dark-border">
          <span className="font-medium text-[15px] text-brand dark:text-[#EDEEF0]">Growth Cooperative</span>
        </div>
        <div className="flex-1 flex flex-col gap-3 p-4">
          {[80, 140, 60, 100, 72].map((w, i) => (
            <div key={i} className="flex items-start gap-3">
              <div className="w-7 h-7 rounded-full bg-[#D5D8DE] dark:bg-[#444444] animate-pulse flex-shrink-0" />
              <div className="flex flex-col gap-1.5">
                <div className="h-2 rounded bg-[#D5D8DE] dark:bg-[#444444] animate-pulse" style={{ width: 80 }} />
                <div className="h-2 rounded bg-[#D5D8DE] dark:bg-[#444444] animate-pulse" style={{ width: w }} />
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (pageState === 'no-access') {
    return (
      <div className="flex flex-col h-full">
        <div className="flex items-center px-4 h-14 border-b border-surface-border dark:border-dark-border">
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

  // Build grouped message list with date dividers.
  const renderedRows: React.ReactNode[] = []
  messages.forEach((msg, i) => {
    const prev = messages[i - 1]

    // Date divider.
    if (!prev || !isSameDay(prev.created_at, msg.created_at)) {
      renderedRows.push(<DateDivider key={`divider-${msg.id}`} label={formatDateLabel(msg.created_at)} />)
    }

    const grouped = !!prev && isSameDay(prev.created_at, msg.created_at) && isGrouped(prev, msg)
    renderedRows.push(<MessageRow key={msg.id} message={msg} grouped={grouped} />)
  })

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 h-14 border-b border-surface-border dark:border-dark-border flex-shrink-0">
        <Network className="h-4 w-4 text-[#6B7280]" />
        <span className="font-medium text-[15px] text-brand dark:text-[#EDEEF0]">Growth Cooperative</span>
        <span className="text-[12px] text-[#6B7280]">Main Room</span>
      </div>

      {/* Message feed */}
      <div className="flex-1 overflow-y-auto py-2">
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full text-[13px] text-[#6B7280]">
            No messages yet. Be the first to post.
          </div>
        ) : (
          <>
            {renderedRows}
          </>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Compose */}
      <div className="flex-shrink-0 px-4 pb-4 pt-2 border-t border-surface-border dark:border-dark-border">
        <div className="flex items-end gap-2 rounded-[8px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page px-3 py-2">
          <textarea
            className="flex-1 bg-transparent resize-none text-[13px] text-brand dark:text-[#EDEEF0] placeholder:text-[#6B7280] focus:outline-none min-h-[20px] max-h-[120px]"
            placeholder="Message Growth Cooperative..."
            rows={1}
            value={compose}
            onChange={(e) => setCompose(e.target.value)}
            onKeyDown={handleKeyDown}
          />
          <button
            onClick={handleSend}
            disabled={!compose.trim() || sending}
            className="px-3 h-7 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[12px] font-medium hover:opacity-90 transition-opacity disabled:opacity-40"
          >
            Send
          </button>
        </div>
        <p className="text-[11px] text-[#9CA3AF] mt-1 px-1">Enter to send, Shift+Enter for new line</p>
      </div>
    </div>
  )
}
