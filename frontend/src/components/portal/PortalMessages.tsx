// frontend/src/components/portal/PortalMessages.tsx
'use client'

import { useState, useEffect, useRef } from 'react'
import { Loader2, Send } from 'lucide-react'
import { toast } from 'sonner'
import { getPortalMessages, sendPortalMessage } from '@/lib/portal-api'
import type { PortalMessage } from '@/lib/portal-api'

interface MessageWithOptimistic extends PortalMessage {
  optimistic?: boolean
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

function formatTimestamp(iso: string): string {
  const d = new Date(iso)
  return (
    d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) +
    ' · ' +
    d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
  )
}

export function PortalMessages({ clientId, firmName, cardColor = '#383838', accentColor = '#3A6A94', portalMode = 'dark', textPrimary = '#EDEEF0', textMuted = '#9CA3AF' }: PortalMessagesProps) {
  const primaryText = textPrimary
  const mutedText = textMuted
  const borderColor = portalMode === 'light' ? '#C8CDD6' : '#383838'
  const inputBorder = portalMode === 'light' ? '#C8CDD6' : '#484848'
  const inputFocusBorder = portalMode === 'light' ? '#1F3148' : '#3A6A94'

  const [messages, setMessages] = useState<MessageWithOptimistic[]>([])
  const [loading, setLoading] = useState(true)
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    getPortalMessages(clientId)
      .then(setMessages)
      .catch(() => setMessages([]))
      .finally(() => setLoading(false))
  }, [clientId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function handleSend() {
    const body = draft.trim()
    if (!body || sending) return
    setDraft('')
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

  if (loading) {
    return (
      <div className="p-5 flex flex-col gap-3 max-w-2xl mx-auto">
        {[1, 2].map((i) => (
          <div key={i} className="h-16 rounded-[6px] animate-pulse" style={{ backgroundColor: cardColor }} />
        ))}
      </div>
    )
  }

  return (
    <div className="flex flex-col">
      <div className="p-5 space-y-4 max-w-2xl mx-auto w-full">
        {messages.length === 0 ? (
          <div className="flex items-center justify-center py-24">
            <p className="text-[12px]" style={{ color: mutedText }}>No messages yet.</p>
          </div>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex flex-col gap-1 ${
                msg.sender_role === 'client' ? 'items-end' : 'items-start'
              }`}
            >
              {msg.sender_role !== 'client' && (
                <span className="text-[11px] px-1" style={{ color: mutedText }}>
                  {msg.sender_name ?? firmName}
                </span>
              )}
              <div
                className={`rounded-[8px] px-3 py-2 max-w-[75%] ${msg.optimistic ? 'opacity-60' : ''}`}
                style={{ backgroundColor: msg.sender_role === 'client' ? accentColor : cardColor }}
              >
                <p className="text-[13px] leading-relaxed" style={{ color: primaryText }}>{msg.body}</p>
              </div>
              <span className="text-[10px] px-1" style={{ color: mutedText }}>
                {formatTimestamp(msg.created_at)}
              </span>
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>

      <div className="border-t p-4 max-w-2xl mx-auto w-full" style={{ borderColor }}>
        <div className="flex items-end gap-2">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Message your accountant..."
            rows={2}
            className="flex-1 rounded-[6px] px-3 py-2 text-[13px] resize-none focus:outline-none"
            style={{
              backgroundColor: cardColor,
              border: `1px solid ${inputBorder}`,
              color: primaryText,
              outlineColor: inputFocusBorder,
            }}
          />
          <button
            onClick={handleSend}
            disabled={!draft.trim() || sending}
            className="h-9 w-9 rounded-[6px] flex items-center justify-center disabled:opacity-40 hover:opacity-90 transition-opacity flex-shrink-0"
            style={{ backgroundColor: accentColor, color: '#FFFFFF' }}
          >
            {sending ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Send className="w-3.5 h-3.5" />
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
