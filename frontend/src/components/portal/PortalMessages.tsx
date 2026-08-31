// frontend/src/components/portal/PortalMessages.tsx
'use client'

import { useState, useEffect, useRef } from 'react'
import { Loader2, Send, Paperclip } from 'lucide-react'
import { toast } from 'sonner'
import { getPortalMessages, sendPortalMessage } from '@/lib/portal-api'
import type { PortalMessage } from '@/lib/portal-api'

interface MessageWithOptimistic extends PortalMessage {
  optimistic?: boolean
}

type MessageGroup = {
  role: string
  senderName: string | null
  messages: MessageWithOptimistic[]
}

interface PortalMessagesProps {
  clientId: string
  firmName: string
  cardColor?: string
  accentColor?: string
  portalMode?: 'light' | 'dark'
  textPrimary?: string
  textMuted?: string
}

function getInitials(name: string): string {
  return name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0])
    .join('')
    .toUpperCase()
}

function formatTimestamp(iso: string): string {
  const d = new Date(iso)
  return (
    d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) +
    ' · ' +
    d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
  )
}

export function PortalMessages({
  clientId,
  firmName,
  accentColor = '#3A6A94',
}: PortalMessagesProps) {
  const [messages, setMessages] = useState<MessageWithOptimistic[]>([])
  const [loading, setLoading] = useState(true)
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    getPortalMessages(clientId)
      .then(setMessages)
      .catch(() => setMessages([]))
      .finally(() => setLoading(false))
  }, [clientId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // PLACEHOLDER FLAG: "Typically replies within one business day" copy below is
  // UNCONFIRMED -- it makes a response-time commitment no firm has agreed to.
  // Remove this warn and the data attribute only after a deliberate copy decision.
  useEffect(() => {
    console.warn(
      '[PortalMessages] PLACEHOLDER: "Typically replies within one business day" ' +
      'is unconfirmed copy pending a real SLA decision. ' +
      'Do not treat this as a permanent commitment.'
    )
  }, [])

  async function handleSend() {
    const body = draft.trim()
    if (!body || sending) return
    setDraft('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
    setSending(true)

    const optimisticId = `opt-${Date.now()}`
    const optimistic: MessageWithOptimistic = {
      id: optimisticId,
      body,
      sender_role: 'client',
      sender_name: null,
      created_at: new Date().toISOString(),
      optimistic: true,
    }
    setMessages((prev) => [...prev, optimistic])

    try {
      const real = await sendPortalMessage(clientId, body)
      setMessages((prev) => prev.map((m) => (m.id === optimisticId ? real : m)))
    } catch {
      setMessages((prev) => prev.filter((m) => m.id !== optimisticId))
      toast.error('Failed to send message. Please try again.')
    } finally {
      setSending(false)
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  function handleDraftChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setDraft(e.target.value)
    const el = e.target
    el.style.height = 'auto'
    el.style.height = `${el.scrollHeight}px`
  }

  // Group consecutive same-sender messages
  const groups: MessageGroup[] = []
  for (const msg of messages) {
    const last = groups[groups.length - 1]
    if (last && last.role === msg.sender_role) {
      last.messages.push(msg)
    } else {
      groups.push({ role: msg.sender_role, senderName: msg.sender_name, messages: [msg] })
    }
  }

  return (
    <div className="flex flex-col min-h-full">

      {/* Page header */}
      <div className="px-5 pt-5 pb-4">
        <h1 className="text-[20px] font-bold" style={{ color: '#1F3148' }}>Messages</h1>
        <p className="text-[13px] mt-0.5" style={{ color: '#6B7280' }}>
          Communicate securely with your accounting team.
        </p>
      </div>

      {/* Conversation card */}
      <div className="mx-5 mb-5 flex flex-col flex-1 bg-white rounded-xl border border-gray-100 overflow-hidden">

        {/* Conversation header: firm name + reply-time placeholder */}
        <div className="px-5 py-4 border-b border-gray-100">
          <div className="text-[14px] font-semibold" style={{ color: '#1F3148' }}>{firmName}</div>
          {/* PLACEHOLDER -- "Typically replies within one business day" is UNCONFIRMED copy.
              An SLA commitment must be reviewed before this ships as permanent. */}
          <div
            className="text-[12px] mt-0.5"
            style={{ color: '#9CA3AF' }}
            data-placeholder-unconfirmed="reply-time"
          >
            Typically replies within one business day
          </div>
        </div>

        {/* Message thread */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
          {loading ? (
            <div className="flex flex-col gap-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className={`flex flex-col gap-1.5 ${i % 2 === 0 ? 'items-end' : 'items-start'}`}>
                  {i % 2 !== 0 && (
                    <div className="flex items-center gap-2">
                      <div className="w-7 h-7 rounded-full bg-gray-100 animate-pulse" />
                      <div className="h-2.5 w-28 bg-gray-100 rounded animate-pulse" />
                    </div>
                  )}
                  <div className={`rounded-[12px] px-3.5 py-2.5 animate-pulse ${i % 2 === 0 ? 'bg-gray-200 w-40' : 'bg-gray-100 w-56'}`} style={{ height: 40 }} />
                  <div className="h-2 w-20 bg-gray-100 rounded animate-pulse" />
                </div>
              ))}
            </div>
          ) : messages.length === 0 ? (
            <div className="flex items-center justify-center py-16">
              <p className="text-[13px]" style={{ color: '#9CA3AF' }}>
                No messages yet. Send a message to get started.
              </p>
            </div>
          ) : (
            groups.map((group, gi) => {
              const isClient = group.role === 'client'
              return (
                <div key={gi} className={`flex flex-col ${isClient ? 'items-end' : 'items-start'}`}>

                  {/* Staff sender label (once per group) */}
                  {!isClient && (
                    <div className="flex items-center gap-2 mb-1.5">
                      <div
                        className="w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-bold text-white flex-shrink-0"
                        style={{ backgroundColor: '#1F3148' }}
                      >
                        {getInitials(group.senderName ?? firmName)}
                      </div>
                      <span className="text-[11px]" style={{ color: '#9CA3AF' }}>
                        {group.senderName ?? firmName} &middot; {formatTimestamp(group.messages[0].created_at)}
                      </span>
                    </div>
                  )}

                  {/* Bubbles */}
                  <div className={`flex flex-col gap-1 max-w-[75%] ${isClient ? 'items-end' : 'items-start'}`}>
                    {group.messages.map((msg) => (
                      <div
                        key={msg.id}
                        className={`rounded-[12px] px-3.5 py-2.5 ${msg.optimistic ? 'opacity-60' : ''} ${isClient ? '' : 'bg-white border border-gray-100'}`}
                        style={isClient ? { backgroundColor: accentColor } : {}}
                      >
                        <p
                          className="text-[13px] leading-relaxed whitespace-pre-wrap"
                          style={{ color: isClient ? '#FFFFFF' : '#1F3148' }}
                        >
                          {msg.body}
                        </p>
                      </div>
                    ))}
                  </div>

                  {/* Timestamp after last bubble */}
                  <span className="text-[10px] mt-1" style={{ color: '#9CA3AF' }}>
                    {isClient
                      ? formatTimestamp(group.messages[group.messages.length - 1].created_at)
                      : ''}
                  </span>
                </div>
              )
            })
          )}
          <div ref={bottomRef} />
        </div>

        {/* Compose box */}
        <div className="border-t border-gray-100 px-4 py-3">
          <div className="flex items-end gap-2 bg-white rounded-xl border border-gray-200 px-3 py-2">
            {/* Attachment icon -- visual placeholder, no upload functionality yet */}
            <Paperclip
              size={16}
              className="flex-shrink-0 mb-1"
              style={{ color: '#9CA3AF' }}
              aria-label="Attach file (coming soon)"
            />
            <textarea
              ref={textareaRef}
              value={draft}
              onChange={handleDraftChange}
              onKeyDown={handleKeyDown}
              placeholder="Type your message..."
              rows={1}
              className="flex-1 resize-none focus:outline-none text-[13px] bg-transparent leading-relaxed overflow-hidden"
              style={{ color: '#1F3148', minHeight: '1.5rem', maxHeight: '7rem' }}
            />
            <button
              onClick={handleSend}
              disabled={!draft.trim() || sending}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-[13px] font-medium text-white flex-shrink-0 disabled:opacity-40 hover:opacity-90 transition-opacity"
              style={{ backgroundColor: accentColor }}
            >
              {sending ? (
                <Loader2 size={13} className="animate-spin" />
              ) : (
                <Send size={13} />
              )}
              Send message
            </button>
          </div>
        </div>

      </div>
    </div>
  )
}