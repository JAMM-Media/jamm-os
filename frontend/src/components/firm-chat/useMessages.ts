// path: frontend/src/components/firm-chat/useMessages.ts
'use client'

import { useState, useEffect, useCallback } from 'react'
import { firmChatApi } from '@/lib/api/firmChat'

export interface Message {
  id: string
  senderId: string
  senderName: string
  senderInitials: string
  body: string
  attachmentKey: string | null
  attachmentName: string | null
  attachmentSize: number | null
  mentions: string[]
  createdAt: string
}

interface UseMessagesReturn {
  messages: Message[]
  isLoading: boolean
  sendMessage: (body: string, mentions: string[]) => void
  markChannelRead: (channelId: string) => void
}

export function useMessages(channelId: string): UseMessagesReturn {
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    if (!channelId) return
    setIsLoading(true)
    firmChatApi
      .listMessages(channelId)
      .then((data) => setMessages(data))
      .catch(() => setMessages([]))
      .finally(() => setIsLoading(false))
  }, [channelId])

  const sendMessage = useCallback(
    (body: string, mentions: string[]) => {
      const optimistic: Message = {
        id: `temp-${Date.now()}`,
        senderId: 'current',
        senderName: 'You',
        senderInitials: 'YO',
        body,
        attachmentKey: null,
        attachmentName: null,
        attachmentSize: null,
        mentions,
        createdAt: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, optimistic])
      firmChatApi
        .postMessage(channelId, body, mentions)
        .then((msg) => {
          setMessages((prev) =>
            prev.map((m) => (m.id === optimistic.id ? msg : m))
          )
        })
        .catch(() => {
          setMessages((prev) => prev.filter((m) => m.id !== optimistic.id))
        })
    },
    [channelId]
  )

  const markChannelRead = useCallback((chId: string) => {
    firmChatApi.markChannelRead(chId).catch(() => {})
  }, [])

  return { messages, isLoading, sendMessage, markChannelRead }
}
