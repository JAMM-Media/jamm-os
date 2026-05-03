// path: frontend/src/components/firm-chat/useChannels.ts
'use client'

import { useState, useEffect, useCallback } from 'react'
import { firmChatApi } from '@/lib/api/firmChat'

export interface Channel {
  id: string
  name: string
  unreadCount: number
}

interface UseChannelsReturn {
  channels: Channel[]
  totalUnread: number
  isLoading: boolean
  createChannel: (name: string) => void
  deleteChannel: (channelId: string) => void
  renameChannel: (channelId: string, name: string) => void
  markChannelRead: (channelId: string) => void
}

export function useChannels(): UseChannelsReturn {
  const [channels, setChannels] = useState<Channel[]>([])
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    if (typeof window !== 'undefined' && !localStorage.getItem('access_token')) return
    setIsLoading(true)
    firmChatApi
      .listChannels()
      .then((data) => setChannels(data))
      .catch(() => setChannels([]))
      .finally(() => setIsLoading(false))
  }, [])

  const totalUnread = channels.reduce((sum, ch) => sum + (ch.unreadCount ?? 0), 0)

  const createChannel = useCallback((name: string) => {
    firmChatApi
      .createChannel(name)
      .then((ch) => setChannels((prev) => [...prev, ch]))
      .catch(() => {})
  }, [])

  const deleteChannel = useCallback((channelId: string) => {
    setChannels((prev) => prev.filter((ch) => ch.id !== channelId))
    firmChatApi.deleteChannel(channelId).catch(() => {})
  }, [])

  const renameChannel = useCallback((channelId: string, name: string) => {
    setChannels((prev) =>
      prev.map((ch) => (ch.id === channelId ? { ...ch, name } : ch))
    )
    firmChatApi.renameChannel(channelId, name).catch(() => {})
  }, [])

  const markChannelRead = useCallback((channelId: string) => {
    setChannels((prev) =>
      prev.map((ch) => (ch.id === channelId ? { ...ch, unreadCount: 0 } : ch))
    )
    firmChatApi.markChannelRead(channelId).catch(() => {})
  }, [])

  return {
    channels,
    totalUnread,
    isLoading,
    createChannel,
    deleteChannel,
    renameChannel,
    markChannelRead,
  }
}
