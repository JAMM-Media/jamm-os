// frontend/src/components/portal/usePortalNotifications.ts
'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  getPortalNotifications,
  markAllPortalNotificationsRead,
  type PortalNotification,
} from '@/lib/portal-api'

interface UsePortalNotificationsReturn {
  notifications: PortalNotification[]
  unreadCount: number
  loading: boolean
  markAllRead: () => Promise<void>
  refetch: () => Promise<void>
}

export function usePortalNotifications(): UsePortalNotificationsReturn {
  const [notifications, setNotifications] = useState<PortalNotification[]>([])
  const [loading, setLoading] = useState(false)

  const fetchNotifications = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getPortalNotifications(20)
      setNotifications(data)
    } catch {
      // leave stale data on error rather than crashing the UI
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchNotifications()
  }, [fetchNotifications])

  const markAllRead = useCallback(async () => {
    try {
      await markAllPortalNotificationsRead()
      // Refetch so is_read states update. Pinned notifications remain unread server-side.
      await fetchNotifications()
    } catch {
      // ignore - stale state is preferable to an error overlay
    }
  }, [fetchNotifications])

  // Unread count includes pinned notifications (they are always is_read=false server-side
  // until explicitly completed, so they should show in the badge count).
  const unreadCount = notifications.filter(n => !n.is_read).length

  return { notifications, unreadCount, loading, markAllRead, refetch: fetchNotifications }
}
