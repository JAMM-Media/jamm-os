// frontend/src/components/portal/PortalNotificationBell.tsx
'use client'

import { useState, useRef, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Bell, X, Pin } from 'lucide-react'
import { usePortalNotifications } from './usePortalNotifications'
import { PortalAttributionSurvey } from './PortalAttributionSurvey'
import type { PortalNotification } from '@/lib/portal-api'

// JAMM brand gold -- used for pinned/action-required treatment only.
// This is not firm-themed and does not change with portal color settings.
const JAMM_GOLD = '#B07D3A'
const POPOVER_BG = '#1A2535'
const ROW_BG = 'rgba(255, 255, 255, 0.06)'
const ROW_HOVER_BG = 'rgba(255, 255, 255, 0.10)'

function formatDateLabel(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterdayStart = new Date(todayStart)
  yesterdayStart.setDate(yesterdayStart.getDate() - 1)
  const notifDay = new Date(date.getFullYear(), date.getMonth(), date.getDate())

  if (notifDay.getTime() === todayStart.getTime()) return 'Today'
  if (notifDay.getTime() === yesterdayStart.getTime()) return 'Yesterday'
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

interface DateGroup {
  label: string
  items: PortalNotification[]
}

function buildGroups(notifications: PortalNotification[]): {
  pinned: PortalNotification[]
  groups: DateGroup[]
} {
  const pinned: PortalNotification[] = []
  const rest: PortalNotification[] = []

  for (const n of notifications) {
    if (n.is_pinned) pinned.push(n)
    else rest.push(n)
  }

  // Build date groups preserving server sort order (most recent first)
  const seen: string[] = []
  const groupMap: Record<string, PortalNotification[]> = {}
  for (const n of rest) {
    const label = formatDateLabel(n.created_at)
    if (!groupMap[label]) {
      groupMap[label] = []
      seen.push(label)
    }
    groupMap[label].push(n)
  }

  const groups: DateGroup[] = seen.map(label => ({ label, items: groupMap[label] }))
  return { pinned, groups }
}

function PinnedRow({
  notification,
  onClose,
  onOpenSurvey,
}: {
  notification: PortalNotification
  onClose: () => void
  onOpenSurvey: () => void
}) {
  const [hovered, setHovered] = useState(false)

  const handleClick = () => {
    onClose()
    onOpenSurvey()
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className="w-full text-left flex items-start gap-3 px-3 py-3 rounded-[6px] transition-colors"
      style={{
        backgroundColor: hovered ? ROW_HOVER_BG : ROW_BG,
        borderLeft: `3px solid ${JAMM_GOLD}`,
      }}
    >
      <div className="mt-0.5 flex-shrink-0">
        <Pin size={12} style={{ color: JAMM_GOLD }} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="mb-1">
          <p className="text-[12px] font-semibold text-white leading-snug mb-1">
            {notification.title}
          </p>
          <span
            className="text-[9px] font-semibold px-1.5 py-0.5 rounded-full inline-block"
            style={{ backgroundColor: JAMM_GOLD, color: '#ffffff' }}
          >
            Action needed
          </span>
        </div>
        {notification.body && (
          <p className="text-[11px] leading-snug" style={{ color: '#9CA3AF' }}>
            {notification.body}
          </p>
        )}
      </div>
    </button>
  )
}

function NormalRow({ notification }: { notification: PortalNotification }) {
  const isUnread = !notification.is_read

  return (
    <div
      className="flex items-start gap-3 px-3 py-3 rounded-[6px]"
      style={{ backgroundColor: ROW_BG }}
    >
      <div
        className="mt-1.5 w-1.5 h-1.5 rounded-full flex-shrink-0"
        style={{ backgroundColor: isUnread ? '#60A5FA' : 'transparent' }}
      />
      <div className="flex-1 min-w-0">
        <p
          className="text-[12px] font-medium mb-0.5 truncate"
          style={{ color: isUnread ? '#EDEEF0' : '#9CA3AF' }}
        >
          {notification.title}
        </p>
        {notification.body && (
          <p className="text-[11px] leading-snug" style={{ color: '#9CA3AF' }}>
            {notification.body}
          </p>
        )}
      </div>
    </div>
  )
}

export function PortalNotificationBell() {
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [surveyOpen, setSurveyOpen] = useState(false)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const popoverRef = useRef<HTMLDivElement>(null)
  const { notifications, unreadCount, loading, markAllRead, refetch } = usePortalNotifications()

  const hasUnreadNonPinned = notifications.some(n => !n.is_read && !n.is_pinned)
  const { pinned, groups } = buildGroups(notifications)
  const isEmpty = notifications.length === 0

  useEffect(() => {
    if (!open) return
    function handleMouseDown(e: MouseEvent) {
      const target = e.target as Node
      if (
        popoverRef.current &&
        !popoverRef.current.contains(target) &&
        buttonRef.current &&
        !buttonRef.current.contains(target)
      ) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleMouseDown)
    return () => document.removeEventListener('mousedown', handleMouseDown)
  }, [open])

  const handleMarkAllRead = async () => {
    await markAllRead()
    // popover stays open so user sees the updated read state
  }

  const handleOpenSurvey = () => {
    setOpen(false)
    setSurveyOpen(true)
  }

  const handleSurveyComplete = async () => {
    setSurveyOpen(false)
    await refetch()
  }

  return (
    <>
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setOpen(prev => !prev)}
        className="relative flex items-center justify-center w-8 h-8 rounded-full transition-colors hover:bg-gray-100"
        style={{ backgroundColor: open ? '#F3F4F6' : 'transparent' }}
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

      {surveyOpen && (
        <PortalAttributionSurvey
          onClose={() => setSurveyOpen(false)}
          onComplete={handleSurveyComplete}
        />
      )}

      {open && (
        // Popover uses fixed positioning so it renders correctly on all screen widths
        // without being clipped by the flex top bar container.
        <div
          ref={popoverRef}
          className="fixed z-50 rounded-xl overflow-hidden flex flex-col"
          style={{
            top: '56px',
            right: '12px',
            width: 'min(300px, calc(100vw - 24px))',
            maxHeight: '420px',
            backgroundColor: POPOVER_BG,
            boxShadow: '0 8px 32px rgba(0, 0, 0, 0.5)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
          }}
        >
          {/* Header */}
          <div
            className="flex items-center justify-between px-4 py-3 border-b flex-shrink-0"
            style={{ borderColor: 'rgba(255,255,255,0.08)' }}
          >
            <span className="text-[13px] font-semibold text-white">Notifications</span>
            <div className="flex items-center gap-3">
              {hasUnreadNonPinned && (
                <button
                  type="button"
                  onClick={handleMarkAllRead}
                  className="text-[11px] transition-opacity hover:opacity-70"
                  style={{ color: '#60A5FA' }}
                >
                  Mark all read
                </button>
              )}
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="flex items-center justify-center transition-opacity hover:opacity-70"
                style={{ color: '#9CA3AF' }}
                aria-label="Close notifications"
              >
                <X size={14} />
              </button>
            </div>
          </div>

          {/* Body */}
          <div className="flex-1 overflow-y-auto">
            {loading && (
              <div className="flex items-center justify-center py-8">
                <span className="text-[12px]" style={{ color: '#6B7280' }}>Loading...</span>
              </div>
            )}

            {!loading && isEmpty && (
              <div className="flex flex-col items-center justify-center py-10 gap-2">
                <Bell size={22} style={{ color: '#374151' }} />
                <p className="text-[12px]" style={{ color: '#6B7280' }}>No notifications</p>
              </div>
            )}

            {!loading && !isEmpty && (
              <div className="p-2 flex flex-col gap-1">
                {/* Pinned notifications always appear first regardless of creation date.
                    This prevents action-required items from getting buried in the date
                    list as time passes. */}
                {pinned.length > 0 && (
                  <>
                    <p
                      className="text-[9px] font-semibold px-1 pt-1 pb-0.5 uppercase tracking-wider"
                      style={{ color: JAMM_GOLD }}
                    >
                      Action Required
                    </p>
                    {pinned.map(n => (
                      <PinnedRow key={n.id} notification={n} onClose={() => setOpen(false)} onOpenSurvey={handleOpenSurvey} />
                    ))}
                    {groups.length > 0 && (
                      <div
                        className="my-1 border-t"
                        style={{ borderColor: 'rgba(255,255,255,0.06)' }}
                      />
                    )}
                  </>
                )}

                {/* Date-grouped regular notifications */}
                {groups.map(group => (
                  <div key={group.label}>
                    <p
                      className="text-[9px] font-medium px-1 pt-1 pb-0.5 uppercase tracking-wider"
                      style={{ color: '#6B7280' }}
                    >
                      {group.label}
                    </p>
                    <div className="flex flex-col gap-0.5">
                      {group.items.map(n => (
                        <NormalRow key={n.id} notification={n} />
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Footer - "View all" link */}
          {!isEmpty && (
            <div
              className="border-t px-4 py-2.5 flex-shrink-0"
              style={{ borderColor: 'rgba(255,255,255,0.08)' }}
            >
              <button
                type="button"
                className="text-[11px] w-full text-center transition-opacity hover:opacity-70"
                style={{ color: '#60A5FA' }}
                onClick={() => {
                  setOpen(false)
                  router.push('/portal/notifications')
                }}
              >
                View all notifications
              </button>
            </div>
          )}
        </div>
      )}
    </>
  )
}
