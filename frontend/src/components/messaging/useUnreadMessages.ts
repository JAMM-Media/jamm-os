// frontend/src/components/messaging/useUnreadMessages.ts
'use client'

import { useState, useEffect, useCallback } from 'react'
import api from '@/lib/api'

interface UseUnreadMessagesReturn {
  unreadCount: number
  markAsRead: () => void
}

export function useUnreadMessages(clientId: string): UseUnreadMessagesReturn {
  const [unreadCount, setUnreadCount] = useState(0)

  useEffect(() => {
    if (!clientId) return
    api
      .get<{ count: number }>(`/clients/${clientId}/messages/unread-count`)
      .then((res) => setUnreadCount(res.data.count))
      .catch(() => setUnreadCount(0))
  }, [clientId])

  const markAsRead = useCallback(() => {
    setUnreadCount(0)
    api.post('/messages/mark-read', { client_id: clientId }).catch(() => {})
  }, [clientId])

  return { unreadCount, markAsRead }
}
