// frontend/src/app/(app)/peer-network/page.tsx
// Deliberately separate component tree from firm-chat per spec section 3.
// No imports from firm-chat hooks, API client, or utilities.
'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { Sprout, Pencil, Trash2, X, Check, Plus, ChevronLeft, ChevronRight, Smile, MessageSquare, MoreHorizontal } from 'lucide-react'
import { useAuth } from '@/lib/hooks/useAuth'
import { peerNetworkApi, type PeerNetworkMessage, type PeerNetworkRoom, type AliasEntry } from '@/lib/api/peerNetwork'
import { ConfirmModal } from '@/components/ui/ConfirmModal'

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

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days}d ago`
  const months = Math.floor(days / 30)
  return `${months}mo ago`
}

const GROUP_WINDOW_MS = 15 * 60 * 1000

// isGrouped uses author_handle, not author_display, so grouping is never affected by aliases.
function isGrouped(prev: PeerNetworkMessage, curr: PeerNetworkMessage): boolean {
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

const PEER_NETWORK_REACTIONS = ['👍', '❤️', '😂', '🎉', '👏', '💡']
const PEER_NETWORK_PICKER_ONLY_REACTIONS = ['😂', '👏', '💡']

function renderBody(body: string, isOwn = false): React.ReactNode {
  // Split on \u0000Name\u0001 markers from the server's _resolve_mentions.
  // Capturing group: odd-indexed parts (i%2===1) are mention names; even are plain text.
  const parts = body.split(/\u0000([^\u0001]*)\u0001/)
  return parts.map((part, i) =>
    i % 2 === 1
      ? <span key={i} className={isOwn ? 'font-semibold underline' : 'font-semibold text-[#2A5A84] dark:text-[#7EB8E4]'}>@{part}</span>
      : part
  )
}

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
  onEdit,
  onDelete,
  onReact,
  onReply,
  replyAuthors,
  lastReplyAt,
  isEditing,
  onEditSave,
  onEditCancel,
}: {
  message: PeerNetworkMessage
  grouped: boolean
  isOwn: boolean
  displayLabel: string
  onLabelClick?: () => void
  onEdit?: () => void
  onDelete?: () => void
  onReact?: (emoji: string) => void
  onReply?: () => void
  replyAuthors?: string[]
  lastReplyAt?: string
  isEditing?: boolean
  onEditSave?: (newBody: string) => Promise<void>
  onEditCancel?: () => void
}) {
  const [editValue, setEditValue] = useState(message.body)
  const [editSaving, setEditSaving] = useState(false)
  const editRef = useRef<HTMLTextAreaElement>(null)
  const saveRef = useRef<HTMLButtonElement>(null)
  const cancelRef = useRef<HTMLButtonElement>(null)
  const [showPicker, setShowPicker] = useState(false)
  const [pickerPinned, setPickerPinned] = useState(false)
  const pickerRef = useRef<HTMLDivElement>(null)
  const [showMoreMenu, setShowMoreMenu] = useState(false)
  const moreMenuRef = useRef<HTMLDivElement>(null)
  const [threadHovered, setThreadHovered] = useState(false)

  useEffect(() => {
    if (!pickerPinned) return
    function handleClickOutside(e: MouseEvent) {
      if (pickerRef.current && !pickerRef.current.contains(e.target as Node)) {
        setPickerPinned(false)
        setShowPicker(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [pickerPinned])

  useEffect(() => {
    if (!showMoreMenu) return
    function handleClickOutside(e: MouseEvent) {
      if (moreMenuRef.current && !moreMenuRef.current.contains(e.target as Node)) {
        setShowMoreMenu(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [showMoreMenu])

  useEffect(() => {
    if (isEditing) {
      setEditValue(message.body)
      setTimeout(() => {
        editRef.current?.focus()
        if (editRef.current) {
          editRef.current.selectionStart = editRef.current.value.length
          editRef.current.selectionEnd = editRef.current.value.length
        }
      }, 0)
    }
  }, [isEditing, message.body])

  const handleEditSave = async () => {
    if (!editValue.trim() || editSaving) return
    setEditSaving(true)
    try {
      await onEditSave?.(editValue.trim())
    } finally {
      setEditSaving(false)
    }
  }

  if (message.deleted) {
    return (
      <div className="flex items-start gap-3 px-3 py-[1px] mx-1 rounded-[6px] hover:bg-[#D5D8DE] dark:hover:bg-[#383838] transition-colors">
        <div className="w-9 flex-shrink-0" />
        <span className="text-[12px] text-[#6B7280] dark:text-[#9CA3AF] italic">
          This message was deleted
        </span>
      </div>
    )
  }

  return (
    <div className={`flex items-start gap-3 px-3 ${grouped ? 'py-[1px]' : 'mt-2 py-0.5'} mx-1 rounded-[6px] hover:bg-[#D5D8DE] dark:hover:bg-[#383838] transition-colors group`}>
      {/* Avatar column or time-gutter for grouped continuation */}
      {grouped ? (
        <div className="w-9 flex-shrink-0 flex items-center justify-end pt-[3px]">
          <span className="text-[11px] text-[#9CA3AF] opacity-0 group-hover:opacity-100 transition-opacity select-none leading-none">
            {formatTimestamp(message.created_at)}
          </span>
        </div>
      ) : (
        <button
          onClick={onLabelClick}
          className="rounded-full hover:opacity-80 transition-opacity flex-shrink-0 mt-[2px]"
          title="Label this member"
        >
          <Avatar handle={message.author_handle} size={36} />
        </button>
      )}

      {/* Content column */}
      <div className="relative flex-1 min-w-0 max-w-[840px]">
        {/* Floating toolbar -- absolute overlay, never reserves document-flow space */}
        {!isEditing && (
          <div className={`absolute -top-3 right-0 z-20 transition-opacity flex items-center gap-0.5 bg-white dark:bg-[#2D2D2D] border border-[#C8CDD6] dark:border-[#484848] rounded-[6px] shadow-lg px-2 py-1.5 ${(showPicker || (isOwn && showMoreMenu)) ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none group-hover:opacity-100 group-hover:pointer-events-auto'}`}>
            <button onClick={() => onReact?.('👍')} title="👍" className="p-1 rounded hover:bg-[#D5D8DE] dark:hover:bg-[#444444] transition-colors text-[16px] leading-none">👍</button>
            <button onClick={() => onReact?.('❤️')} title="❤️" className="p-1 rounded hover:bg-[#D5D8DE] dark:hover:bg-[#444444] transition-colors text-[16px] leading-none">❤️</button>
            <button onClick={() => onReact?.('🎉')} title="🎉" className="p-1 rounded hover:bg-[#D5D8DE] dark:hover:bg-[#444444] transition-colors text-[16px] leading-none">🎉</button>
            <div className="w-[1px] h-4 bg-[#C8CDD6] dark:bg-[#484848] mx-0.5" />
            <div
              ref={pickerRef}
              className="relative pb-1"
              onMouseEnter={() => setShowPicker(true)}
              onMouseLeave={() => { if (!pickerPinned) setShowPicker(false) }}
            >
              <button
                title="React"
                onClick={() => {
                  if (pickerPinned) { setPickerPinned(false); setShowPicker(false) }
                  else { setPickerPinned(true); setShowPicker(true) }
                }}
                className="flex items-center gap-1 px-1.5 py-1 rounded hover:bg-[#D5D8DE] dark:hover:bg-[#444444] transition-colors"
              >
                <Smile className="w-3.5 h-3.5 text-[#6B7280]" strokeWidth={2.5} />
                <span className="text-[12px] font-medium text-[#4B5563]">React</span>
              </button>
              {showPicker && (
                <div className="absolute bottom-full right-0 flex bg-white dark:bg-[#2D2D2D] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] rounded-[6px] shadow-sm p-1 gap-0.5 z-30">
                  {PEER_NETWORK_PICKER_ONLY_REACTIONS.map(e => (
                    <button key={e} onClick={() => { onReact?.(e); setPickerPinned(false); setShowPicker(false) }} className="p-1 rounded hover:bg-[#F7F7F8] dark:hover:bg-[#383838] text-[16px] leading-none">{e}</button>
                  ))}
                </div>
              )}
            </div>
            {onReply && (
              <button onClick={() => onReply()} title="Reply" className="flex items-center gap-1 px-1.5 py-1 rounded hover:bg-[#D5D8DE] dark:hover:bg-[#444444] transition-colors">
                <MessageSquare className="w-3.5 h-3.5 text-[#6B7280]" strokeWidth={2.5} />
                <span className="text-[12px] font-medium text-[#4B5563]">Reply</span>
              </button>
            )}
            {isOwn && (
              <div ref={moreMenuRef} className="relative">
                <button
                  title="More options"
                  onClick={() => setShowMoreMenu(m => !m)}
                  className="p-1 rounded hover:bg-[#D5D8DE] dark:hover:bg-[#444444] transition-colors"
                >
                  <MoreHorizontal className="w-3 h-3 text-[#6B7280]" />
                </button>
                {showMoreMenu && (
                  <div className="absolute top-full right-0 mt-0.5 bg-white dark:bg-[#2D2D2D] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] rounded-[6px] shadow-sm py-0.5 z-30 min-w-[80px]">
                    <button
                      onClick={() => { onEdit?.(); setShowMoreMenu(false) }}
                      className="flex items-center gap-1.5 w-full px-2 py-1 text-[12px] text-[#1F3148] dark:text-[#EDEEF0] hover:bg-[#F7F7F8] dark:hover:bg-[#383838] transition-colors"
                    >
                      <Pencil className="w-3 h-3 text-[#6B7280]" />
                      Edit
                    </button>
                    <button
                      onClick={() => { onDelete?.(); setShowMoreMenu(false) }}
                      className="flex items-center gap-1.5 w-full px-2 py-1 text-[12px] text-[#1F3148] dark:text-[#EDEEF0] hover:bg-[#F7F7F8] dark:hover:bg-[#383838] transition-colors"
                    >
                      <Trash2 className="w-3 h-3 text-[#6B7280]" />
                      Delete
                    </button>
                    {/* Pointer shield -- transparent overlay below dropdown, blocks next row's hover zone during mouse travel to Delete */}
                    <div className="absolute top-full left-0 right-0 h-14 z-40" />
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Header: author name + JAMM badge + timestamp + edited marker + reply-count */}
        {!grouped && (
          <div className="flex items-baseline gap-1.5 mb-0.5">
            <button
              onClick={onLabelClick}
              className="text-[16px] font-semibold text-[#1F3148] dark:text-[#EDEEF0] hover:underline transition-colors text-left"
              title="Label this member"
            >
              {displayLabel}
            </button>
            {message.is_jamm_team && (
              <span className="inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-medium bg-[#3A6A94]/10 text-[#3A6A94] dark:bg-[#7EB8E4]/10 dark:text-[#7EB8E4]">
                JAMM
              </span>
            )}
            <span className="text-[13px] text-[#9CA3AF]">{formatTimestamp(message.created_at)}</span>
            {message.edited && <span className="text-[13px] text-[#9CA3AF]">(edited)</span>}
          </div>
        )}

        {/* Message body or edit-in-place */}
        {isEditing ? (
          <div className="flex flex-col">
            <div style={{ display: 'grid' }} className="w-full">
              <textarea
                ref={editRef}
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleEditSave() }
                  if (e.key === 'Escape') onEditCancel?.()
                }}
                onBlur={(e) => {
                  if (e.relatedTarget !== saveRef.current && e.relatedTarget !== cancelRef.current) {
                    onEditCancel?.()
                  }
                }}
                className="w-full rounded-[6px] px-3 py-1.5 text-[14px] bg-[#F7F7F8] dark:bg-[#383838] text-[#1F3148] dark:text-[#EDEEF0] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] resize-none overflow-hidden focus:outline-none focus:ring-2 focus:ring-[#4A7FA5]/30"
                style={{ gridArea: '1 / 1 / 2 / 2' }}
              />
              <span
                aria-hidden
                style={{
                  gridArea: '1 / 1 / 2 / 2',
                  visibility: 'hidden',
                  pointerEvents: 'none',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  fontSize: '14px',
                  fontFamily: 'inherit',
                  padding: '6px 12px',
                }}
              >
                {editValue + ' '}
              </span>
            </div>
            <div className="flex gap-1 mt-1">
              <button
                ref={cancelRef}
                onClick={onEditCancel}
                className="p-1 rounded-full bg-[#E5E7EB] dark:bg-[#444444] text-[#6B7280] hover:bg-[#D1D5DB] dark:hover:bg-[#555555] transition-colors"
                title="Cancel edit"
              >
                <X className="w-3.5 h-3.5" />
              </button>
              <button
                ref={saveRef}
                onClick={handleEditSave}
                disabled={editSaving || !editValue.trim()}
                className="p-1 rounded-full bg-[#3A6A94] text-white hover:opacity-90 transition-opacity disabled:opacity-40"
                title="Save edit"
              >
                <Check className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        ) : (
          <p className="text-[16px] text-[#1F3148] dark:text-[#EDEEF0] leading-relaxed whitespace-pre-wrap break-words">
            {renderBody(message.body)}
          </p>
        )}

        {/* Thread preview -- shown for all top-level messages with replies */}
        {!message.parent_id && (message.reply_count ?? 0) > 0 && (
          <button
            onClick={() => onReply?.()}
            onMouseEnter={() => setThreadHovered(true)}
            onMouseLeave={() => setThreadHovered(false)}
            className={`flex items-center gap-1.5 mt-1.5 px-2 py-1 min-w-[240px] rounded-[6px] border border-[0.5px] transition-colors ${
              threadHovered
                ? 'border-[#4A7FA5] bg-[#4A7FA5]/10 dark:bg-[#4A7FA5]/10'
                : 'border-[#C8CDD6] dark:border-[#484848] bg-transparent'
            }`}
          >
            {replyAuthors && replyAuthors.length > 0 && (
              <div className="flex items-center">
                {replyAuthors.slice(0, 3).map((handle, i) => (
                  <div key={handle} style={{ marginLeft: i > 0 ? '-4px' : 0 }}>
                    <Avatar handle={handle} size={16} />
                  </div>
                ))}
              </div>
            )}
            <span className="text-[13px] font-medium text-[#4A7FA5]">{message.reply_count} {message.reply_count === 1 ? 'reply' : 'replies'}</span>
            {threadHovered ? (
              <span className="text-[13px] font-medium text-[#4A7FA5]">View thread</span>
            ) : (
              <span className="text-[13px] text-[#6B7280]">{lastReplyAt ? `Last reply ${relativeTime(lastReplyAt)}` : ''}</span>
            )}
          </button>
        )}

        {/* Reaction pills -- always visible */}
        {message.reactions && message.reactions.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1">
            {message.reactions.map(r => (
              <button
                key={r.emoji}
                onClick={() => onReact?.(r.emoji)}
                className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full text-[12px] border transition-colors ${
                  r.reacted_by_me
                    ? 'border-[#3A6A94] bg-[#3A6A94]/10 text-[#3A6A94] dark:border-[#7EB8E4] dark:text-[#7EB8E4]'
                    : 'border-[#C8CDD6] dark:border-[#484848] text-[#6B7280] hover:border-[#3A6A94]/50'
                }`}
              >
                {r.emoji} <span className="text-[11px]">{r.count}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// First-post interstitial
// ---------------------------------------------------------------------------

function FirstPostModal({ onConfirm, onCancel }: { onConfirm: () => Promise<void>; onCancel: () => void }) {
  const [confirming, setConfirming] = useState(false)

  const handleConfirm = async () => {
    setConfirming(true)
    try {
      await onConfirm()
    } finally {
      setConfirming(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
      onClick={(e) => { if (e.target === e.currentTarget) onCancel() }}
    >
      <div className="bg-white dark:bg-[#2D2D2D] rounded-[10px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] shadow-lg w-[380px] p-5 flex flex-col gap-4">
        <div className="flex flex-col gap-1">
          <p className="text-[14px] font-semibold text-[#1F3148] dark:text-[#EDEEF0]">Before you post</p>
          <p className="text-[13px] text-[#6B7280] leading-relaxed">
            The Peer Network is a shared room with members from other firms, including firms in your market. Every message you post is visible to all members.
          </p>
          <p className="text-[13px] text-[#6B7280] leading-relaxed mt-1">
            Client-identifying information does not belong here. Do not include names, descriptions, or any detail that could identify a specific client.
          </p>
        </div>
        <div className="flex items-center gap-2 justify-end">
          <button
            onClick={onCancel}
            className="px-3 h-8 rounded-[6px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] text-[12px] text-[#6B7280] hover:bg-[#F7F7F8] dark:hover:bg-[#383838] transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            disabled={confirming}
            className="px-3 h-8 rounded-[6px] bg-[#3A6A94] text-white text-[12px] font-medium hover:opacity-90 transition-opacity disabled:opacity-40"
          >
            {confirming ? 'Sending...' : 'I Understand, Continue'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// New Message modal (DM / subgroup creation)
// ---------------------------------------------------------------------------

function NewMessageModal({
  aliases,
  onClose,
  onCreated,
}: {
  aliases: AliasEntry[]
  onClose: () => void
  onCreated: (roomId: string) => void
}) {
  const [search, setSearch] = useState('')
  const [handleResults, setHandleResults] = useState<AliasEntry[]>([])
  const [selected, setSelected] = useState<AliasEntry[]>([])
  const [groupName, setGroupName] = useState('')
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const aliasResults = search
    ? aliases.filter(a => (a.label ?? a.handle).toLowerCase().startsWith(search.toLowerCase()))
    : []

  const selectedIds = new Set(selected.map(s => s.target_member_id))
  const filteredAliasResults = aliasResults.filter(a => !selectedIds.has(a.target_member_id))
  const filteredHandleResults = handleResults.filter(a => !selectedIds.has(a.target_member_id) && !filteredAliasResults.find(b => b.target_member_id === a.target_member_id))
  const results = [...filteredAliasResults, ...filteredHandleResults]

  const onSearch = async (q: string) => {
    setSearch(q)
    if (q.length >= 2) {
      try {
        const { items } = await peerNetworkApi.searchMembers(q)
        setHandleResults(items)
      } catch {}
    } else {
      setHandleResults([])
    }
  }

  const toggleSelect = (entry: AliasEntry) => {
    setSelected(prev =>
      prev.find(s => s.target_member_id === entry.target_member_id)
        ? prev.filter(s => s.target_member_id !== entry.target_member_id)
        : [...prev, entry]
    )
    setSearch('')
    setHandleResults([])
  }

  const handleCreate = async () => {
    if (selected.length === 0) return
    setCreating(true)
    setError(null)
    try {
      const roomType = selected.length === 1 ? 'dm' : 'subgroup'
      const name = roomType === 'subgroup' && groupName.trim() ? groupName.trim() : undefined
      const room = await peerNetworkApi.createRoom(roomType, selected.map(s => s.target_member_id), name)
      onCreated(room.id)
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail ?? 'Failed to create conversation.')
    } finally {
      setCreating(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="bg-white dark:bg-[#2D2D2D] rounded-[10px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] shadow-lg w-[360px] flex flex-col">
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#C8CDD6] dark:border-[#484848]">
          <p className="text-[13px] font-semibold text-[#1F3148] dark:text-[#EDEEF0]">New Message</p>
          <button onClick={onClose} className="p-1 rounded hover:bg-[#F7F7F8] dark:hover:bg-[#383838] transition-colors">
            <X className="w-3.5 h-3.5 text-[#6B7280]" />
          </button>
        </div>
        <div className="px-4 pt-3 pb-2">
          {selected.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mb-2">
              {selected.map(s => (
                <span key={s.target_member_id} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[#3A6A94]/10 text-[#3A6A94] text-[12px]">
                  {s.label ?? s.handle}
                  <button onMouseDown={() => setSelected(prev => prev.filter(p => p.target_member_id !== s.target_member_id))} className="hover:opacity-70">
                    <X className="w-2.5 h-2.5" />
                  </button>
                </span>
              ))}
            </div>
          )}
          <input
            type="text"
            value={search}
            onChange={(e) => onSearch(e.target.value)}
            placeholder="Search by alias or handle..."
            autoFocus
            className="w-full h-9 px-3 rounded-[6px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] bg-[#F7F7F8] dark:bg-[#383838] text-[13px] text-[#1F3148] dark:text-[#EDEEF0] placeholder:text-[#6B7280] focus:outline-none focus:border-[#4A7FA5] transition-colors"
          />
        </div>
        {results.length > 0 && (
          <div className="max-h-[180px] overflow-y-auto border-t border-[#C8CDD6] dark:border-[#484848]">
            {results.slice(0, 8).map(a => (
              <button
                key={a.target_member_id}
                onMouseDown={() => toggleSelect(a)}
                className="w-full text-left px-4 py-2 text-[13px] text-[#1F3148] dark:text-[#EDEEF0] hover:bg-[#F7F7F8] dark:hover:bg-[#383838] flex items-center gap-2"
              >
                <span className="font-medium">{a.label ?? a.handle}</span>
                {a.label && <span className="text-[#9CA3AF] text-[11px]">{a.handle}</span>}
              </button>
            ))}
          </div>
        )}
        {selected.length >= 2 && (
          <div className="px-4 py-2 border-t border-[#C8CDD6] dark:border-[#484848]">
            <input
              type="text"
              value={groupName}
              onChange={(e) => setGroupName(e.target.value)}
              placeholder="Group name (optional)"
              className="w-full h-8 px-3 rounded-[6px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] bg-[#F7F7F8] dark:bg-[#383838] text-[12px] text-[#1F3148] dark:text-[#EDEEF0] placeholder:text-[#6B7280] focus:outline-none focus:border-[#4A7FA5] transition-colors"
            />
          </div>
        )}
        {error && <p className="px-4 pb-2 text-[12px] text-red-500">{error}</p>}
        <div className="px-4 pb-4 pt-2 border-t border-[#C8CDD6] dark:border-[#484848]">
          <button
            onClick={handleCreate}
            disabled={selected.length === 0 || creating}
            className="w-full h-9 rounded-[6px] bg-[#3A6A94] text-white text-[13px] font-medium hover:opacity-90 transition-opacity disabled:opacity-40"
          >
            {creating ? 'Creating...' : selected.length === 1 ? 'Start DM' : 'Create Group'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Thread panel (Slack-style docked column for replies)
// ---------------------------------------------------------------------------

function ThreadPanel({
  parentMessage,
  replies,
  myHandle,
  displayOverrides,
  editingMessageId,
  onClose,
  onSendReply,
  onReact,
  onEditStart,
  onEditSave,
  onEditCancel,
  onDeleteStart,
  onLabelClick,
}: {
  parentMessage: PeerNetworkMessage
  replies: PeerNetworkMessage[]
  myHandle: string | null
  displayOverrides: Record<string, string>
  editingMessageId: string | null
  onClose: () => void
  onSendReply: (body: string) => Promise<void>
  onReact: (messageId: string, emoji: string) => void
  onEditStart: (messageId: string) => void
  onEditSave: (messageId: string, newBody: string) => Promise<void>
  onEditCancel: () => void
  onDeleteStart: (messageId: string) => void
  onLabelClick: (memberId: string, currentLabel: string) => void
}) {
  const [compose, setCompose] = useState('')
  const [sending, setSending] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [replies])

  const handleSend = async () => {
    if (!compose.trim() || sending) return
    setSending(true)
    try {
      await onSendReply(compose.trim())
      setCompose('')
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="w-80 flex-shrink-0 border-l border-[#C8CDD6] dark:border-[#484848] flex flex-col bg-white dark:bg-[#1E1E1E]">
      <div className="flex items-center justify-between px-4 py-3 border-b border-[#C8CDD6] dark:border-[#484848] flex-shrink-0">
        <span className="text-[13px] font-semibold text-[#1F3148] dark:text-[#EDEEF0]">Thread</span>
        <button onClick={onClose} className="p-1 rounded hover:bg-[#F7F7F8] dark:hover:bg-[#383838] transition-colors">
          <X className="w-3.5 h-3.5 text-[#6B7280]" />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto">
        {/* Parent message */}
        {(() => {
          const isParentOwn = parentMessage.author_handle === myHandle
          const parentDisplay = parentMessage.author_member_id && displayOverrides[parentMessage.author_member_id]
            ? displayOverrides[parentMessage.author_member_id]
            : (parentMessage.author_display ?? parentMessage.author_handle)
          return (
            <div className="border-b border-[#C8CDD6] dark:border-[#484848] py-1">
              <MessageBubble
                message={parentMessage}
                grouped={false}
                isOwn={isParentOwn}
                displayLabel={parentDisplay}
                onLabelClick={!isParentOwn && parentMessage.author_member_id ? () => onLabelClick(parentMessage.author_member_id!, parentDisplay) : undefined}
                onEdit={isParentOwn && !parentMessage.deleted ? () => onEditStart(parentMessage.id) : undefined}
                onDelete={isParentOwn && !parentMessage.deleted ? () => onDeleteStart(parentMessage.id) : undefined}
                onReact={!parentMessage.deleted ? (emoji) => onReact(parentMessage.id, emoji) : undefined}
                onReply={undefined}
                isEditing={editingMessageId === parentMessage.id}
                onEditSave={isParentOwn ? (newBody) => onEditSave(parentMessage.id, newBody) : undefined}
                onEditCancel={onEditCancel}
              />
            </div>
          )
        })()}
        {/* Replies */}
        <div className="py-1">
          {replies.length === 0 && (
            <p className="text-[12px] text-[#9CA3AF] text-center py-4">No replies yet.</p>
          )}
          {replies.map(msg => {
            const isReplyOwn = msg.author_handle === myHandle
            const replyDisplay = msg.author_member_id && displayOverrides[msg.author_member_id]
              ? displayOverrides[msg.author_member_id]
              : (msg.author_display ?? msg.author_handle)
            return (
              <MessageBubble
                key={msg.id}
                message={msg}
                grouped={false}
                isOwn={isReplyOwn}
                displayLabel={replyDisplay}
                onLabelClick={!isReplyOwn && msg.author_member_id ? () => onLabelClick(msg.author_member_id!, replyDisplay) : undefined}
                onEdit={isReplyOwn && !msg.deleted ? () => onEditStart(msg.id) : undefined}
                onDelete={isReplyOwn && !msg.deleted ? () => onDeleteStart(msg.id) : undefined}
                onReact={!msg.deleted ? (emoji) => onReact(msg.id, emoji) : undefined}
                onReply={undefined}
                isEditing={editingMessageId === msg.id}
                onEditSave={isReplyOwn ? (newBody) => onEditSave(msg.id, newBody) : undefined}
                onEditCancel={onEditCancel}
              />
            )
          })}
          <div ref={bottomRef} />
        </div>
      </div>
      <div className="px-3 py-2 border-t border-[#C8CDD6] dark:border-[#484848] flex-shrink-0">
        <div className="flex items-center gap-2 rounded-[6px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] bg-[#F7F7F8] dark:bg-[#383838] px-3 py-2 focus-within:border-[#4A7FA5] transition-colors">
          <textarea
            className="flex-1 bg-transparent resize-none text-[13px] text-[#1F3148] dark:text-[#EDEEF0] placeholder:text-[#6B7280] focus:outline-none min-h-[20px] max-h-[80px] overflow-y-auto"
            placeholder="Reply..."
            rows={1}
            value={compose}
            onChange={(e) => {
              setCompose(e.target.value)
              e.target.style.height = 'auto'
              e.target.style.height = e.target.scrollHeight + 'px'
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
            }}
          />
          <button
            onClick={handleSend}
            disabled={!compose.trim() || sending}
            className="px-2 h-6 rounded-[4px] bg-[#3A6A94] text-white text-[11px] font-medium hover:opacity-90 transition-opacity disabled:opacity-40"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Terms modal
// ---------------------------------------------------------------------------

function TermsModal({ onAccept }: { onAccept: () => Promise<void> }) {
  const [accepting, setAccepting] = useState(false)

  const handleAccept = async () => {
    setAccepting(true)
    try {
      await onAccept()
    } finally {
      setAccepting(false)
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 px-4 h-14 border-b border-[#C8CDD6] dark:border-[#484848]">
        <Sprout className="h-4 w-4 text-[#6B7280]" />
        <span className="font-medium text-[15px] text-brand dark:text-[#EDEEF0]">Peer Network</span>
      </div>
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-[560px] mx-auto flex flex-col gap-5">
          <div>
            <p className="text-[15px] font-semibold text-[#1F3148] dark:text-[#EDEEF0] mb-1">Before you enter</p>
            <p className="text-[13px] text-[#6B7280]">Please read and agree to the following before accessing the Peer Network.</p>
          </div>
          <ol className="flex flex-col gap-3 list-decimal list-inside marker:text-[#6B7280] marker:text-[13px]">
            <li className="text-[13px] text-[#1F3148] dark:text-[#EDEEF0] leading-relaxed">
              <span className="font-medium">You are responsible for what you share.</span> Everything you post about yourself, your firm, your clients, or your business is your responsibility. JAMM does not vet, endorse, or take responsibility for member posts.
            </li>
            <li className="text-[13px] text-[#1F3148] dark:text-[#EDEEF0] leading-relaxed">
              <span className="font-medium">Never post client-identifying information.</span> Do not share any details that could identify a specific client, including names, industries, locations, or descriptions that make a client recognizable. This is a firm boundary, not a guideline.
            </li>
            <li className="text-[13px] text-[#1F3148] dark:text-[#EDEEF0] leading-relaxed">
              <span className="font-medium">This room is pseudonymous, not anonymous.</span> Your handle is permanent and consistent across all your sessions. Other members will recognize patterns in what you share over time. Do not assume you cannot be identified by the content of your posts.
            </li>
            <li className="text-[13px] text-[#1F3148] dark:text-[#EDEEF0] leading-relaxed">
              <span className="font-medium">Other members may be your competitors.</span> The Peer Network includes firms in your geographic market. Members you interact with may recruit your staff, compete for your clients, or both. You participate knowing this.
            </li>
            <li className="text-[13px] text-[#1F3148] dark:text-[#EDEEF0] leading-relaxed">
              <span className="font-medium">Mutes are permanent pending appeal.</span> If your access is muted for violating these terms, the mute does not expire automatically. You may appeal to JAMM, but reinstatement is not guaranteed.
            </li>
            <li className="text-[13px] text-[#1F3148] dark:text-[#EDEEF0] leading-relaxed">
              <span className="font-medium">Messages persist after you leave.</span> If you leave the platform or your firm deactivates, your past messages remain visible to current members. They are not deleted on your departure.
            </li>
            <li className="text-[13px] text-[#1F3148] dark:text-[#EDEEF0] leading-relaxed">
              <span className="font-medium">Screenshots expose your private labels.</span> If you take a screenshot of the Peer Network, any private labels you have attached to other members will appear in your screenshot alongside their messages. You are responsible for what those screenshots reveal about how you have identified others.
            </li>
            <li className="text-[13px] text-[#1F3148] dark:text-[#EDEEF0] leading-relaxed">
              <span className="font-medium">JAMM may remove any message.</span> JAMM reserves the right to remove any message from the Peer Network at any time, for any reason, without prior notice.
            </li>
          </ol>
          <button
            onClick={handleAccept}
            disabled={accepting}
            className="w-full h-10 rounded-[8px] bg-[#3A6A94] text-white text-[14px] font-medium hover:opacity-90 transition-opacity disabled:opacity-40"
          >
            {accepting ? 'Saving...' : 'I Understand and Agree'}
          </button>
        </div>
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
          Join the Peer Network
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
          {loading ? 'Enabling...' : 'Enable Peer Network'}
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
          Peer Network
        </p>
        <p className="text-[12px] text-[#6B7280]">
          Your firm owner can grant you access to the Peer Network. Reach out to them to request access.
        </p>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

type PageState = 'loading' | 'no-access' | 'needs-terms' | 'ready'

export default function PeerNetworkPage() {
  const { user } = useAuth()

  const [pageState, setPageState] = useState<PageState>('loading')
  const [rooms, setRooms] = useState<PeerNetworkRoom[]>([])
  const [activeRoomId, setActiveRoomId] = useState<string | null>(null)
  const [myHandle, setMyHandle] = useState<string | null>(null)
  const [messages, setMessages] = useState<PeerNetworkMessage[]>([])
  const [compose, setCompose] = useState('')
  const [sending, setSending] = useState(false)
  const [displayOverrides, setDisplayOverrides] = useState<Record<string, string>>({})
  const [aliasTarget, setAliasTarget] = useState<{ memberId: string; currentLabel: string } | null>(null)
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null)
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)
  const [myHasPosted, setMyHasPosted] = useState(false)
  const [myIsMuted, setMyIsMuted] = useState(false)
  const [myMutedReason, setMyMutedReason] = useState<string | null>(null)
  const [showFirstPostModal, setShowFirstPostModal] = useState(false)
  const [showNewMessageModal, setShowNewMessageModal] = useState(false)
  const [openThreadParentId, setOpenThreadParentId] = useState<string | null>(null)
  const [aliases, setAliases] = useState<AliasEntry[]>([])
  const [mentionSearch, setMentionSearch] = useState<string | null>(null)
  const [mentionResults, setMentionResults] = useState<AliasEntry[]>([])
  const [mentionReplacements, setMentionReplacements] = useState<Array<{ display: string; token: string }>>([])
  const bottomRef = useRef<HTMLDivElement>(null)
  const composeRef = useRef<HTMLTextAreaElement>(null)

  const loadRoom = useCallback(async (keepActiveRoomId?: string) => {
    try {
      const { items, my_handle, has_posted, is_muted, muted_reason } = await peerNetworkApi.getRooms()
      setRooms(items)
      setMyHandle(my_handle)
      setMyHasPosted(has_posted)
      setMyIsMuted(is_muted)
      setMyMutedReason(muted_reason)
      const targetId = keepActiveRoomId ?? items.find((r) => r.room_type === 'main')?.id ?? items[0]?.id
      if (!targetId) return
      setActiveRoomId(targetId)
      const { items: msgs } = await peerNetworkApi.getMessages(targetId)
      setMessages(msgs)
      setPageState('ready')
      try {
        const { items: myAliases } = await peerNetworkApi.getAliases()
        setAliases(myAliases)
      } catch {}
    } catch (err: unknown) {
      const res = (err as { response?: { status?: number; data?: { detail?: string } } })?.response
      if (res?.status === 403) {
        if (res?.data?.detail === 'Terms and conditions must be accepted before accessing the Peer Network.') {
          setPageState('needs-terms')
        } else {
          setPageState('no-access')
        }
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
    await peerNetworkApi.optIn()
    await loadRoom()
  }

  const handleAcceptTerms = async () => {
    await peerNetworkApi.acceptTerms()
    await loadRoom()
  }

  const switchRoom = useCallback(async (roomId: string) => {
    if (roomId === activeRoomId) return
    setActiveRoomId(roomId)
    setMessages([])
    setEditingMessageId(null)
    setCompose('')
    setMentionSearch(null)
    setMentionResults([])
    setMentionReplacements([])
    try {
      const { items: msgs } = await peerNetworkApi.getMessages(roomId)
      setMessages(msgs)
    } catch {}
  }, [activeRoomId])

  const getRoomDisplayName = (room: PeerNetworkRoom): string => {
    if (room.room_type === 'main') return 'Main Room'
    if (room.room_type === 'announcements') return 'Announcements'
    if (room.room_type === 'dm') return room.dm_display ?? 'Direct Message'
    return room.name ?? 'Unnamed Group'
  }

  const activeRoomDisplayName = (() => {
    const r = rooms.find(r => r.id === activeRoomId)
    return r ? getRoomDisplayName(r) : 'Peer Network'
  })()

  const sortedRooms = [
    ...rooms.filter(r => r.room_type === 'main'),
    ...rooms.filter(r => r.room_type === 'announcements'),
    ...rooms.filter(r => r.room_type === 'dm'),
    ...rooms.filter(r => r.room_type === 'subgroup'),
  ]

  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false
    return localStorage.getItem('pn_sidebar_collapsed') === 'true'
  })

  const toggleSidebar = () => {
    setSidebarCollapsed(prev => {
      const next = !prev
      localStorage.setItem('pn_sidebar_collapsed', String(next))
      return next
    })
  }

  const handleHideRoom = async (roomId: string) => {
    try {
      await peerNetworkApi.hideRoom(roomId)
      setRooms(prev => prev.filter(r => r.id !== roomId))
      if (activeRoomId === roomId) {
        const main = rooms.find(r => r.room_type === 'main')
        if (main) switchRoom(main.id)
      }
    } catch {}
  }

  const encodeBody = (text: string, replacements: Array<{ display: string; token: string }>) => {
    let encoded = text
    // Sort longest display first to avoid partial-match replacements.
    const sorted = [...replacements].sort((a, b) => b.display.length - a.display.length)
    for (const { display, token } of sorted) {
      encoded = encoded.split('@' + display).join(token)
    }
    return encoded
  }

  const doSend = async () => {
    if (!compose.trim() || !activeRoomId || sending) return
    setSending(true)
    try {
      const encodedBody = encodeBody(compose.trim(), mentionReplacements)
      const msg = await peerNetworkApi.postMessage(activeRoomId!, encodedBody)
      setMessages((prev) => [...prev, msg])
      setCompose('')
      if (composeRef.current) { composeRef.current.style.height = 'auto' }
      setMyHasPosted(true)
      setMentionReplacements([])
    } finally {
      setSending(false)
    }
  }

  const handleSend = async () => {
    if (!compose.trim() || !activeRoomId || sending) return
    if (!myHasPosted) {
      setShowFirstPostModal(true)
      return
    }
    await doSend()
  }

  const handleFirstPostConfirm = async () => {
    setShowFirstPostModal(false)
    await doSend()
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleSaveAlias = async (memberId: string, label: string) => {
    await peerNetworkApi.setAlias(memberId, label)
    setDisplayOverrides((prev) => ({ ...prev, [memberId]: label }))
  }

  const handleEditSave = async (messageId: string, newBody: string) => {
    const result = await peerNetworkApi.editMessage(messageId, newBody)
    setMessages((prev) =>
      prev.map((m) => m.id === messageId ? { ...m, body: result.body, edited: true } : m)
    )
    setEditingMessageId(null)
  }

  const handleDelete = async (messageId: string) => {
    await peerNetworkApi.deleteMessage(messageId)
    setMessages((prev) =>
      prev.map((m) => m.id === messageId ? { ...m, deleted: true, body: '[deleted]' } : m)
    )
    setConfirmDeleteId(null)
  }

  const handleReact = async (messageId: string, emoji: string) => {
    try {
      const result = await peerNetworkApi.toggleReaction(messageId, emoji)
      setMessages((prev) =>
        prev.map((m) => m.id === messageId ? { ...m, reactions: result.reactions } : m)
      )
    } catch {}
  }

  const handleSendReply = async (body: string) => {
    if (!activeRoomId || !openThreadParentId) return
    const msg = await peerNetworkApi.postMessage(activeRoomId, body, openThreadParentId)
    setMessages((prev) => [
      ...prev.map((m) =>
        m.id === openThreadParentId ? { ...m, reply_count: (m.reply_count ?? 0) + 1 } : m
      ),
      msg,
    ])
  }

  if (!user) return null

  if (pageState === 'loading') {
    return (
      <div className="flex flex-col h-full p-4 gap-3">
        <div className="flex items-center gap-2">
          <Sprout className="h-4 w-4 text-[#6B7280]" />
          <span className="font-medium text-[15px] text-brand dark:text-[#EDEEF0]">Peer Network</span>
          <span className="text-[12px] text-[#6B7280]">Loading...</span>
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
          <span className="font-medium text-[15px] text-brand dark:text-[#EDEEF0]">Peer Network</span>
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

  if (pageState === 'needs-terms') {
    return <TermsModal onAccept={handleAcceptTerms} />
  }

  // Build grouped bubble list with date dividers.
  const renderedRows: React.ReactNode[] = []
  messages.forEach((msg, i) => {
    const prev = messages[i - 1]
    if (msg.parent_id) return
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

    const msgReplies = !msg.parent_id && (msg.reply_count ?? 0) > 0 ? messages.filter(m => m.parent_id === msg.id) : []
    const msgReplyAuthors = msgReplies.length > 0
      ? Array.from(new Set(msgReplies.map(m => m.author_handle))).slice(0, 3)
      : undefined
    const msgLastReplyAt = msgReplies.length > 0
      ? msgReplies.reduce((latest, m) => m.created_at > latest ? m.created_at : latest, msgReplies[0].created_at)
      : undefined
    renderedRows.push(
      <MessageBubble
        key={msg.id}
        message={msg}
        grouped={grouped}
        isOwn={isOwn}
        displayLabel={effectiveDisplay}
        onLabelClick={!isOwn && msg.author_member_id ? () => {
          setAliasTarget({ memberId: msg.author_member_id!, currentLabel: effectiveDisplay })
        } : undefined}
        onEdit={isOwn && !msg.deleted ? () => setEditingMessageId(msg.id) : undefined}
        onDelete={isOwn && !msg.deleted ? () => setConfirmDeleteId(msg.id) : undefined}
        onReact={!msg.deleted ? (emoji) => handleReact(msg.id, emoji) : undefined}
        onReply={!msg.deleted && !msg.parent_id ? () => setOpenThreadParentId(msg.id) : undefined}
        replyAuthors={msgReplyAuthors}
        lastReplyAt={msgLastReplyAt}
        isEditing={editingMessageId === msg.id}
        onEditSave={isOwn ? (newBody) => handleEditSave(msg.id, newBody) : undefined}
        onEditCancel={() => setEditingMessageId(null)}
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

      {showFirstPostModal && (
        <FirstPostModal
          onConfirm={handleFirstPostConfirm}
          onCancel={() => setShowFirstPostModal(false)}
        />
      )}

      <ConfirmModal
        open={confirmDeleteId !== null}
        message="Delete this message? It will show as deleted to everyone."
        confirmLabel="Delete"
        destructive={true}
        onConfirm={() => { if (confirmDeleteId) handleDelete(confirmDeleteId) }}
        onCancel={() => setConfirmDeleteId(null)}
      />

      {showNewMessageModal && (
        <NewMessageModal
          aliases={aliases}
          onClose={() => setShowNewMessageModal(false)}
          onCreated={async (roomId) => {
            setShowNewMessageModal(false)
            await loadRoom(roomId)
          }}
        />
      )}

      <div className="flex h-full">
        {/* Room sidebar */}
        <div className={`flex-shrink-0 border-r border-[#C8CDD6] dark:border-[#484848] flex flex-col bg-[#F7F7F8] dark:bg-[#252525] ${sidebarCollapsed ? 'w-8' : 'w-52'}`}>
          {sidebarCollapsed ? (
            <div className="flex flex-col items-center pt-2">
              <button
                onClick={toggleSidebar}
                title="Expand sidebar"
                className="p-1.5 rounded hover:bg-[#E4E6EA] dark:hover:bg-[#383838] transition-colors"
              >
                <ChevronRight className="w-3.5 h-3.5 text-[#6B7280]" />
              </button>
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between px-3 py-3 border-b border-[#C8CDD6] dark:border-[#484848]">
                <div className="flex items-center gap-1.5">
                  <Sprout className="h-3.5 w-3.5 text-[#6B7280]" />
                  <span className="text-[12px] font-semibold text-[#1F3148] dark:text-[#EDEEF0]">Peer Network</span>
                </div>
                <div className="flex items-center gap-0.5">
                  <button
                    onClick={() => setShowNewMessageModal(true)}
                    title="New Message"
                    className="p-1 rounded hover:bg-[#E4E6EA] dark:hover:bg-[#383838] transition-colors"
                  >
                    <Plus className="w-3.5 h-3.5 text-[#6B7280]" />
                  </button>
                  <button
                    onClick={toggleSidebar}
                    title="Collapse sidebar"
                    className="p-1 rounded hover:bg-[#E4E6EA] dark:hover:bg-[#383838] transition-colors"
                  >
                    <ChevronLeft className="w-3.5 h-3.5 text-[#6B7280]" />
                  </button>
                </div>
              </div>
              <div className="flex-1 overflow-y-auto py-1">
                {sortedRooms.map(room => (
                  <div key={room.id} className="group relative flex items-center">
                    <button
                      onClick={() => switchRoom(room.id)}
                      className={`flex-1 text-left px-3 py-2 text-[12px] transition-colors truncate pr-7 ${
                        activeRoomId === room.id
                          ? 'bg-[#3A6A94]/10 text-[#3A6A94] dark:text-[#7EB8E4] font-medium'
                          : 'text-[#374151] dark:text-[#D1D5DB] hover:bg-[#E4E6EA] dark:hover:bg-[#383838]'
                      }`}
                    >
                      {getRoomDisplayName(room)}
                    </button>
                    {(room.room_type === 'dm' || room.room_type === 'subgroup') && (
                      <button
                        onClick={(e) => { e.stopPropagation(); handleHideRoom(room.id) }}
                        title="Hide conversation"
                        className="absolute right-1.5 p-0.5 rounded opacity-0 group-hover:opacity-100 transition-opacity hover:bg-[#D5D8DE] dark:hover:bg-[#444444]"
                      >
                        <X className="w-3 h-3 text-[#6B7280]" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

        {/* Main feed column */}
        <div className="flex flex-col flex-1 min-w-0 min-h-0 p-4 gap-3">
        {/* Header */}
        <div className="flex items-center gap-2 flex-shrink-0">
          <span className="font-medium text-[15px] text-[#1F3148] dark:text-[#EDEEF0]">{activeRoomDisplayName}</span>
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
          {rooms.find(r => r.id === activeRoomId)?.room_type === 'announcements' && user.role !== 'system_admin' ? (
            <div className="rounded-[6px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] bg-[#F7F7F8] dark:bg-[#383838] px-4 py-3">
              <p className="text-[12px] text-[#6B7280] dark:text-[#9CA3AF]">Announcements is read-only. Only the JAMM team can post here.</p>
            </div>
          ) : myIsMuted ? (
            <div className="rounded-[6px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] bg-[#F7F7F8] dark:bg-[#383838] px-4 py-3">
              <p className="text-[13px] font-medium text-[#374151] dark:text-[#EDEEF0] mb-1">Your account has been muted</p>
              <p className="text-[12px] text-[#6B7280] dark:text-[#9CA3AF] leading-relaxed">
                {myMutedReason}
              </p>
              <p className="text-[12px] text-[#6B7280] dark:text-[#9CA3AF] mt-2">
                To appeal, contact{' '}
                <a href="mailto:appeals@jammpx.com" className="text-[#4A7FA5] hover:underline">appeals@jammpx.com</a>.
              </p>
            </div>
          ) : (
            <>
              {mentionSearch !== null && mentionResults.length > 0 && (
                <div className="mb-1 rounded-[6px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] bg-white dark:bg-[#2D2D2D] shadow-sm overflow-hidden">
                  {mentionResults.slice(0, 5).map((a) => (
                    <button
                      key={a.target_member_id}
                      onMouseDown={(e) => {
                        e.preventDefault()
                        const displayName = a.label ?? a.handle
                        const token = `@{${a.target_member_id}}`
                        // Replace the @partial in compose with the display name.
                        setCompose((prev) => {
                          const atIdx = prev.lastIndexOf('@')
                          if (atIdx === -1) return prev
                          return prev.slice(0, atIdx) + '@' + displayName + ' ' + prev.slice(atIdx + 1 + (mentionSearch?.length ?? 0))
                        })
                        setMentionReplacements((prev) => [
                          ...prev.filter(r => r.display !== displayName),
                          { display: displayName, token },
                        ])
                        setMentionSearch(null)
                        setMentionResults([])
                        composeRef.current?.focus()
                      }}
                      className="w-full text-left px-3 py-2 text-[13px] text-[#1F3148] dark:text-[#EDEEF0] hover:bg-[#F7F7F8] dark:hover:bg-[#383838] flex items-center gap-2"
                    >
                      <span className="font-medium">{a.label ?? a.handle}</span>
                      {a.label && <span className="text-[#9CA3AF] text-[11px]">{a.handle}</span>}
                    </button>
                  ))}
                </div>
              )}
              <div className="flex items-center gap-2 rounded-[6px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] bg-[#F7F7F8] dark:bg-[#383838] px-3 py-2 focus-within:border-[#4A7FA5] transition-colors">
                <textarea
                  ref={composeRef}
                  className="flex-1 bg-transparent resize-none text-[14px] text-[#1F3148] dark:text-[#EDEEF0] placeholder:text-[#6B7280] focus:outline-none min-h-[20px] max-h-[120px] overflow-y-auto"
                  placeholder="Message Peer Network..."
                  rows={1}
                  value={compose}
                  onChange={(e) => {
                    const val = e.target.value
                    setCompose(val)
                    e.target.style.height = 'auto'
                    e.target.style.height = e.target.scrollHeight + 'px'
                    // Detect @ trigger for mention autocomplete.
                    const cursor = e.target.selectionStart ?? val.length
                    const before = val.slice(0, cursor)
                    const atMatch = before.match(/@(\S*)$/)
                    if (atMatch) {
                      const q = atMatch[1].toLowerCase()
                      const aliasHits = aliases.filter(a => a.label?.toLowerCase().startsWith(q))
                      setMentionResults(aliasHits)
                      setMentionSearch(q)
                    } else {
                      setMentionSearch(null)
                      setMentionResults([])
                    }
                  }}
                  onKeyDown={(e) => {
                if (mentionSearch !== null && mentionResults.length > 0 && e.key === 'Escape') {
                  setMentionSearch(null)
                  setMentionResults([])
                  return
                }
                handleKeyDown(e)
              }}
                />
                <button
                  onClick={handleSend}
                  disabled={!compose.trim() || sending}
                  className="px-3 h-7 rounded-[6px] bg-[#3A6A94] text-white text-[12px] font-medium hover:opacity-90 transition-opacity disabled:opacity-40"
                >
                  Send
                </button>
              </div>
              <div className="flex items-center justify-between mt-1 px-1">
                <p className="text-[11px] text-[#6B7280] dark:text-[#9CA3AF]">Remember: no client-identifying information</p>
                <p className="text-[11px] text-[#9CA3AF]">Enter to send, Shift+Enter for new line</p>
              </div>
            </>
          )}
        </div>
        </div>
        {/* Thread panel */}
        {openThreadParentId && (() => {
          const parent = messages.find(m => m.id === openThreadParentId)
          if (!parent) return null
          const replies = messages.filter(m => m.parent_id === openThreadParentId)
          return (
            <ThreadPanel
              parentMessage={parent}
              replies={replies}
              myHandle={myHandle}
              displayOverrides={displayOverrides}
              editingMessageId={editingMessageId}
              onClose={() => setOpenThreadParentId(null)}
              onSendReply={handleSendReply}
              onReact={handleReact}
              onEditStart={setEditingMessageId}
              onEditSave={handleEditSave}
              onEditCancel={() => setEditingMessageId(null)}
              onDeleteStart={setConfirmDeleteId}
              onLabelClick={(memberId, currentLabel) => setAliasTarget({ memberId, currentLabel })}
            />
          )
        })()}
      </div>
    </>
  )
}
