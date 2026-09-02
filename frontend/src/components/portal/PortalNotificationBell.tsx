// frontend/src/components/portal/PortalNotificationBell.tsx
'use client'

import { useRouter } from 'next/navigation'
import { Bell } from 'lucide-react'
import { usePortalNotifications } from './usePortalNotifications'

// JAMM brand gold -- used for the unread-count badge on the bell icon.
const JAMM_GOLD = '#B07D3A'

export function PortalNotificationBell() {
  const router = useRouter()
  const { unreadCount } = usePortalNotifications()

  return (
    <button
      type="button"
      onClick={() => router.push('/portal/notifications')}
      className="relative flex items-center justify-center w-8 h-8 rounded-full transition-colors hover:bg-gray-100"
      aria-label="Notifications"
    >
      <Bell size={16} style={{ color: '#374151' }} />
      {unreadCount > 0 && (
        <span
          className="absolute -top-0.5 -right-0.5 min-w-[14px] h-[14px] rounded-full flex items-center justify-center text-[8px] font-bold px-[3px]"
          style={{ backgroundColor: JAMM_GOLD, color: '#ffffff' }}
        >
          {unreadCount > 99 ? '99+' : unreadCount}
        </span>
      )}
    </button>
  )
}
