// path: frontend/src/app/calendar/page.tsx
'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import { AppShell } from '@/components/layout/AppShell'
import { engagementsApi, type CalendarItem } from '@/lib/api'
import { CheckCircle, ChevronLeft, ChevronRight, RefreshCw } from 'lucide-react'

type ViewMode = 'list' | 'month'

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
]
const DAY_NAMES = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

function parseDate(dateStr: string): Date {
  const [y, m, d] = dateStr.split('-').map(Number)
  return new Date(y, m - 1, d)
}

function formatDate(dateStr: string): string {
  const d = parseDate(dateStr)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function urgencyColor(dateStr: string): string {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const deadline = parseDate(dateStr)
  const days = Math.ceil((deadline.getTime() - today.getTime()) / 86400000)
  if (days <= 7) return 'bg-red-500'
  if (days <= 14) return 'bg-amber-400'
  return 'bg-green-500'
}

function urgencyTextColor(dateStr: string): string {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const deadline = parseDate(dateStr)
  const days = Math.ceil((deadline.getTime() - today.getTime()) / 86400000)
  if (days <= 7) return 'text-red-600 dark:text-red-400'
  if (days <= 14) return 'text-amber-600 dark:text-amber-400'
  return 'text-green-600 dark:text-green-400'
}

function getWeekLabel(dateStr: string): string {
  const d = parseDate(dateStr)
  const day = d.getDay()
  const monday = new Date(d)
  monday.setDate(d.getDate() - day)
  return `Week of ${monday.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`
}

function groupByWeek(items: CalendarItem[]): Record<string, CalendarItem[]> {
  const groups: Record<string, CalendarItem[]> = {}
  for (const item of items) {
    const key = getWeekLabel(item.effectiveDeadline)
    if (!groups[key]) groups[key] = []
    groups[key].push(item)
  }
  return groups
}

function ListView({ items, onRowClick }: { items: CalendarItem[]; onRowClick: (id: string) => void }) {
  if (items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-3">
        <CheckCircle className="h-10 w-10 text-green-500" />
        <p className="text-[14px] font-medium text-brand dark:text-[#EDEEF0]">No upcoming deadlines in the next 6 months.</p>
        <p className="text-[12px] text-[#6B7280]">You&apos;re all clear — well done.</p>
      </div>
    )
  }

  const groups = groupByWeek(items)

  return (
    <div className="flex flex-col gap-4">
      {Object.entries(groups).map(([week, engagements]) => (
        <div key={week}>
          <p className="text-[11px] uppercase tracking-[0.05em] text-[#6B7280] mb-2">{week}</p>
          <div className="flex flex-col gap-1.5">
            {engagements.map((eng) => (
              <div
                key={eng.engagementId}
                onClick={() => onRowClick(eng.engagementId)}
                className="flex items-center justify-between bg-white dark:bg-dark-card border border-[0.5px] border-surface-border dark:border-dark-border rounded-[8px] px-3.5 py-2.5 cursor-pointer hover:bg-[#F9FAFB] dark:hover:bg-[#2A2A2A] transition-colors"
              >
                <div className="flex items-center gap-2.5 min-w-0 flex-1">
                  <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${urgencyColor(eng.effectiveDeadline)}`} />
                  <div className="min-w-0">
                    <p className="text-[13px] font-[500] text-[#111827] dark:text-[#EDEEF0] truncate">{eng.engagementName}</p>
                    <p className="text-[12px] text-[#6B7280] truncate">{eng.clientName}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0 ml-3">
                  <span className={`text-[12px] font-[500] ${urgencyTextColor(eng.effectiveDeadline)}`}>
                    {formatDate(eng.effectiveDeadline)}
                  </span>
                  {eng.deadlineType === 'extended' ? (
                    <span className="text-[11px] font-medium px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
                      Extended
                    </span>
                  ) : (
                    <span className="text-[11px] font-medium px-1.5 py-0.5 rounded bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
                      Filing
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

function MonthView({ items, month, year, onPrev, onNext, onRowClick }: {
  items: CalendarItem[]
  month: number
  year: number
  onPrev: () => void
  onNext: () => void
  onRowClick: (id: string) => void
}) {
  const [popoverDay, setPopoverDay] = useState<number | null>(null)
  const today = new Date()
  today.setHours(0, 0, 0, 0)

  const firstDay = new Date(year, month, 1).getDay()
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const prevMonthDays = new Date(year, month, 0).getDate()

  const byDay: Record<number, CalendarItem[]> = {}
  for (const item of items) {
    const d = parseDate(item.effectiveDeadline)
    if (d.getFullYear() === year && d.getMonth() === month) {
      const day = d.getDate()
      if (!byDay[day]) byDay[day] = []
      byDay[day].push(item)
    }
  }

  const cells: Array<{ day: number; inMonth: boolean }> = []
  for (let i = firstDay - 1; i >= 0; i--) cells.push({ day: prevMonthDays - i, inMonth: false })
  for (let d = 1; d <= daysInMonth; d++) cells.push({ day: d, inMonth: true })
  while (cells.length % 7 !== 0) {
    cells.push({ day: cells.length - daysInMonth - firstDay + 1, inMonth: false })
  }

  const rows: typeof cells[] = []
  for (let i = 0; i < cells.length; i += 7) rows.push(cells.slice(i, i + 7))

  return (
    <div>
      {/* Month navigation */}
      <div className="flex items-center justify-between mb-3">
        <button onClick={onPrev} className="p-1.5 rounded hover:bg-[#F3F4F6] dark:hover:bg-[#333333] text-[#374151] dark:text-[#D1D5DB]">
          <ChevronLeft className="h-4 w-4" />
        </button>
        <p className="text-[14px] font-[500] text-brand dark:text-[#EDEEF0]">
          {MONTH_NAMES[month]} {year}
        </p>
        <button onClick={onNext} className="p-1.5 rounded hover:bg-[#F3F4F6] dark:hover:bg-[#333333] text-[#374151] dark:text-[#D1D5DB]">
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>

      <div className="bg-white dark:bg-dark-card rounded-[8px] border border-surface-border dark:border-dark-border overflow-hidden">
        {/* Day headers */}
        <div className="grid grid-cols-7 border-b border-surface-border dark:border-dark-border">
          {DAY_NAMES.map((d) => (
            <div key={d} className="px-2 py-2 text-[11px] font-medium text-[#6B7280] text-center uppercase tracking-[0.05em]">
              {d}
            </div>
          ))}
        </div>

        {/* Rows */}
        {rows.map((row, ri) => (
          <div key={ri} className="grid grid-cols-7 border-b border-surface-border dark:border-dark-border last:border-0">
            {row.map((cell, ci) => {
              const cellDate = cell.inMonth ? new Date(year, month, cell.day) : null
              const isToday = cellDate?.getTime() === today.getTime()
              const engInDay = cell.inMonth ? (byDay[cell.day] ?? []) : []

              return (
                <div
                  key={ci}
                  className={[
                    'min-h-[72px] p-1.5 border-r border-surface-border dark:border-dark-border last:border-0 relative',
                    !cell.inMonth ? 'opacity-40' : '',
                  ].join(' ')}
                >
                  <span className={[
                    'text-[12px] font-medium inline-flex items-center justify-center w-6 h-6 rounded-full',
                    isToday ? 'bg-brand text-white' : 'text-[#374151] dark:text-[#D1D5DB]',
                  ].join(' ')}>
                    {cell.day}
                  </span>
                  {engInDay.length > 0 && (
                    <div className="mt-1 relative">
                      <button
                        onClick={() => setPopoverDay(popoverDay === cell.day ? null : cell.day)}
                        className="flex items-center justify-center bg-brand text-white text-[10px] font-medium rounded-full px-1.5 py-0.5 min-w-[20px]"
                      >
                        {engInDay.length}
                      </button>
                      {popoverDay === cell.day && (
                        <div className="absolute top-full mt-1 left-0 z-30 bg-white dark:bg-dark-card border border-[0.5px] border-surface-border dark:border-dark-border rounded-[8px] shadow-md max-h-[200px] overflow-y-auto min-w-[220px]">
                          {engInDay.map((eng) => (
                            <button
                              key={eng.engagementId}
                              onClick={(e) => { e.stopPropagation(); onRowClick(eng.engagementId) }}
                              className="w-full text-left px-3 py-2 hover:bg-[#F3F4F6] dark:hover:bg-[#333333] border-b border-[0.5px] border-[#E5E7EB] dark:border-dark-border last:border-0"
                            >
                              <p className="text-[12px] font-medium text-[#111827] dark:text-[#EDEEF0] truncate">{eng.engagementName}</p>
                              <p className="text-[11px] text-[#6B7280] truncate">{eng.clientName}</p>
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        ))}
      </div>
    </div>
  )
}

export default function CalendarPage() {
  const router = useRouter()
  const [view, setView] = useState<ViewMode>('list')
  const now = new Date()
  const [calMonth, setCalMonth] = useState(now.getMonth())
  const [calYear, setCalYear] = useState(now.getFullYear())

  const { data: items = [], isLoading, isError, refetch } = useQuery<CalendarItem[]>({
    queryKey: ['engagements-calendar'],
    queryFn: () => engagementsApi.getCalendar(180),
    staleTime: 5 * 60 * 1000,
  })

  function prevMonth() {
    if (calMonth === 0) { setCalMonth(11); setCalYear((y) => y - 1) }
    else setCalMonth((m) => m - 1)
  }
  function nextMonth() {
    if (calMonth === 11) { setCalMonth(0); setCalYear((y) => y + 1) }
    else setCalMonth((m) => m + 1)
  }

  return (
    <AppShell>
      <div className="flex flex-col p-6 gap-4">

        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-[24px] font-[500] text-brand dark:text-[#EDEEF0]">
              Deadline Calendar
            </h1>
          </div>
          {/* View toggle */}
          <div className="flex rounded-[6px] border border-surface-border dark:border-dark-border overflow-hidden">
            {(['list', 'month'] as const).map((v) => (
              <button
                key={v}
                onClick={() => setView(v)}
                className={[
                  'px-3 py-1.5 text-[12px] font-medium transition-colors',
                  view === v
                    ? 'bg-brand text-white'
                    : 'bg-white dark:bg-dark-card text-[#374151] dark:text-[#D1D5DB] hover:bg-[#F3F4F6] dark:hover:bg-[#2A2A2A]',
                ].join(' ')}
              >
                {v.charAt(0).toUpperCase() + v.slice(1)}
              </button>
            ))}
          </div>
        </div>

        {isLoading ? (
          <div className="flex flex-col gap-4">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i}>
                <div className="h-3 w-32 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded mb-2" />
                <div className="flex flex-col gap-1.5">
                  {Array.from({ length: 2 }).map((_, j) => (
                    <div key={j} className="h-14 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded-[8px]" />
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : isError ? (
          <div className="flex flex-col items-center justify-center py-24 gap-3">
            <p className="text-[13px] text-[#DC2626]">Failed to load calendar data.</p>
            <button
              onClick={() => refetch()}
              className="flex items-center gap-1.5 text-[13px] font-medium px-4 py-2 rounded-[6px] bg-brand text-white hover:opacity-90"
            >
              <RefreshCw className="h-4 w-4" /> Retry
            </button>
          </div>
        ) : view === 'list' ? (
          <ListView items={items} onRowClick={(id) => router.push(`/engagements/${id}`)} />
        ) : (
          <MonthView
            items={items}
            month={calMonth}
            year={calYear}
            onPrev={prevMonth}
            onNext={nextMonth}
            onRowClick={(id) => router.push(`/engagements/${id}`)}
          />
        )}

      </div>
    </AppShell>
  )
}
