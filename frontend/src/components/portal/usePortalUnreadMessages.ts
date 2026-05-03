// frontend/src/components/portal/usePortalUnreadMessages.ts
'use client'

import { useState, useEffect, useCallback } from 'react'
import api from '@/lib/api'

interface UsePortalUnreadMessagesReturn {
  unreadCount: number
  markAsRead: () => void
}

export function usePortalUnreadMessages(): UsePortalUnreadMessagesReturn {
  const [unreadCount, setUnreadCount] = useState(0)

  useEffect(() => {
    api
      .get<{ count: number }>('/portal/messages/unread-count')
      .then((res) => setUnreadCount(res.data.count))
      .catch(() => setUnreadCount(0))
  }, [])

  const markAsRead = useCallback(() => {
    setUnreadCount(0)
    api.post('/portal/messages/mark-read').catch(() => {})
  }, [])

  return { unreadCount, markAsRead }
}
