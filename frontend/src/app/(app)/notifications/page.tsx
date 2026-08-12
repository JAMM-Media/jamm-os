// path: frontend/src/app/notifications/page.tsx
'use client'

import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useRouter } from 'next/navigation'
import api from '@/lib/api'
import { toast } from 'sonner'

// Notification type from backend NotificationOut schema
interface Notification {
  id: string
  title: string
  body: string
  notification_type: string
  is_read: boolean
  created_at: string
  related_entity_type?: string
  related_entity_id?: string
}

// Relative timestamp helper
function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return 'Just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days === 1) return 'Yesterday'
  return `${days}d ago`
}

// Entity navigation map
function getEntityPath(type?: string, id?: string): string | null {
  if (!type || !id) return null
  const map: Record<string, string> = {
    engagement: `/engagements/${id}`,
    task: `/tasks/${id}`,
    client: `/clients/${id}`,
    message: '/firm-chat',
  }
  return map[type] ?? null
}

export default function NotificationsPage() {
  const queryClient = useQueryClient()
  const router = useRouter()
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState('all')
  const [readFilter, setReadFilter] = useState('all')

  const { data, isLoading, isError, refetch } = useQuery<{ items: Notification[] }>({
    queryKey: ['notifications'],
    queryFn: () => api.get('/api/v1/notifications/?limit=50').then((r) => r.data),
    staleTime: 30 * 1000,
  })

  const notifications = data?.items ?? []
  const unreadCount = notifications.filter((n) => !n.is_read).length

  const filtered = notifications.filter((n) => {
    if (search && !n.title.toLowerCase().includes(search.toLowerCase()) && !n.body.toLowerCase().includes(search.toLowerCase())) return false
    if (typeFilter !== 'all' && n.notification_type !== typeFilter) return false
    if (readFilter === 'unread' && n.is_read) return false
    if (readFilter === 'read' && !n.is_read) return false
    return true
  })

  async function handleMarkRead(id: string) {
    await api.patch(`/api/v1/notifications/${id}`, { is_read: true })
    queryClient.setQueryData(['notifications'], (old: { items: Notification[] } | undefined) => {
      if (!old) return old
      return { ...old, items: old.items.map((n) => n.id === id ? { ...n, is_read: true } : n) }
    })
    queryClient.invalidateQueries({ queryKey: ['notifications-unread-count'] })
  }

  async function handleMarkAllRead() {
    await api.patch('/api/v1/notifications/read-all')
    refetch()
    queryClient.invalidateQueries({ queryKey: ['notifications-unread-count'] })
    toast.success('All notifications marked as read')
  }

  async function handleRowClick(n: Notification) {
    if (!n.is_read) await handleMarkRead(n.id)
    const path = getEntityPath(n.related_entity_type, n.related_entity_id)
    if (path) router.push(path)
  }

  const NOTIFICATION_TYPE_LABELS: Record<string, string> = {
    'mention': '@ Mention',
    'task.assigned': 'Task Assigned',
    'task.completed': 'Task Completed',
    'task.overdue': 'Task Overdue',
    'engagement.deadline_approaching': 'Deadline Approaching',
    'engagement.completed': 'Engagement Completed',
    'document_request.completed': 'Documents Received',
    'document_request.reminder_sent': 'Document Reminder Sent',
    'invoice.paid': 'Invoice Paid',
    'invoice.overdue': 'Invoice Overdue',
    'invoice.reminder_sent': 'Invoice Reminder Sent',
    'irs_authorization.expiry_approaching': 'IRS Auth Expiring',
    'portal.first_login': 'Client Portal Login',
    'firm_chat.message': 'Firm Chat Message',
    'anniversary': 'Client Anniversary',
    'automation.fired': 'Automation Fired',
  }

  const uniqueTypes = Array.from(
    new Set(notifications.map((n) => n.notification_type))
  ).sort()

  return (
      <div className="p-6 max-w-3xl">
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <h1 className="text-[24px] font-medium text-brand dark:text-[#EDEEF0]">Notifications</h1>
          {unreadCount > 0 && (
            <button
              onClick={handleMarkAllRead}
              className="text-[12px] font-medium text-[#6B7280] hover:text-brand underline"
            >
              Mark all as read
            </button>
          )}
        </div>

        {/* Search */}
        <div className="relative mb-3">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search notifications..."
            className="w-full h-9 pl-8 pr-3 text-[13px] rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-input dark:bg-dark-card text-brand dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-[#4A7FA5]"
          />
          <svg className="absolute left-2.5 top-2.5 w-4 h-4 text-[#9CA3AF]" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" />
          </svg>
        </div>

        {/* Filter bar */}
        <div className="flex items-center gap-2 flex-wrap mb-4">
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="text-[12px] h-8 px-2 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-brand dark:text-[#EDEEF0] cursor-pointer"
          >
            <option value="all">All Types</option>
            {uniqueTypes.map((t) => (
              <option key={t} value={t}>
                {NOTIFICATION_TYPE_LABELS[t] ?? t}
              </option>
            ))}
          </select>

          <select
            value={readFilter}
            onChange={(e) => setReadFilter(e.target.value)}
            className="text-[12px] h-8 px-2 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-brand dark:text-[#EDEEF0] cursor-pointer"
          >
            <option value="all">All</option>
            <option value="unread">Unread</option>
            <option value="read">Read</option>
          </select>

          {(typeFilter !== 'all' || readFilter !== 'all') && (
            <button
              onClick={() => { setTypeFilter('all'); setReadFilter('all') }}
              className="text-[11px] text-[#6B7280] hover:text-brand underline"
            >
              Clear filters
            </button>
          )}
        </div>

        {/* Notification list */}
        {isLoading ? (
          <div className="space-y-1">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="flex items-start gap-3 px-4 py-3 rounded-[8px] bg-surface-card dark:bg-dark-card">
                <div className="flex-shrink-0 mt-1.5">
                  <div className="w-2 h-2 rounded-full bg-[#D5D8DE] dark:bg-[#444444] animate-pulse" />
                </div>
                <div className="flex-1 min-w-0 flex flex-col gap-1.5">
                  <div className="h-3 w-[60%] bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                  <div className="h-2.5 w-[80%] bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                </div>
                <div className="h-2.5 w-12 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded flex-shrink-0 mt-0.5" />
              </div>
            ))}
          </div>
        ) : isError ? (
          <div className="text-center py-12">
            <p className="text-[13px] text-[#6B7280] mb-3">Failed to load notifications.</p>
            <button onClick={() => refetch()} className="text-[12px] font-medium px-4 py-2 rounded-[6px] bg-brand text-white">Retry</button>
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 gap-2.5">
            <div className="w-10 h-10 rounded-[8px] border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card flex items-center justify-center">
              <svg width="18" height="18" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24" className="text-[#6B7280]">
                <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 0 0 5.454-1.31A8.967 8.967 0 0 1 18 9.75V9A6 6 0 0 0 6 9v.75a8.967 8.967 0 0 1-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 0 1-5.714 0m5.714 0a3 3 0 1 1-5.714 0" />
              </svg>
            </div>
            <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">No notifications yet</p>
            <p className="text-[12px] text-[#6B7280]">You&apos;ll see mentions, messages, and updates here.</p>
          </div>
        ) : (
          <div className="space-y-1">
            {filtered.map((n) => {
              const hasLink = !!getEntityPath(n.related_entity_type, n.related_entity_id)
              return (
                <div
                  key={n.id}
                  onClick={() => handleRowClick(n)}
                  className={`flex items-start gap-3 px-4 py-3 rounded-[8px] transition-colors ${
                    n.is_read
                      ? 'bg-surface-card dark:bg-dark-card'
                      : 'bg-[#EDEEF0] dark:bg-[#2D2D2D] border border-surface-border dark:border-dark-border'
                  } ${hasLink ? 'cursor-pointer hover:bg-[#E4E6EA] dark:hover:bg-[#383838]' : ''}`}
                >
                  {/* Unread dot */}
                  <div className="flex-shrink-0 mt-1.5">
                    <div className={`w-2 h-2 rounded-full ${n.is_read ? 'bg-transparent' : 'bg-brand'}`} />
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0] leading-snug">{n.title}</p>
                    <p className="text-[12px] text-[#6B7280] mt-0.5 truncate">{n.body}</p>
                  </div>

                  {/* Timestamp */}
                  <span className="text-[11px] text-[#6B7280] flex-shrink-0 mt-0.5">{relativeTime(n.created_at)}</span>
                </div>
              )
            })}
          </div>
        )}
      </div>
  )
}
