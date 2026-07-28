// frontend/src/lib/hooks/useConciergeNotifications.ts
'use client'

import { useState, useEffect, useCallback } from 'react'
import api from '@/lib/api'

export interface ConciergeNotification {
  id: string
  trigger_type: string
  message: string
  created_at: string
  metadata?: Record<string, unknown> | null
}

// ---------------------------------------------------------------------------
// Module-level shared state and subscriber system.
// Follows the same standalone-hook pattern as useConciergeContext: no React
// Context provider, module-level data shared across all callers, with each
// caller subscribing to receive re-renders when the shared state changes.
// ---------------------------------------------------------------------------

let _notifications: ConciergeNotification[] = []
const _subscribers = new Set<() => void>()
let _fetching = false
let _lastFetch = 0
let _pollingInterval: ReturnType<typeof setInterval> | null = null
let _refCount = 0

function _notifySubscribers() {
  _subscribers.forEach((fn) => fn())
}

function _setNotifications(next: ConciergeNotification[]) {
  _notifications = next
  _notifySubscribers()
}

async function _fetch() {
  if (_fetching) return
  _fetching = true
  try {
    const res = await api.get('/concierge/notifications')
    const incoming = (res.data.items ?? []) as ConciergeNotification[]
    // Merge: append only notifications not already present (matches panel's prior behavior)
    const existing = new Set(_notifications.map((n) => n.id))
    const fresh = incoming.filter((n) => !existing.has(n.id))
    if (fresh.length > 0) {
      _setNotifications([..._notifications, ...fresh])
    }
    _lastFetch = Date.now()
  } catch {
    // non-fatal
  } finally {
    _fetching = false
  }
}

function _startPolling() {
  if (_pollingInterval) return
  _pollingInterval = setInterval(async () => {
    try {
      await api.post('/concierge/trigger-check')
    } catch {
      // non-fatal
    }
    _fetch()
  }, 60_000)
}

function _stopPolling() {
  if (_pollingInterval) {
    clearInterval(_pollingInterval)
    _pollingInterval = null
  }
}

// ---------------------------------------------------------------------------
// Public hook
// ---------------------------------------------------------------------------

export function useConciergeNotifications() {
  const [, forceUpdate] = useState(0)

  useEffect(() => {
    const notify = () => forceUpdate((n) => n + 1)
    _subscribers.add(notify)
    _refCount++

    _startPolling()

    // Fetch immediately on first mount if we have no data yet
    if (_lastFetch === 0) {
      _fetch()
    }

    return () => {
      _subscribers.delete(notify)
      _refCount--
      if (_refCount === 0) {
        _stopPolling()
      }
    }
  }, [])

  const dismissNotification = useCallback(async (id: string) => {
    _setNotifications(_notifications.filter((n) => n.id !== id))
    try {
      await api.patch(`/concierge/notifications/${id}/read`)
    } catch {
      // already removed from UI
    }
  }, [])

  const refetch = useCallback(() => {
    _fetch()
  }, [])

  return {
    notifications: _notifications,
    dismissNotification,
    refetch,
  }
}
