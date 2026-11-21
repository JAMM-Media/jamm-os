// path: frontend/src/app/(app)/notifications/page.tsx
'use client'

import { useMemo, useRef, useState } from 'react'
import { useInfiniteQuery, useQuery, useQueryClient, type InfiniteData } from '@tanstack/react-query'
import { useRouter } from 'next/navigation'
import api from '@/lib/api'
import { toast } from 'sonner'
import { useAuth } from '@/lib/hooks/useAuth'
import { DeleteRequestActions } from '@/components/notifications/DeleteRequestActions'
import { isDeleteRequestRow } from '@/lib/deleteRequestState'
import { getEntityPath, getEntityDestinationLabel, isAsyncDestination } from '@/lib/notificationPaths'
import { resolveIrsAuthorizationPath } from '@/lib/irsAuthorizationDestination'
import {
  DAY_GROUP_LABELS,
  dedupeById,
  getDayGroup,
  getNotificationTypeLabel,
  splitDeleteRequestBody,
  type DayGroup,
} from '@/lib/notificationDisplay'

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

// Response shape of GET /api/v1/notifications/ (PaginatedResponse)
interface NotificationsResponse {
  items: Notification[]
  total: number
  limit: number
  offset: number
}

type CachedNotifications = InfiniteData<NotificationsResponse, number>

const PAGE_SIZE = 50

// Marks one row (or every accumulated row when id is null) as read across
// all loaded pages, so a row stays read after Load more.
function markCachedRead(
  old: CachedNotifications | undefined,
  id: string | null,
): CachedNotifications | undefined {
  if (!old) return old
  return {
    ...old,
    pages: old.pages.map((p) => ({
      ...p,
      items: p.items.map((n) => (id === null || n.id === id ? { ...n, is_read: true } : n)),
    })),
  }
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

export default function NotificationsPage() {
  const queryClient = useQueryClient()
  const router = useRouter()
  const { user } = useAuth()
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState('all')
  const [readFilter, setReadFilter] = useState('all')
  // True while an async destination (a lookup before navigating) is being opened.
  const openingAsync = useRef(false)

  const {
    data,
    isLoading,
    isError,
    refetch,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isFetchNextPageError,
  } = useInfiniteQuery({
    queryKey: ['notifications'],
    initialPageParam: 0,
    queryFn: ({ pageParam }): Promise<NotificationsResponse> =>
      api.get(`/api/v1/notifications/?limit=${PAGE_SIZE}&skip=${pageParam}`).then((r) => r.data),
    // Next skip is the number of rows fetched so far. Rows arriving mid-session
    // shift offsets, so the loaded rows are deduped by id below.
    getNextPageParam: (lastPage, allPages) => {
      const fetched = allPages.reduce((sum, p) => sum + p.items.length, 0)
      if (lastPage.items.length === 0 || fetched >= lastPage.total) return undefined
      return fetched
    },
    staleTime: 30 * 1000,
  })

  // Same key and queryFn as the Sidebar badge, so the cache entry is shared.
  const { data: unreadData } = useQuery({
    queryKey: ['notifications-unread-count'],
    queryFn: () => api.get('/api/v1/notifications/unread-count').then((r) => r.data),
    staleTime: 30 * 1000,
  })
  const serverUnread: number = unreadData?.count ?? 0

  const notifications = useMemo(
    () => dedupeById(data?.pages.flatMap((p) => p.items) ?? []),
    [data],
  )
  const total = data?.pages[data.pages.length - 1]?.total ?? 0
  const loadedUnread = notifications.filter((n) => !n.is_read).length
  const showMarkAll = loadedUnread > 0 || serverUnread > 0
  const loadedOnly = notifications.length < total

  const filtered = notifications.filter((n) => {
    if (search && !n.title.toLowerCase().includes(search.toLowerCase()) && !n.body.toLowerCase().includes(search.toLowerCase())) return false
    if (typeFilter !== 'all' && n.notification_type !== typeFilter) return false
    if (readFilter === 'unread' && n.is_read) return false
    if (readFilter === 'read' && !n.is_read) return false
    return true
  })

  async function handleMarkRead(id: string) {
    await api.patch(`/api/v1/notifications/${id}/read`)
    queryClient.setQueryData<CachedNotifications>(['notifications'], (old) => markCachedRead(old, id))
    queryClient.invalidateQueries({ queryKey: ['notifications-unread-count'] })
  }

  async function handleMarkAllRead() {
    await api.patch('/api/v1/notifications/read-all')
    queryClient.setQueryData<CachedNotifications>(['notifications'], (old) => markCachedRead(old, null))
    queryClient.invalidateQueries({ queryKey: ['notifications-unread-count'] })
    toast.success('All notifications marked as read')
  }

  async function handleRowClick(n: Notification) {
    const path = getEntityPath(n.related_entity_type, n.related_entity_id)
    const asyncId = isAsyncDestination(n.related_entity_type) ? n.related_entity_id : undefined
    if (asyncId) {
      // A second click while the first is still opening is ignored.
      if (openingAsync.current) return
      openingAsync.current = true
    }
    try {
      if (!n.is_read) {
        try {
          await handleMarkRead(n.id)
        } catch {
          toast.error('Could not mark notification as read')
        }
      }
      if (asyncId) {
        try {
          router.push(await resolveIrsAuthorizationPath(asyncId))
        } catch {
          toast.error('Could not open this IRS authorization')
        }
        return
      }
      if (path) router.push(path)
    } finally {
      if (asyncId) openingAsync.current = false
    }
  }

  const uniqueTypes = Array.from(
    new Set(notifications.map((n) => n.notification_type))
  ).sort()

  // Rows arrive newest first, so each day group is contiguous.
  const now = new Date()
  const groups: Array<{ group: DayGroup; rows: Notification[] }> = []
  for (const n of filtered) {
    const g = getDayGroup(n.created_at, now)
    const last = groups[groups.length - 1]
    if (last && last.group === g) last.rows.push(n)
    else groups.push({ group: g, rows: [n] })
  }

  return (
      <div className="p-6 max-w-3xl">
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <h1 className="text-[24px] font-medium text-brand dark:text-[#EDEEF0]">Notifications</h1>
          {showMarkAll && (
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
                {getNotificationTypeLabel(t)}
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
        ) : isError && !data ? (
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
          <div>
            {groups.map(({ group, rows }) => (
              <section key={`${group}-${rows[0].id}`} className="mb-4">
                <h2 className="text-[11px] font-medium uppercase tracking-wide text-[#6B7280] mb-1.5 px-1">
                  {DAY_GROUP_LABELS[group]}
                </h2>
                <div className="space-y-1">
                  {rows.map((n) => {
                    const destLabel = getEntityDestinationLabel(n.related_entity_type, n.related_entity_id)
                    const { main, reason } = splitDeleteRequestBody(n.title, n.body, n.related_entity_type)
                    return (
                      <div
                        key={n.id}
                        data-unread={n.is_read ? 'false' : 'true'}
                        onClick={() => handleRowClick(n)}
                        className={`flex items-start gap-3 px-4 py-3 rounded-[8px] transition-colors ${
                          n.is_read
                            ? 'bg-surface-card dark:bg-dark-card'
                            : 'bg-[#EDEEF0] dark:bg-[#2D2D2D] border border-surface-border dark:border-dark-border'
                        } ${destLabel ? 'cursor-pointer hover:bg-[#E4E6EA] dark:hover:bg-[#383838]' : ''}`}
                      >
                        {/* Unread dot */}
                        <div className="flex-shrink-0 mt-1.5">
                          <div className={`w-2 h-2 rounded-full ${n.is_read ? 'bg-transparent' : 'bg-brand'}`} />
                        </div>

                        {/* Content */}
                        <div className="flex-1 min-w-0">
                          <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0] leading-snug">{n.title}</p>
                          <p className="text-[12px] text-[#6B7280] mt-0.5 whitespace-pre-wrap break-words">{main}</p>
                          {reason && (
                            <p className="text-[12px] text-[#6B7280] mt-0.5 whitespace-pre-wrap break-words">
                              <span className="font-medium">Reason:</span> {reason}
                            </p>
                          )}
                          {isDeleteRequestRow(n.title, n.related_entity_type, n.related_entity_id) && (
                            <DeleteRequestActions notification={n} role={user?.role} onMarkRead={handleMarkRead} />
                          )}
                          <p className="text-[11px] text-[#9CA3AF] mt-1">
                            {destLabel ? `Opens: ${destLabel}` : 'No linked page'}
                          </p>
                        </div>

                        {/* Timestamp */}
                        <span className="text-[11px] text-[#6B7280] flex-shrink-0 mt-0.5">{relativeTime(n.created_at)}</span>
                      </div>
                    )
                  })}
                </div>
              </section>
            ))}
          </div>
        )}

        {/* Load more and loaded-only note */}
        {!isLoading && !(isError && !data) && (
          <div className="mt-2 flex flex-col items-center gap-2">
            {loadedOnly && (
              <p className="text-[11px] text-[#6B7280] text-center">
                Showing {notifications.length} of {total} notifications. Search and filters apply to the loaded notifications only.
              </p>
            )}
            {isFetchNextPageError && (
              <p className="text-[12px] text-[#6B7280]">Could not load more notifications.</p>
            )}
            {hasNextPage && (
              <button
                onClick={() => fetchNextPage()}
                disabled={isFetchingNextPage}
                className="text-[12px] font-medium px-4 py-2 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-brand dark:text-[#EDEEF0] disabled:opacity-60"
              >
                {isFetchingNextPage ? 'Loading...' : isFetchNextPageError ? 'Retry' : 'Load more'}
              </button>
            )}
          </div>
        )}
      </div>
  )
}
