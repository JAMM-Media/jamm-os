// frontend/src/app/(dashboard)/timesheets/AggregateTab.tsx
'use client'

import { useState, useEffect } from 'react'
import { ChevronLeft, ChevronRight, Download, Pencil, Check, AlertTriangle } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import api from '@/lib/api'

export type Period = 'weekly' | 'biweekly' | 'monthly' | 'quarterly' | 'yearly'

export interface AggregateTabProps {
  period: Period
  selectedUserId: string | null
  currentUserId: string
  userRole: string
  billableFilter?: string
  engagementFilter?: string
}

interface SummaryRow {
  user_id: string
  user_name: string
  date: string
  total_hours: number
  billable_hours: number
  billable_pct: number
  entry_count: number
  is_submitted: boolean
  has_edits: boolean
}

interface TimeEntry {
  id: string
  engagement_id: string
  user_id: string
  description: string
  hours: number
  hourly_rate: number
  is_billable: boolean
  date: string
  start_time?: string | null
  end_time?: string | null
  activity_type?: string | null
  is_submitted: boolean
  is_approved: boolean
  edited_after_submission: boolean
}

function toISO(d: Date) {
  return d.toISOString().slice(0, 10)
}

function addDays(d: Date, n: number): Date {
  const result = new Date(d)
  result.setDate(result.getDate() + n)
  return result
}

function startOfWeek(d: Date): Date {
  const day = d.getDay()
  const diff = day === 0 ? -6 : 1 - day
  return addDays(d, diff)
}

function calcDateRange(period: Period, offset: number): { start: Date; end: Date } {
  const now = new Date()
  if (period === 'weekly') {
    const mon = addDays(startOfWeek(now), offset * 7)
    return { start: mon, end: addDays(mon, 6) }
  }
  if (period === 'biweekly') {
    const mon = addDays(startOfWeek(now), offset * 14)
    return { start: mon, end: addDays(mon, 13) }
  }
  if (period === 'monthly') {
    const d = new Date(now.getFullYear(), now.getMonth() + offset, 1)
    return {
      start: d,
      end: new Date(d.getFullYear(), d.getMonth() + 1, 0),
    }
  }
  if (period === 'quarterly') {
    const q = Math.floor(now.getMonth() / 3) + offset
    const year = now.getFullYear() + Math.floor(q / 4)
    const qMod = ((q % 4) + 4) % 4
    const start = new Date(year, qMod * 3, 1)
    return { start, end: new Date(year, qMod * 3 + 3, 0) }
  }
  // yearly
  const year = now.getFullYear() + offset
  return {
    start: new Date(year, 0, 1),
    end: new Date(year, 11, 31),
  }
}

function formatPeriodLabel(period: Period, start: Date, end: Date): string {
  const fmt = (d: Date) =>
    d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  const fmtYear = (d: Date) => d.getFullYear()

  if (period === 'weekly' || period === 'biweekly') {
    return `${fmt(start)} – ${fmt(end)}, ${fmtYear(end)}`
  }
  if (period === 'monthly') {
    return start.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
  }
  if (period === 'quarterly') {
    const q = Math.floor(start.getMonth() / 3) + 1
    return `Q${q} ${fmtYear(start)}`
  }
  return String(fmtYear(start))
}

function groupByUser(rows: SummaryRow[]): Record<string, SummaryRow[]> {
  const result: Record<string, SummaryRow[]> = {}
  for (const row of rows) {
    if (!result[row.user_id]) result[row.user_id] = []
    result[row.user_id].push(row)
  }
  return result
}

function userStatus(rows: SummaryRow[]): 'green' | 'amber' | 'red' {
  if (rows.every((r) => r.is_submitted)) return 'green'
  if (rows.some((r) => r.is_submitted)) return 'amber'
  return 'red'
}

function totalHoursForUser(rows: SummaryRow[]): number {
  return rows.reduce((s, r) => s + r.total_hours, 0)
}

const STATUS_COLORS = {
  green: 'bg-green-500',
  amber: 'bg-amber-400',
  red: 'bg-red-500',
}

export default function AggregateTab({
  period,
  selectedUserId,
  currentUserId,
  userRole,
  billableFilter = 'all',
  engagementFilter = 'all',
}: AggregateTabProps) {
  const isManagerOrAbove = userRole === 'firm_owner' || userRole === 'manager'
  const [offset, setOffset] = useState(0)
  const [summary, setSummary] = useState<SummaryRow[]>([])
  const [entries, setEntries] = useState<TimeEntry[]>([])
  const [engagements, setEngagements] = useState<Record<string, string>>({})
  const [users, setUsers] = useState<Record<string, string>>({})
  const [loadingSummary, setLoadingSummary] = useState(true)
  const [loadingEntries, setLoadingEntries] = useState(true)
  const [editModal, setEditModal] = useState<TimeEntry | null>(null)
  const [editNote, setEditNote] = useState('')
  const [editFields, setEditFields] = useState<Partial<TimeEntry>>({})

  const { start, end } = calcDateRange(period, offset)
  const startISO = toISO(start)
  const endISO = toISO(end)

  const effectiveUserId =
    !isManagerOrAbove ? currentUserId : selectedUserId ?? undefined

  useEffect(() => {
    api.get('/engagements/?limit=100').then((r) => {
      const map: Record<string, string> = {}
      for (const e of r.data?.items ?? []) map[e.id] = e.name
      setEngagements(map)
    }).catch(() => {})
  }, [])

  useEffect(() => {
    setLoadingSummary(true)
    const params = new URLSearchParams({ start_date: startISO, end_date: endISO })
    if (effectiveUserId) params.set('user_id', effectiveUserId)
    api
      .get(`/api/v1/time-entries/summary?${params}`)
      .then((r) => {
        const rows: SummaryRow[] = r.data ?? []
        setSummary(rows)
        const userMap: Record<string, string> = {}
        for (const row of rows) userMap[row.user_id] = row.user_name
        setUsers((prev) => ({ ...prev, ...userMap }))
      })
      .catch(() => setSummary([]))
      .finally(() => setLoadingSummary(false))

    setLoadingEntries(true)
    const eParams = new URLSearchParams({ start_date: startISO, end_date: endISO, limit: '500' })
    if (effectiveUserId) eParams.set('user_id', effectiveUserId)
    api
      .get(`/api/v1/time-entries/?${eParams}`)
      .then((r) => setEntries(r.data?.items ?? []))
      .catch(() => setEntries([]))
      .finally(() => setLoadingEntries(false))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [startISO, endISO, effectiveUserId])

  function handleExport() {
    const params = new URLSearchParams({ start_date: startISO, end_date: endISO })
    if (effectiveUserId) params.set('user_id', effectiveUserId)
    const url = `/api/v1/time-entries/export?${params}`
    window.open(url, '_blank')
  }

  async function handleApprove(entryId: string) {
    try {
      await api.post(`/api/v1/time-entries/${entryId}/approve`)
      setEntries((prev) =>
        prev.map((e) => (e.id === entryId ? { ...e, is_approved: true } : e))
      )
      toast.success('Entry approved')
    } catch {
      toast.error('Failed to approve entry')
    }
  }

  async function handleSubmittedEdit() {
    if (!editModal) return
    try {
      await api.patch(`/api/v1/time-entries/${editModal.id}/submitted-edit`, {
        ...editFields,
        edit_note: editNote || undefined,
      })
      setEditModal(null)
      setEditNote('')
      setEditFields({})
      // Reload
      const params = new URLSearchParams({ start_date: startISO, end_date: endISO, limit: '500' })
      if (effectiveUserId) params.set('user_id', effectiveUserId)
      const r = await api.get(`/api/v1/time-entries/?${params}`)
      setEntries(r.data?.items ?? [])
      toast.success('Entry updated')
    } catch {
      toast.error('Failed to update entry')
    }
  }

  const summaryRows = summary.filter((row) => {
    if (billableFilter === 'billable') return row.billable_hours > 0
    if (billableFilter === 'non_billable') return row.billable_hours === 0
    return true
  })
  const userGroups = groupByUser(summaryRows)

  const WEEKLY_OT_HOURS = (period === 'weekly' || period === 'biweekly') ? 40 : Infinity

  return (
    <div className="flex flex-col gap-4">
      {/* Navigation + export */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setOffset((o) => o - 1)}
            className="p-1.5 rounded border border-surface-border dark:border-dark-border hover:bg-[#F3F4F6] dark:hover:bg-[#2A2A2A] text-[#6B7280]"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <span className="text-[13px] font-medium text-brand dark:text-[#EDEEF0] min-w-[160px] text-center">
            {formatPeriodLabel(period, start, end)}
          </span>
          <button
            onClick={() => setOffset((o) => o + 1)}
            className="p-1.5 rounded border border-surface-border dark:border-dark-border hover:bg-[#F3F4F6] dark:hover:bg-[#2A2A2A] text-[#6B7280]"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
        <button
          onClick={handleExport}
          className="flex items-center gap-1.5 h-8 px-3 text-[13px] font-medium rounded-[6px] border border-surface-border dark:border-dark-border text-[#374151] dark:text-[#D1D5DB] hover:bg-[#F3F4F6] dark:hover:bg-[#2A2A2A]"
        >
          <Download className="h-3.5 w-3.5" />
          Export CSV
        </button>
      </div>

      {/* Manager summary */}
      {isManagerOrAbove && !loadingSummary && Object.keys(userGroups).length > 0 && (
        <div className="rounded-[8px] border border-[0.5px] border-surface-border dark:border-dark-border overflow-hidden">
          <table className="w-full border-collapse text-[12px]">
            <thead>
              <tr className="bg-surface-card dark:bg-[#252525]">
                {['Staff', 'Total Hours', 'Billable Hrs', 'Billable %', 'Entries', 'Status'].map(
                  (col) => (
                    <th
                      key={col}
                      className="px-3 py-2 text-left text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] whitespace-nowrap"
                    >
                      {col}
                    </th>
                  )
                )}
              </tr>
            </thead>
            <tbody>
              {Object.entries(userGroups).map(([uid, rows], i, arr) => {
                const total = totalHoursForUser(rows)
                const billable = rows.reduce((s, r) => s + r.billable_hours, 0)
                const pct =
                  total > 0 ? Math.round((billable / total) * 100) : 0
                const count = rows.reduce((s, r) => s + r.entry_count, 0)
                const status = userStatus(rows)
                const isOT = total > WEEKLY_OT_HOURS
                const isHardOT = total > 50
                return (
                  <tr
                    key={uid}
                    className={cn(
                      'border-b border-[0.5px] border-[#D5D8DE] dark:border-dark-card last:border-0',
                      isHardOT
                        ? 'bg-red-50 dark:bg-red-950/20'
                        : isOT
                        ? 'bg-amber-50 dark:bg-amber-950/20'
                        : i % 2 === 0
                        ? 'bg-surface-page dark:bg-dark-page'
                        : 'bg-surface-card dark:bg-[#252525]'
                    )}
                  >
                    <td className="px-3 py-2 font-medium text-brand dark:text-[#EDEEF0]">
                      {rows[0]?.user_name ?? uid}
                    </td>
                    <td className="px-3 py-2 text-[#374151] dark:text-[#9CA3AF]">
                      {total.toFixed(2)}
                    </td>
                    <td className="px-3 py-2 text-[#374151] dark:text-[#9CA3AF]">
                      {billable.toFixed(2)}
                    </td>
                    <td className="px-3 py-2 text-[#374151] dark:text-[#9CA3AF]">{pct}%</td>
                    <td className="px-3 py-2 text-[#374151] dark:text-[#9CA3AF]">{count}</td>
                    <td className="px-3 py-2">
                      <span
                        className={cn('inline-block w-2.5 h-2.5 rounded-full', STATUS_COLORS[status])}
                        title={status}
                      />
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Detail table */}
      {loadingEntries ? (
        <div className="text-[13px] text-[#6B7280] py-4">Loading...</div>
      ) : entries.length === 0 ? (
        <div className="text-[13px] text-[#6B7280] py-8 text-center">
          No entries for this period.
        </div>
      ) : (
        <div className="rounded-[8px] border border-[0.5px] border-surface-border dark:border-dark-border overflow-x-auto">
          <table className="w-full border-collapse text-[12px] min-w-[700px]">
            <thead>
              <tr className="bg-surface-card dark:bg-[#252525]">
                {[
                  'Date',
                  ...(isManagerOrAbove ? ['Staff'] : []),
                  'Engagement',
                  'Activity',
                  'Start',
                  'End',
                  'Hours',
                  'Billable',
                  'Notes',
                  'Submitted',
                  'Approved',
                  'Actions',
                ].map((col) => (
                  <th
                    key={col}
                    className="px-3 py-2 text-left text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] whitespace-nowrap"
                  >
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {entries.filter((e) => {
                if (billableFilter === 'billable') return e.is_billable === true
                if (billableFilter === 'non_billable') return e.is_billable === false
                if (engagementFilter !== 'all' && e.engagement_id !== engagementFilter) return false
                return true
              }).map((entry, i) => {
                const isOwn = entry.user_id === currentUserId
                return (
                  <tr
                    key={entry.id}
                    className={cn(
                      'border-b border-[0.5px] border-[#D5D8DE] dark:border-dark-card last:border-0',
                      i % 2 === 0
                        ? 'bg-surface-page dark:bg-dark-page'
                        : 'bg-surface-card dark:bg-[#252525]'
                    )}
                  >
                    <td className="px-3 py-2 whitespace-nowrap text-[#374151] dark:text-[#9CA3AF]">
                      {entry.date}
                    </td>
                    {isManagerOrAbove && (
                      <td className="px-3 py-2 whitespace-nowrap text-brand dark:text-[#EDEEF0] font-medium">
                        {users[entry.user_id] ?? '—'}
                      </td>
                    )}
                    <td className="px-3 py-2 text-[#374151] dark:text-[#9CA3AF]">
                      {engagements[entry.engagement_id] ?? '—'}
                    </td>
                    <td className="px-3 py-2 text-[#374151] dark:text-[#9CA3AF]">
                      {entry.activity_type ?? '—'}
                    </td>
                    <td className="px-3 py-2 whitespace-nowrap text-[#374151] dark:text-[#9CA3AF]">
                      {entry.start_time ?? '—'}
                    </td>
                    <td className="px-3 py-2 whitespace-nowrap text-[#374151] dark:text-[#9CA3AF]">
                      {entry.end_time ?? '—'}
                    </td>
                    <td className="px-3 py-2 text-[#374151] dark:text-[#9CA3AF]">
                      {Number(entry.hours).toFixed(2)}
                    </td>
                    <td className="px-3 py-2">
                      {entry.is_billable ? (
                        <Check className="h-3.5 w-3.5 text-green-500" />
                      ) : (
                        <span className="text-[#9CA3AF]">—</span>
                      )}
                    </td>
                    <td className="px-3 py-2 max-w-[160px] truncate text-[#374151] dark:text-[#9CA3AF]">
                      {entry.description}
                    </td>
                    <td className="px-3 py-2">
                      {entry.is_submitted ? (
                        <Check className="h-3.5 w-3.5 text-green-500" />
                      ) : (
                        <span className="text-[#9CA3AF]">—</span>
                      )}
                    </td>
                    <td className="px-3 py-2">
                      {entry.is_approved ? (
                        <Check className="h-3.5 w-3.5 text-green-500" />
                      ) : (
                        <span className="text-[#9CA3AF]">—</span>
                      )}
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-1">
                        {isManagerOrAbove ? (
                          <>
                            {entry.is_submitted && !entry.is_approved && (
                              <button
                                onClick={() => handleApprove(entry.id)}
                                className="px-2 py-0.5 text-[11px] bg-green-600 text-white rounded hover:bg-green-700"
                              >
                                Approve
                              </button>
                            )}
                            <button
                              onClick={() => {
                                setEditModal(entry)
                                setEditFields({})
                                setEditNote('')
                              }}
                              className="p-1 rounded text-amber-500 hover:text-amber-700 hover:bg-amber-50 dark:hover:bg-[#2A2A2A]"
                              title="Edit submitted entry"
                            >
                              <Pencil className="h-3.5 w-3.5" />
                            </button>
                          </>
                        ) : isOwn ? (
                          !entry.is_submitted ? (
                            <button
                              onClick={() => {
                                setEditModal(entry)
                                setEditFields({})
                                setEditNote('')
                              }}
                              className="p-1 rounded text-[#6B7280] hover:text-brand hover:bg-[#F3F4F6] dark:hover:bg-[#2A2A2A]"
                              title="Edit"
                            >
                              <Pencil className="h-3.5 w-3.5" />
                            </button>
                          ) : (
                            <button
                              onClick={() => {
                                setEditModal(entry)
                                setEditFields({})
                                setEditNote('')
                              }}
                              className="p-1 rounded text-amber-500 hover:text-amber-700"
                              title="Edit submitted entry"
                            >
                              <Pencil className="h-3.5 w-3.5" />
                            </button>
                          )
                        ) : null}
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Edit modal */}
      {editModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white dark:bg-dark-card rounded-[10px] p-6 shadow-xl max-w-md w-full mx-4">
            <div className="flex items-start gap-2 mb-4">
              <AlertTriangle className="h-5 w-5 text-amber-500 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-[14px] font-medium text-[#111827] dark:text-[#EDEEF0]">
                  {editModal.is_submitted ? 'Editing a submitted entry' : 'Edit entry'}
                </p>
                {editModal.is_submitted && (
                  <p className="text-[12px] text-[#6B7280] mt-0.5">
                    This will notify all managers.
                  </p>
                )}
              </div>
            </div>
            <div className="flex flex-col gap-3 mb-4">
              <div className="flex flex-col gap-1">
                <label className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em]">Hours</label>
                <input
                  type="number"
                  min={0.25}
                  max={24}
                  step={0.25}
                  defaultValue={editModal.hours}
                  onChange={(e) => setEditFields((f) => ({ ...f, hours: parseFloat(e.target.value) }))}
                  className="w-full rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[13px] px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-brand"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em]">Description</label>
                <input
                  type="text"
                  defaultValue={editModal.description}
                  onChange={(e) => setEditFields((f) => ({ ...f, description: e.target.value }))}
                  className="w-full rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[13px] px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-brand"
                />
              </div>
              {editModal.is_submitted && (
                <div className="flex flex-col gap-1">
                  <label className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em]">
                    Reason for edit (optional)
                  </label>
                  <textarea
                    rows={2}
                    value={editNote}
                    onChange={(e) => setEditNote(e.target.value)}
                    placeholder="Add a note..."
                    className="w-full rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[13px] px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-brand resize-none"
                  />
                </div>
              )}
            </div>
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => { setEditModal(null); setEditNote(''); setEditFields({}) }}
                className="px-4 py-2 text-[13px] rounded-[6px] border border-surface-border dark:border-dark-border text-[#374151] dark:text-[#D1D5DB]"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmittedEdit}
                className="px-4 py-2 text-[13px] rounded-[6px] bg-brand text-white hover:opacity-90"
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
