// frontend/src/components/portal/usePortalUnreadMessages.ts
'use client'

import { useState, useEffect, useCallback } from 'react'
import { getPortalUnreadCount } from '@/lib/portal-api'

function getPortalClientId(): string | null {
  if (typeof window === 'undefined') return null
  const token = localStorage.getItem('portal_access_token')
  if (!token) return null
  try {
    const parts = token.split('.')
    if (parts.length < 2) return null
    const payload = JSON.parse(atob(parts[1].replace(/-/g, '+').replace(/_/g, '/')))
    return payload.sub ?? null
  } catch {
    return null
  }
}

interface UsePortalUnreadMessagesReturn {
  unreadCount: number
  markAsRead: () => void
}

export function usePortalUnreadMessages(): UsePortalUnreadMessagesReturn {
  const [unreadCount, setUnreadCount] = useState(0)

  useEffect(() => {
    const clientId = getPortalClientId()
    if (!clientId) return
    getPortalUnreadCount(clientId)
      .then(setUnreadCount)
      .catch(() => setUnreadCount(0))
  }, [])

  const markAsRead = useCallback(() => {
    setUnreadCount(0)
  }, [])

  return { unreadCount, markAsRead }
}
