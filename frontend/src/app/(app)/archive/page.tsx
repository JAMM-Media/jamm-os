// frontend/src/app/(app)/archive/page.tsx
'use client'

import { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
import { Star, Archive } from 'lucide-react'
import { toast } from 'sonner'
import { useAuth } from '@/lib/hooks/useAuth'
import { useFetch } from '@/lib/hooks/useFetch'
import api from '@/lib/api'
import { archiveApi, type ArchiveEntry, type ArchiveResponse } from '@/lib/api/archive'

interface StaffUser {
  id: string
  full_name: string
  email: string
}

function SkeletonRow() {
  return (
    <tr className="border-b border-[0.5px] border-[#D5D8DE] dark:border-dark-card">
      {Array.from({ length: 8 }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <div className="h-2 rounded bg-[#D5D8DE] dark:bg-[#444444] animate-pulse" style={{ width: `${40 + (i % 3) * 20}px` }} />
        </td>
      ))}
    </tr>
  )
}

function EmptyArchive() {
  return (
    <div className="flex flex-col items-center justify-center py-24 gap-[10px]">
      <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-surface-card dark:bg-dark-card border border-[0.5px] border-surface-border dark:border-dark-border">
        <Archive className="h-[18px] w-[18px] text-[#6B7280]" />
      </div>
      <div className="text-center">
        <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0] mb-[3px]">
          No completed work yet
        </p>
        <p className="text-[12px] text-[#6B7280]">
          The archive fills automatically as tasks are completed. Nothing is added manually.
        </p>
      </div>
    </div>
  )
}

function EmptyFiltered({ onClear }: { onClear: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-24 gap-[10px]">
      <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-surface-card dark:bg-dark-card border border-[0.5px] border-surface-border dark:border-dark-border">
        <Archive className="h-[18px] w-[18px] text-[#6B7280]" />
      </div>
      <div className="text-center">
        <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0] mb-[3px]">
          No results for these filters
        </p>
        <p className="text-[12px] text-[#6B7280]">
          Try adjusting the date range or other filters.
        </p>
      </div>
      <button
        onClick={onClear}
        className="mt-1 px-3 h-9 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[13px] text-brand dark:text-[#EDEEF0] hover:bg-[#DDDFE3] dark:hover:bg-[#323232] transition-colors"
      >
        Clear filters
      </button>
    </div>
  )
}

export default function ArchivePage() {
  const { user } = useAuth()
  const isManagerOrAbove = user?.role === 'firm_owner' || user?.role === 'manager'

  const [selectedUserId, setSelectedUserId] = useState<string>('')
  const [staffList, setStaffList] = useState<StaffUser[]>([])
  const [clientList, setClientList] = useState<{ id: string; name: string }[]>([])
  const [engagementList, setEngagementList] = useState<{ id: string; name: string }[]>([])

  const [search, setSearch] = useState('')
  const [fromDate, setFromDate] = useState('')
  const [toDate, setToDate] = useState('')
  const [clientFilter, setClientFilter] = useState('all')
  const [engagementFilter, setEngagementFilter] = useState('all')
  const [roleFilter, setRoleFilter] = useState('all')
  const [starredFilter, setStarredFilter] = useState('all')

  const [starredOverrides, setStarredOverrides] = useState<Record<string, boolean>>({})

  const hasFilters = fromDate !== '' || toDate !== '' || clientFilter !== 'all' || engagementFilter !== 'all' || roleFilter !== 'all' || starredFilter !== 'all'

  useEffect(() => {
    if (user?.id) setSelectedUserId(user.id)
  }, [user?.id])

  useEffect(() => {
    if (!isManagerOrAbove) return
    api.get('/users/?limit=100').then((r) => {
      const items: StaffUser[] = (r.data?.items ?? []).filter(
        (u: StaffUser & { role?: string }) =>
          u.role !== 'client_portal_user' && u.role !== 'system_admin'
      )
      setStaffList(items)
    }).catch(() => {})
  }, [isManagerOrAbove])

  useEffect(() => {
    api.get('/clients/?limit=100').then((r) => {
      setClientList((r.data?.items ?? []).map((c: { id: string; name: string }) => ({ id: c.id, name: c.name })))
    }).catch(() => {})
    api.get('/engagements/?limit=100').then((r) => {
      setEngagementList((r.data?.items ?? []).map((e: { id: string; name: string }) => ({ id: e.id, name: e.name })))
    }).catch(() => {})
  }, [])

  const params: Record<string, string | boolean> = {}
  if (fromDate) params.from = fromDate
  if (toDate) params.to = toDate
  if (clientFilter !== 'all') params.client_id = clientFilter
  if (engagementFilter !== 'all') params.engagement_id = engagementFilter
  if (roleFilter !== 'all') params.role = roleFilter
  if (starredFilter === 'starred') params.starred = true
  if (starredFilter === 'unstarred') params.starred = false

  const { data, isLoading } = useFetch<ArchiveResponse>(
    () => selectedUserId ? archiveApi.getArchive(selectedUserId, params) : Promise.resolve({ items: [], total: 0, aggregates: { tasks_completed: 0, hours_logged: 0, engagements_touched: 0 } }),
    [selectedUserId, fromDate, toDate, clientFilter, engagementFilter, roleFilter, starredFilter]
  )

  const clearFilters = useCallback(() => {
    setFromDate('')
    setToDate('')
    setClientFilter('all')
    setEngagementFilter('all')
    setRoleFilter('all')
    setStarredFilter('all')
    setSearch('')
  }, [])

  const handleStarToggle = useCallback(async (entry: ArchiveEntry) => {
    let wasStarred = false
    setStarredOverrides((prev) => {
      wasStarred = prev[entry.task_id] ?? entry.starred
      return { ...prev, [entry.task_id]: !wasStarred }
    })
    try {
      if (wasStarred) {
        await archiveApi.unstarTask(entry.task_id)
      } else {
        await archiveApi.starTask(entry.task_id)
      }
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(detail ?? 'Failed to update star')
      setStarredOverrides((prev) => ({ ...prev, [entry.task_id]: wasStarred }))
    }
  }, [])

  if (!user) return null

  const isViewingOtherUser = selectedUserId !== '' && selectedUserId !== user.id

  const items = data?.items ?? []
  const aggregates = data?.aggregates

  const filtered = search.trim()
    ? items.filter((e) =>
        e.task_title.toLowerCase().includes(search.trim().toLowerCase()) ||
        e.client.name.toLowerCase().includes(search.trim().toLowerCase())
      )
    : items

  const selectClass = 'h-8 px-2 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[13px] text-brand dark:text-[#EDEEF0] focus:outline-none'

  return (
    <div className="flex flex-col p-6 gap-4">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <h1 className="font-medium text-[#1F3148] dark:text-[#EDEEF0]" style={{ fontSize: 20 }}>
          Archive
        </h1>
        <div className="flex items-center gap-2 flex-wrap">
          {/* Search */}
          <input
            type="text"
            placeholder="Search tasks..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="h-8 px-2 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[13px] text-brand dark:text-[#EDEEF0] placeholder:text-[#6B7280] focus:outline-none w-[180px]"
          />

          {/* Date range */}
          <input
            type="date"
            value={fromDate}
            onChange={(e) => setFromDate(e.target.value)}
            className={selectClass}
            title="From date"
          />
          <input
            type="date"
            value={toDate}
            onChange={(e) => setToDate(e.target.value)}
            className={selectClass}
            title="To date"
          />

          {/* Client filter */}
          <select value={clientFilter} onChange={(e) => setClientFilter(e.target.value)} className={selectClass}>
            <option value="all">All Clients</option>
            {clientList.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>

          {/* Engagement filter */}
          <select value={engagementFilter} onChange={(e) => setEngagementFilter(e.target.value)} className={selectClass}>
            <option value="all">All Engagements</option>
            {engagementList.map((e) => (
              <option key={e.id} value={e.id}>{e.name}</option>
            ))}
          </select>

          {/* Role filter */}
          <select value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)} className={selectClass}>
            <option value="all">All Roles</option>
            <option value="performed">Performed</option>
            <option value="reviewed">Reviewed</option>
          </select>

          {/* Starred filter */}
          <select value={starredFilter} onChange={(e) => setStarredFilter(e.target.value)} className={selectClass}>
            <option value="all">All</option>
            <option value="starred">Starred</option>
            <option value="unstarred">Unstarred</option>
          </select>

          {/* Staff selector (manager/owner only) */}
          {isManagerOrAbove && (
            <select
              value={selectedUserId}
              onChange={(e) => setSelectedUserId(e.target.value)}
              className={selectClass}
            >
              {staffList.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.full_name || s.email}
                </option>
              ))}
            </select>
          )}
        </div>
      </div>

      {/* Aggregate row */}
      {aggregates && !isLoading && (
        <div className="flex items-center gap-6">
          <span className="text-[12px] text-[#6B7280]">
            <span className="font-medium text-[#374151] dark:text-[#9CA3AF]">{aggregates.tasks_completed}</span> tasks completed
          </span>
          <span className="text-[12px] text-[#6B7280]">
            <span className="font-medium text-[#374151] dark:text-[#9CA3AF]">{aggregates.hours_logged.toFixed(1)}</span> hours
          </span>
          <span className="text-[12px] text-[#6B7280]">
            <span className="font-medium text-[#374151] dark:text-[#9CA3AF]">{aggregates.engagements_touched}</span> engagements
          </span>
        </div>
      )}

      {/* Table */}
      <div className="rounded-modal border border-[0.5px] border-surface-border dark:border-dark-border overflow-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr className="bg-surface-card dark:bg-[#252525]">
              {['Task', 'Client', 'Engagement', 'Role', 'Completed', 'Revision', 'Hours', ''].map((col) => (
                <th
                  key={col}
                  className="px-4 py-2.5 text-left text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] whitespace-nowrap"
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => <SkeletonRow key={i} />)
            ) : filtered.length === 0 ? (
              <tr>
                <td colSpan={8}>
                  {data?.total === 0 && !hasFilters && !search
                    ? <EmptyArchive />
                    : <EmptyFiltered onClear={clearFilters} />
                  }
                </td>
              </tr>
            ) : (
              filtered.map((entry, i) => {
                const isStarred = starredOverrides[entry.task_id] ?? entry.starred
                const completedDate = entry.completed_at
                  ? new Date(entry.completed_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
                  : null

                return (
                  <tr
                    key={entry.task_id}
                    className={[
                      'group bg-surface-page dark:bg-dark-page hover:bg-[#DDDFE3] dark:hover:bg-[#323232] transition-colors',
                      i !== filtered.length - 1 ? 'border-b border-[0.5px] border-[#D5D8DE] dark:border-dark-card' : '',
                    ].join(' ')}
                  >
                    {/* Task */}
                    <td className="px-4 py-3">
                      <Link
                        href={`/tasks/${entry.task_id}`}
                        className="text-[12px] font-medium text-brand dark:text-[#EDEEF0] hover:underline"
                        onClick={(e) => e.stopPropagation()}
                      >
                        {entry.task_title}
                      </Link>
                    </td>

                    {/* Client */}
                    <td className="px-4 py-3">
                      <Link
                        href={`/clients/${entry.client.id}`}
                        className="text-[12px] text-brand-light hover:underline"
                        onClick={(e) => e.stopPropagation()}
                      >
                        {entry.client.name}
                      </Link>
                    </td>

                    {/* Engagement */}
                    <td className="px-4 py-3">
                      <Link
                        href={`/engagements/${entry.engagement.id}`}
                        className="text-[12px] text-brand-light hover:underline"
                        onClick={(e) => e.stopPropagation()}
                      >
                        {entry.engagement.name}
                      </Link>
                    </td>

                    {/* Role */}
                    <td className="px-4 py-3">
                      <span className="text-[12px] text-[#374151] dark:text-[#9CA3AF] capitalize">
                        {entry.role}
                      </span>
                    </td>

                    {/* Completed */}
                    <td className="px-4 py-3">
                      {completedDate ? (
                        entry.completed_at_is_approximate ? (
                          <span className="text-[12px] text-[#9CA3AF] dark:text-[#6B7280] italic">
                            ~{completedDate}
                          </span>
                        ) : (
                          <span className="text-[12px] text-[#374151] dark:text-[#9CA3AF]">
                            {completedDate}
                          </span>
                        )
                      ) : (
                        <span className="text-[12px] text-[#9CA3AF]">--</span>
                      )}
                    </td>

                    {/* Revision */}
                    <td className="px-4 py-3">
                      {entry.revision_count != null && entry.revision_count >= 2 ? (
                        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-medium bg-[#F3F4F6] dark:bg-[#2a2a2a] text-[#374151] dark:text-[#9CA3AF]">
                          {entry.revision_count}
                        </span>
                      ) : null}
                    </td>

                    {/* Hours */}
                    <td className="px-4 py-3">
                      <span className="text-[12px] text-[#374151] dark:text-[#9CA3AF]">
                        {entry.hours.toFixed(1)}h
                      </span>
                    </td>

                    {/* Star */}
                    <td className="px-4 py-3">
                      {isViewingOtherUser ? (
                        <button
                          className="flex items-center justify-center w-6 h-6 rounded cursor-not-allowed"
                          title="You can only star items in your own archive"
                        >
                          <Star className="w-[14px] h-[14px] text-[#D1D5DB] dark:text-[#4B5563]" />
                        </button>
                      ) : (
                        <button
                          onClick={() => handleStarToggle(entry)}
                          className="flex items-center justify-center w-6 h-6 rounded hover:bg-[#D5D8DE] dark:hover:bg-[#444444] transition-colors"
                          title={isStarred ? 'Unstar' : 'Star'}
                        >
                          <Star
                            className={[
                              'w-[14px] h-[14px] transition-colors',
                              isStarred
                                ? 'fill-[#F59E0B] text-[#F59E0B]'
                                : 'text-[#9CA3AF] hover:text-[#6B7280]',
                            ].join(' ')}
                          />
                        </button>
                      )}
                    </td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
