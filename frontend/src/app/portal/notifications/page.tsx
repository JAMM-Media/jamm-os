// frontend/src/app/portal/notifications/page.tsx
'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import {
  Bell,
  Loader2,
  MessageCircle,
  FileText,
  CheckSquare,
  CheckCircle,
  Upload,
  FolderOpen,
  Receipt,
  FileCheck,
  Pencil,
} from 'lucide-react'
import { getPortalNotifications, type PortalNotification } from '@/lib/portal-api'
import { PortalShell } from '@/components/portal/PortalShell'
import { PortalAttributionSurvey } from '@/components/portal/PortalAttributionSurvey'

// Icon badge token values from portal-design-tokens.md
const BADGE_GOLD_BG = '#FEF3C7'
const BADGE_GOLD_ICON = '#D97706'
const BADGE_BLUE_BG = '#DBEAFE'
const BADGE_BLUE_ICON = '#3B82F6'
const UNREAD_DOT = '#F97316'

const LIMIT = 20

interface PortalMe {
  client_id: string
  client_name: string
  firm_name: string
  portal_display_name: string
  portal_logo_url: string | null
  portal_mode: 'light' | 'dark'
  portal_top_bar_color: string
  portal_page_color: string
  portal_tab_bar_color: string
  portal_accent_color: string
  portal_avatar_color: string
  portal_subtitle_color: string
  portal_card_color: string
  portal_text_primary: string
  portal_text_muted: string
}

function formatTimestamp(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const notifDay = new Date(date.getFullYear(), date.getMonth(), date.getDate())

  if (notifDay.getTime() === todayStart.getTime()) {
    return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
  }
  const yesterday = new Date(todayStart)
  yesterday.setDate(yesterday.getDate() - 1)
  if (notifDay.getTime() === yesterday.getTime()) return 'Yesterday'
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

type LucideIcon = React.ComponentType<{ size?: number; color?: string }>

function resolveIcon(
  type: string,
  isPinned: boolean,
): { Icon: LucideIcon; variant: 'gold' | 'blue' } {
  if (isPinned) return { Icon: Bell, variant: 'gold' }
  switch (type) {
    case 'message':
    case 'new_message':
      return { Icon: MessageCircle, variant: 'gold' }
    case 'document_request':
    case 'document_request_created':
      return { Icon: FileText, variant: 'gold' }
    case 'todo':
    case 'todo_assigned':
    case 'to_do':
      return { Icon: CheckSquare, variant: 'gold' }
    case 'payment_due':
    case 'invoice_overdue':
      return { Icon: Receipt, variant: 'gold' }
    case 'signature_needed':
      return { Icon: Pencil, variant: 'gold' }
    case 'invoice_paid':
    case 'payment_received':
      return { Icon: CheckCircle, variant: 'blue' }
    case 'invoice_sent':
      return { Icon: Receipt, variant: 'blue' }
    case 'document_uploaded':
    case 'document_ready':
      return { Icon: Upload, variant: 'blue' }
    case 'organizer_ready':
    case 'tax_organizer':
    case 'organizer_available':
      return { Icon: FolderOpen, variant: 'blue' }
    case 'engagement_update':
    case 'engagement_completed':
      return { Icon: FileCheck, variant: 'blue' }
    default:
      return { Icon: Bell, variant: 'blue' }
  }
}

// Returns the portal tab destination for a notification type, or null for
// types with no real destination (system, unknown).
function notifDestination(type: string): string | null {
  switch (type) {
    case 'message':
    case 'new_message':
      return '/portal?tab=messages'
    case 'document_request':
    case 'document_request_created':
    case 'signature_needed':
    case 'document_uploaded':
    case 'document_ready':
      return '/portal?tab=documents'
    case 'payment_due':
    case 'invoice_overdue':
    case 'invoice_paid':
    case 'invoice_sent':
      return '/portal?tab=billing-detail'
    case 'engagement_update':
    case 'engagement_completed':
    case 'todo':
    case 'todo_assigned':
    case 'to_do':
      return '/portal?tab=todo'
    case 'organizer_ready':
    case 'tax_organizer':
    case 'organizer_available':
      return '/portal?tab=organizer'
    default:
      return null
  }
}

function NotificationRow({
  notification,
  isLast,
  onSurveyOpen,
  onNavigate,
}: {
  notification: PortalNotification
  isLast: boolean
  onSurveyOpen: () => void
  onNavigate: (id: string, type: string) => void
}) {
  const { Icon, variant } = resolveIcon(notification.notification_type, notification.is_pinned)
  const isUnread = !notification.is_read
  const badgeBg = variant === 'gold' ? BADGE_GOLD_BG : BADGE_BLUE_BG
  const iconColor = variant === 'gold' ? BADGE_GOLD_ICON : BADGE_BLUE_ICON
  const borderClass = !isLast ? ' border-b border-gray-100' : ''
  const dest = notifDestination(notification.notification_type)
  const isNavigable = !notification.is_pinned && dest !== null

  const inner = (
    <>
      <div
        className="w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0"
        style={{ backgroundColor: badgeBg }}
      >
        <Icon size={16} color={iconColor} />
      </div>
      <div className="flex-1 min-w-0">
        <p
          className="text-[13px] font-medium leading-snug"
          style={{ color: isUnread ? '#1F3148' : '#6B7280' }}
        >
          {notification.title}
        </p>
        {notification.body && (
          <p className="text-[12px] mt-0.5 leading-snug" style={{ color: '#6B7280' }}>
            {notification.body}
          </p>
        )}
      </div>
      <div className="flex flex-col items-end gap-1.5 flex-shrink-0 ml-2">
        <span className="text-[11px] whitespace-nowrap" style={{ color: '#9CA3AF' }}>
          {formatTimestamp(notification.created_at)}
        </span>
        {isUnread && (
          <div className="w-2 h-2 rounded-full" style={{ backgroundColor: UNREAD_DOT }} />
        )}
      </div>
    </>
  )

  if (notification.is_pinned) {
    return (
      <button
        type="button"
        onClick={onSurveyOpen}
        className={`flex items-start gap-3 px-4 py-4${borderClass} w-full text-left transition-colors hover:bg-gray-50`}
      >
        {inner}
      </button>
    )
  }

  if (isNavigable) {
    return (
      <button
        type="button"
        onClick={() => onNavigate(notification.id, notification.notification_type)}
        className={`flex items-start gap-3 px-4 py-4${borderClass} w-full text-left transition-colors hover:bg-gray-50`}
      >
        {inner}
      </button>
    )
  }

  return (
    <div className={`flex items-start gap-3 px-4 py-4${borderClass}`}>
      {inner}
    </div>
  )
}

export default function PortalNotificationsPage() {
  const router = useRouter()
  const [me, setMe] = useState<PortalMe | null>(null)
  const [notifications, setNotifications] = useState<PortalNotification[]>([])
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [hasMore, setHasMore] = useState(false)
  const [skip, setSkip] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [surveyOpen, setSurveyOpen] = useState(false)

  useEffect(() => {
    const token = localStorage.getItem('portal_access_token')
    fetch('/api/backend/portal/me', {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then(async res => {
        if (res.status === 401 || res.status === 403) {
          router.replace('/portal/login')
          return
        }
        if (!res.ok) return
        setMe(await res.json())
      })
      .catch(() => router.replace('/portal/login'))
  }, [router])

  useEffect(() => {
    getPortalNotifications(LIMIT, 0)
      .then(data => {
        setNotifications(data)
        setHasMore(data.length === LIMIT)
        setSkip(LIMIT)
      })
      .catch(() => setError('Could not load notifications. Please try again.'))
      .finally(() => setLoading(false))
  }, [])

  const handleLoadMore = async () => {
    setLoadingMore(true)
    try {
      const more = await getPortalNotifications(LIMIT, skip)
      setNotifications(prev => [...prev, ...more])
      setHasMore(more.length === LIMIT)
      setSkip(prev => prev + LIMIT)
    } finally {
      setLoadingMore(false)
    }
  }

  const handleSurveyComplete = async () => {
    setSurveyOpen(false)
    try {
      const fresh = await getPortalNotifications(LIMIT, 0)
      setNotifications(fresh)
      setSkip(LIMIT)
      setHasMore(fresh.length === LIMIT)
    } catch {
      // leave stale list
    }
  }

  const handleNavigate = (id: string, type: string) => {
    const token = localStorage.getItem('portal_access_token')
    const headers: Record<string, string> = {}
    if (token) headers['Authorization'] = `Bearer ${token}`
    // Fire-and-forget mark-as-read; navigate immediately for responsive UX
    fetch(`/api/backend/portal/notifications/${id}/read`, { method: 'PATCH', headers }).catch(() => {})
    setNotifications(prev => prev.map(n => n.id === id ? { ...n, is_read: true } : n))
    const dest = notifDestination(type)
    if (dest) router.push(dest)
  }

  if (!me) {
    return (
      <div className="min-h-screen flex flex-col bg-gray-50">
        <div className="h-12 flex-shrink-0 animate-pulse bg-gray-200" />
        <div className="h-10 flex-shrink-0 animate-pulse bg-gray-100" />
        <div className="flex-1" />
      </div>
    )
  }

  const logoImgSrc = me.portal_logo_url
    ? `https://api.jammpx.com${me.portal_logo_url}`
    : undefined
  const isEmpty = !loading && notifications.length === 0

  return (
    <>
      <PortalShell
        firmName={me.portal_display_name || me.firm_name}
        logoUrl={logoImgSrc}
        brandColor={me.portal_top_bar_color}
        pageColor={me.portal_page_color}
        tabBarColor={me.portal_tab_bar_color}
        accentColor={me.portal_accent_color}
        avatarColor={me.portal_avatar_color}
        subtitleColor={me.portal_subtitle_color}
        portalMode={me.portal_mode}
        clientName={me.client_name}
        activeTab=""
        onTabChange={tab => router.push(`/portal?tab=${tab}`)}
      >
        <div className="w-full px-4 py-6">
          {/* Page header */}
          <div className="mb-5">
            <h1 className="text-[20px] font-bold" style={{ color: '#1F3148' }}>
              Notifications
            </h1>
            <p className="text-[13px] mt-1" style={{ color: '#6B7280' }}>
              Stay up to date on important activity and updates.
            </p>
          </div>

          {/* Loading skeleton */}
          {loading && (
            <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
              {[0, 1, 2].map(i => (
                <div
                  key={i}
                  className={`flex items-start gap-3 px-4 py-4${i < 2 ? ' border-b border-gray-100' : ''}`}
                >
                  <div className="w-9 h-9 rounded-full bg-gray-100 animate-pulse flex-shrink-0" />
                  <div className="flex-1 space-y-2 py-1">
                    <div className="h-3 bg-gray-100 animate-pulse rounded w-3/4" />
                    <div className="h-3 bg-gray-100 animate-pulse rounded w-1/2" />
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Error state */}
          {!loading && error && (
            <div className="flex flex-col items-center py-10 gap-3">
              <p className="text-[13px] text-center" style={{ color: '#9CA3AF' }}>{error}</p>
              <button
                type="button"
                onClick={() => {
                  setError(null)
                  setLoading(true)
                  getPortalNotifications(LIMIT, 0)
                    .then(data => {
                      setNotifications(data)
                      setHasMore(data.length === LIMIT)
                      setSkip(LIMIT)
                    })
                    .catch(() => setError('Could not load notifications. Please try again.'))
                    .finally(() => setLoading(false))
                }}
                className="text-[12px] transition-opacity hover:opacity-70"
                style={{ color: '#3B82F6' }}
              >
                Try again
              </button>
            </div>
          )}

          {/* Empty state */}
          {isEmpty && (
            <div className="bg-white rounded-xl border border-gray-100 flex flex-col items-center py-14 gap-3">
              <Bell size={28} style={{ color: '#D1D5DB' }} />
              <p className="text-[13px]" style={{ color: '#9CA3AF' }}>No notifications yet.</p>
            </div>
          )}

          {/* Notification list */}
          {!loading && notifications.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
              {notifications.map((n, i) => (
                <NotificationRow
                  key={n.id}
                  notification={n}
                  isLast={i === notifications.length - 1}
                  onSurveyOpen={() => setSurveyOpen(true)}
                  onNavigate={handleNavigate}
                />
              ))}
            </div>
          )}

          {/* Load more */}
          {hasMore && !loading && (
            <button
              type="button"
              onClick={handleLoadMore}
              disabled={loadingMore}
              className="w-full mt-3 py-3 rounded-xl text-[12px] font-medium transition-opacity disabled:opacity-60 flex items-center justify-center gap-2 bg-white border border-gray-100"
              style={{ color: '#6B7280' }}
            >
              {loadingMore && <Loader2 size={12} className="animate-spin" />}
              {loadingMore ? 'Loading...' : 'Load more'}
            </button>
          )}
        </div>
      </PortalShell>

      {surveyOpen && (
        <PortalAttributionSurvey
          onClose={() => setSurveyOpen(false)}
          onComplete={handleSurveyComplete}
        />
      )}
    </>
  )
}
