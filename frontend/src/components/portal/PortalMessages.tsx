// frontend/src/components/portal/PortalMessages.tsx
'use client'

import { useState, useEffect } from 'react'

interface RawMessage {
  id: string
  sender_role: string
  sender_name: string | null
  body: string
  created_at: string
}

interface PortalMessagesProps {
  clientId: string
  firmName: string
}

function formatTimestamp(isoString: string): string {
  const date = new Date(isoString)
  return (
    date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) +
    ' · ' +
    date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
  )
}

export function PortalMessages({ clientId, firmName }: PortalMessagesProps) {
  const [messages, setMessages] = useState<RawMessage[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('portal_access_token')
    fetch(`/api/backend/portal/clients/${clientId}/messages`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => setMessages(Array.isArray(data) ? data : []))
      .catch(() => setMessages([]))
      .finally(() => setLoading(false))
  }, [clientId])

  if (loading) {
    return (
      <div className="p-5 flex flex-col gap-3 max-w-2xl mx-auto">
        {[1, 2].map((i) => (
          <div key={i} className="h-16 rounded-[6px] bg-[#383838] animate-pulse" />
        ))}
      </div>
    )
  }

  if (messages.length === 0) {
    return (
      <div className="flex items-center justify-center py-24">
        <p className="text-[12px] text-[#9CA3AF]">No messages yet.</p>
      </div>
    )
  }

  return (
    <div className="p-5 space-y-3">
      {messages.map((msg) => (
        <div
          key={msg.id}
          className="rounded-[6px] p-[10px_12px] bg-[#EDEEF0] dark:bg-[#383838]"
        >
          <div className="flex items-center justify-between mb-1">
            <span className="text-[12px] font-medium text-brand dark:text-[#EDEEF0]">
              {msg.sender_role === 'client' ? 'You' : firmName}
            </span>
            <span className="text-[11px] text-[#9CA3AF]">{formatTimestamp(msg.created_at)}</span>
          </div>
          <p className="text-[13px] text-[#374151] dark:text-[#9CA3AF] leading-[1.6]">{msg.body}</p>
        </div>
      ))}
    </div>
  )
}
