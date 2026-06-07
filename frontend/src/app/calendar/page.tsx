// path: frontend/src/app/calendar/page.tsx
'use client'

import { useState, useCallback, useRef, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { AppShell } from '@/components/layout/AppShell'
import { engagementsApi } from '@/lib/api/engagements'
import { tasksApi } from '@/lib/api/tasks'
import { useAuth } from '@/lib/hooks/useAuth'
import api from '@/lib/api'
import { ChevronDown, ChevronLeft, ChevronRight, Pencil, Plus, X } from 'lucide-react'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type EventType = 'deadline' | 'extension' | 'task' | 'meeting' | 'holiday'

interface CalEvent {
  id: string
  title: string
  date: string // YYYY-MM-DD
  type: EventType
  assignedTo?: string | null
  description?: string
  engagementId?: string | null
  location?: string | null
}

interface MySettings {
  colors: Record<string, string>
  custom_categories: Array<{ name: string; color: string }>
}

interface StaffMember {
  id: string
  full_name: string | null
  email: string
  role: string
}

type ViewMode = 'month' | 'week' | 'agenda'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_COLORS: Record<string, string> = {
  deadline: '#EF4444',
  extension: '#F97316',
  task: '#3B82F6',
  meeting: '#22C55E',
  holiday: '#9CA3AF',
}

const STAFF_PALETTE = [
  '#6366F1', '#EC4899', '#14B8A6', '#F59E0B',
  '#8B5CF6', '#06B6D4', '#F43F5E', '#84CC16',
]

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
]
const DAY_NAMES = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

const TYPE_LABELS: Record<string, string> = {
  deadline: 'Deadlines',
  extension: 'Extensions',
  task: 'Tasks',
  meeting: 'Meetings',
  holiday: 'Holidays',
}

// ---------------------------------------------------------------------------
// US Federal Holidays for current year
// ---------------------------------------------------------------------------

function usHolidays(year: number): CalEvent[] {
  const fixed = [
    { month: 1, day: 1, name: "New Year's Day" },
    { month: 6, day: 19, name: 'Juneteenth' },
    { month: 7, day: 4, name: 'Independence Day' },
    { month: 11, day: 11, name: "Veterans Day" },
    { month: 12, day: 25, name: 'Christmas Day' },
  ]

  function nthWeekday(y: number, m: number, weekday: number, n: number): string {
    const d = new Date(y, m - 1, 1)
    let count = 0
    while (true) {
      if (d.getDay() === weekday) {
        count++
        if (count === n) break
      }
      d.setDate(d.getDate() + 1)
    }
    return `${y}-${String(m).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  }

  function lastWeekday(y: number, m: number, weekday: number): string {
    const d = new Date(y, m, 0)
    while (d.getDay() !== weekday) d.setDate(d.getDate() - 1)
    return `${y}-${String(m).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  }

  const computed = [
    { date: nthWeekday(year, 1, 1, 3), name: 'MLK Day' },
    { date: nthWeekday(year, 2, 1, 3), name: "Presidents' Day" },
    { date: lastWeekday(year, 5, 1), name: 'Memorial Day' },
    { date: nthWeekday(year, 9, 1, 1), name: 'Labor Day' },
    { date: nthWeekday(year, 10, 1, 2), name: 'Columbus Day' },
    { date: nthWeekday(year, 11, 4, 4), name: 'Thanksgiving' },
  ]

  const holidays: CalEvent[] = []

  for (const h of fixed) {
    const ds = `${year}-${String(h.month).padStart(2, '0')}-${String(h.day).padStart(2, '0')}`
    holidays.push({ id: `holiday-${ds}`, title: h.name, date: ds, type: 'holiday' })
  }

  for (const h of computed) {
    holidays.push({ id: `holiday-${h.date}`, title: h.name, date: h.date, type: 'holiday' })
  }

  return holidays
}

// ---------------------------------------------------------------------------
// Date helpers
// ---------------------------------------------------------------------------

function toDateStr(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function parseDate(s: string): Date {
  const [y, m, d] = s.split('-').map(Number)
  return new Date(y, m - 1, d)
}

function formatDate(s: string): string {
  return parseDate(s).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

// ---------------------------------------------------------------------------
// Color picker popover
// ---------------------------------------------------------------------------

interface ColorPickerProps {
  value: string
  onChange: (c: string) => void
  onClose: () => void
}

function ColorPicker({ value, onChange, onClose }: ColorPickerProps) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose()
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [onClose])

  return (
    <div ref={ref} className="absolute z-50 bg-surface-card border border-surface-border rounded shadow-lg p-2" style={{ top: '100%', left: 0 }}>
      <input
        type="color"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-10 h-10 cursor-pointer border-0 p-0 bg-transparent"
        autoFocus
      />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Event pill
// ---------------------------------------------------------------------------

interface PillProps {
  event: CalEvent
  borderColor: string
  fillColor: string
  isOwner: boolean
  isPersonalView: boolean
  onClick?: (e: React.MouseEvent) => void
}

function EventPill({ event, borderColor, fillColor, isOwner, isPersonalView, onClick }: PillProps) {
  const useFill = isOwner && !isPersonalView ? fillColor : 'transparent'
  return (
    <div
      title={event.title}
      className="rounded truncate cursor-pointer"
      style={{
        padding: '2px',
        backgroundColor: borderColor,
        maxWidth: '100%',
      }}
      onClick={onClick}
    >
      <div
        className="text-xs px-1 rounded-sm truncate"
        style={{
          backgroundColor: useFill !== 'transparent' ? useFill : 'var(--background)',
          color: 'inherit',
          lineHeight: '1.4',
        }}
      >
        {event.title}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Meeting URL extractor
// ---------------------------------------------------------------------------

function extractJoinUrl(description: string, location: string): string | null {
  const combined = `${description} ${location}`
  const patterns = [
    /https?:\/\/[^\s]*zoom\.us\/[^\s]*/i,
    /https?:\/\/meet\.google\.com\/[^\s]*/i,
    /https?:\/\/teams\.microsoft\.com\/[^\s]*/i,
    /https?:\/\/[^\s]*webex\.com\/[^\s]*/i,
    /https?:\/\/[^\s]*gotomeeting\.com\/[^\s]*/i,
  ]
  for (const pattern of patterns) {
    const match = combined.match(pattern)
    if (match) return match[0].replace(/[.,;)>]+$/, '')
  }
  return null
}

// ---------------------------------------------------------------------------
// Meeting popover
// ---------------------------------------------------------------------------

function MeetingPopover({ event, pos, onClose }: { event: CalEvent; pos: { x: number; y: number }; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose()
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [onClose])

  const joinUrl = extractJoinUrl(event.description ?? '', event.location ?? '')

  return (
    <div
      ref={ref}
      className="fixed z-50 bg-surface-card border border-surface-border rounded-[10px] shadow-lg p-4 w-72"
      style={{ top: pos.y, left: Math.min(pos.x, window.innerWidth - 300) }}
    >
      <div className="flex items-start justify-between gap-2 mb-3">
        <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0] leading-snug">{event.title}</p>
        <button onClick={onClose} className="text-[#6B7280] hover:text-brand flex-shrink-0"><X size={14} /></button>
      </div>
      <p className="text-[12px] text-[#6B7280] mb-1">{formatDate(event.date)}</p>
      {event.location && (
        <p className="text-[12px] text-[#6B7280] mb-1">{event.location}</p>
      )}
      {event.description && !joinUrl && (
        <p className="text-[12px] text-[#6B7280] line-clamp-3 mb-2">{event.description}</p>
      )}
      {joinUrl && (
        <a
          href={joinUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-2 flex items-center gap-2 h-8 px-3 rounded-[6px] bg-brand text-white text-[12px] font-medium hover:bg-brand/90 transition-colors w-full justify-center"
        >
          Join Meeting
        </a>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function CalendarPage() {
  const { user } = useAuth()
  const qc = useQueryClient()
  const isFirmOwner = user?.role === 'firm_owner'

  const today = new Date()
  const [view, setView] = useState<ViewMode>('month')
  const [cursor, setCursor] = useState(new Date(today.getFullYear(), today.getMonth(), 1))
  const [selectedStaff, setSelectedStaff] = useState<string[]>([])
  const [justMe, setJustMe] = useState(true)
  const [sidebarFilter, setSidebarFilter] = useState<EventType[]>(['deadline'])
  const [editingColor, setEditingColor] = useState<string | null>(null)
  const [addCatOpen, setAddCatOpen] = useState(false)
  const [newCatName, setNewCatName] = useState('')
  const [newCatColor, setNewCatColor] = useState('#3B82F6')
  const [expandedDay, setExpandedDay] = useState<string | null>(null)

  // Clicked event popover
  const [clickedEvent, setClickedEvent] = useState<CalEvent | null>(null)
  const [popoverPos, setPopoverPos] = useState<{ x: number; y: number }>({ x: 0, y: 0 })

  // Staff color picker
  const [editingStaffColor, setEditingStaffColor] = useState<string | null>(null)

  // Staff dropdown
  const [isDropdownOpen, setIsDropdownOpen] = useState(false)
  const [staffSearch, setStaffSearch] = useState('')
  const dropdownRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleMouseDown(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handleMouseDown)
    return () => document.removeEventListener('mousedown', handleMouseDown)
  }, [])

  const year = today.getFullYear()
  const holidays = usHolidays(year)

  // ---------------------------------------------------------------------------
  // Data fetching
  // ---------------------------------------------------------------------------

  const { data: calendarItems = [] } = useQuery({
    queryKey: ['engagements-calendar'],
    queryFn: () => engagementsApi.getCalendar(180),
  })

  const { data: tasksData } = useQuery({
    queryKey: ['tasks-calendar'],
    queryFn: () => tasksApi.list(0, 200),
  })

  const { data: externalData } = useQuery({
    queryKey: ['external-events'],
    queryFn: async () => {
      const { data } = await api.get('/api/v1/calendar/external-events')
      return data as { events: Array<{ id: string; title: string; start: string; end: string; description: string; location: string; type: string }>; provider: string | null }
    },
    retry: false,
  })

  const { data: mySettings } = useQuery({
    queryKey: ['my-calendar-settings'],
    queryFn: async () => {
      const { data } = await api.get('/api/v1/calendar/my-settings')
      return data as MySettings
    },
  })

  const { data: staffColors } = useQuery({
    queryKey: ['staff-colors'],
    queryFn: async () => {
      const { data } = await api.get('/api/v1/calendar/staff-colors')
      return data.colors as Record<string, string>
    },
    enabled: isFirmOwner,
  })

  const { data: staffList = [] } = useQuery({
    queryKey: ['staff-list'],
    queryFn: async () => {
      const { data } = await api.get('/users/', { params: { limit: 100, offset: 0 } })
      const items = Array.isArray(data) ? data : (data.items ?? [])
      return items.filter((u: StaffMember) => u.role !== 'client_portal_user') as StaffMember[]
    },
    enabled: isFirmOwner,
  })

  const patchSettings = useMutation({
    mutationFn: async (payload: { colors?: Record<string, string>; custom_categories?: Array<{ name: string; color: string }> }) => {
      const { data } = await api.patch('/api/v1/calendar/my-settings', payload)
      return data as MySettings
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['my-calendar-settings'] }),
  })

  const patchStaffColor = useMutation({
    mutationFn: async (payload: { user_id: string; color: string }) => {
      const { data } = await api.patch('/api/v1/calendar/staff-colors', payload)
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['staff-colors'] }),
  })

  // ---------------------------------------------------------------------------
  // Derived colors
  // ---------------------------------------------------------------------------

  const eventColors: Record<string, string> = { ...DEFAULT_COLORS, ...(mySettings?.colors ?? {}) }
  const customCategories = mySettings?.custom_categories ?? []

  function getStaffColor(userId: string, index: number): string {
    return (staffColors ?? {})[userId] ?? STAFF_PALETTE[index % STAFF_PALETTE.length]
  }

  // ---------------------------------------------------------------------------
  // Build unified event list
  // ---------------------------------------------------------------------------

  const today180 = new Date(today)
  today180.setDate(today180.getDate() + 180)

  const allEvents: CalEvent[] = []

  for (const item of calendarItems) {
    allEvents.push({
      id: `eng-${item.engagementId}`,
      title: item.engagementName,
      date: item.effectiveDeadline,
      type: item.deadlineType === 'extended' ? 'extension' : 'deadline',
      assignedTo: item.assignedTo ?? null,
      engagementId: item.engagementId,
    })
  }

  const taskItems = tasksData?.items ?? []
  for (const task of taskItems) {
    if (!task.dueDate) continue
    const d = parseDate(task.dueDate)
    if (d >= today && d <= today180) {
      allEvents.push({
        id: `task-${task.id}`,
        title: task.title,
        date: task.dueDate,
        type: 'task',
        assignedTo: task.assignedTo,
      })
    }
  }

  if (externalData?.events) {
    for (const ev of externalData.events) {
      const start = ev.start.includes('T') ? ev.start.split('T')[0] : ev.start
      allEvents.push({
        id: `ext-${ev.id}`,
        title: ev.title,
        date: start,
        type: 'meeting',
        description: ev.description,
        location: ev.location ?? null,
      })
    }
  }

  for (const h of holidays) allEvents.push(h)

  // Filtering by selected staff (firm owner aggregate view)
  function isEventVisible(ev: CalEvent): boolean {
    if (justMe || !isFirmOwner) return true
    if (!ev.assignedTo) return true
    return selectedStaff.includes(ev.assignedTo)
  }

  const visibleEvents = allEvents.filter(isEventVisible)

  // Group by date for easy lookup
  const byDate: Record<string, CalEvent[]> = {}
  for (const ev of visibleEvents) {
    if (!byDate[ev.date]) byDate[ev.date] = []
    byDate[ev.date].push(ev)
  }

  // ---------------------------------------------------------------------------
  // Staff index map
  // ---------------------------------------------------------------------------

  const filteredStaffList = staffList.filter((s) => s.id !== user?.id)
  const staffIndexMap: Record<string, number> = {}
  filteredStaffList.forEach((s, i) => { staffIndexMap[s.id] = i })

  // ---------------------------------------------------------------------------
  // Navigation
  // ---------------------------------------------------------------------------

  function prev() {
    if (view === 'month') setCursor(new Date(cursor.getFullYear(), cursor.getMonth() - 1, 1))
    else if (view === 'week') {
      const d = new Date(cursor)
      d.setDate(d.getDate() - 7)
      setCursor(d)
    }
  }

  function next() {
    if (view === 'month') setCursor(new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1))
    else if (view === 'week') {
      const d = new Date(cursor)
      d.setDate(d.getDate() + 7)
      setCursor(d)
    }
  }

  function cursorLabel(): string {
    if (view === 'month') return `${MONTH_NAMES[cursor.getMonth()]} ${cursor.getFullYear()}`
    if (view === 'week') {
      const sun = new Date(cursor)
      sun.setDate(sun.getDate() - sun.getDay())
      const sat = new Date(sun)
      sat.setDate(sat.getDate() + 6)
      return `${sun.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} - ${sat.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}`
    }
    return 'Agenda'
  }

  // ---------------------------------------------------------------------------
  // Event click handler
  // ---------------------------------------------------------------------------

  function handleEventClick(ev: CalEvent, e: React.MouseEvent) {
    e.stopPropagation()
    if (ev.type === 'deadline' || ev.type === 'extension') {
      if (ev.engagementId) {
        window.location.href = `/engagements/${ev.engagementId}`
      }
      return
    }
    if (ev.type === 'task') {
      if (ev.engagementId) {
        window.location.href = `/engagements/${ev.engagementId}`
      }
      return
    }
    if (ev.type === 'meeting') {
      const rect = (e.target as HTMLElement).getBoundingClientRect()
      setPopoverPos({ x: rect.left, y: rect.bottom + 8 })
      setClickedEvent(clickedEvent?.id === ev.id ? null : ev)
      return
    }
    // holidays: no action
  }

  // ---------------------------------------------------------------------------
  // Pill rendering helpers
  // ---------------------------------------------------------------------------

  function renderPills(events: CalEvent[], limit = 99) {
    return events.slice(0, limit).map((ev) => {
      const borderColor = eventColors[ev.type] ?? '#9CA3AF'
      const staffIdx = ev.assignedTo ? (staffIndexMap[ev.assignedTo] ?? 0) : 0
      const fillColor = ev.assignedTo ? getStaffColor(ev.assignedTo, staffIdx) : 'transparent'
      return (
        <EventPill
          key={ev.id}
          event={ev}
          borderColor={borderColor}
          fillColor={fillColor}
          isOwner={isFirmOwner}
          isPersonalView={justMe}
          onClick={(e) => handleEventClick(ev, e)}
        />
      )
    })
  }

  // ---------------------------------------------------------------------------
  // Month view
  // ---------------------------------------------------------------------------

  function MonthView() {
    const year = cursor.getFullYear()
    const month = cursor.getMonth()
    const firstDay = new Date(year, month, 1).getDay()
    const daysInMonth = new Date(year, month + 1, 0).getDate()
    const todayStr = toDateStr(today)

    const cells: (string | null)[] = Array(firstDay).fill(null)
    for (let d = 1; d <= daysInMonth; d++) {
      cells.push(`${year}-${String(month + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`)
    }
    while (cells.length % 7 !== 0) cells.push(null)

    return (
      <div className="flex-1 overflow-auto">
        <div className="grid grid-cols-7 border-b border-surface-border">
          {DAY_NAMES.map((d) => (
            <div key={d} className="text-center text-xs font-medium py-1 text-muted-foreground">{d}</div>
          ))}
        </div>
        <div className="grid grid-cols-7">
          {cells.map((ds, i) => {
            if (!ds) return <div key={i} className="min-h-[80px] border-b border-r border-surface-border/50 bg-surface-card/30" />
            const dayEvents = byDate[ds] ?? []
            const isToday = ds === todayStr
            const isExpanded = expandedDay === ds
            return (
              <div
                key={ds}
                className="min-h-[80px] border-b border-r border-surface-border/50 p-1 relative"
              >
                <div
                  className={`text-xs font-medium mb-1 w-5 h-5 flex items-center justify-center rounded-full ${isToday ? 'bg-primary text-primary-foreground' : 'text-foreground'}`}
                >
                  {parseDate(ds).getDate()}
                </div>
                <div className="flex flex-col gap-0.5">
                  {renderPills(dayEvents, 3)}
                  {dayEvents.length > 3 && (
                    <button
                      className="text-xs text-primary underline text-left"
                      onClick={() => setExpandedDay(isExpanded ? null : ds)}
                    >
                      +{dayEvents.length - 3} more
                    </button>
                  )}
                </div>
                {isExpanded && dayEvents.length > 3 && (
                  <div className="absolute top-0 left-0 z-40 bg-surface-card border border-surface-border rounded shadow-lg p-2 w-56">
                    <div className="flex justify-between items-center mb-1">
                      <span className="text-xs font-medium">{formatDate(ds)}</span>
                      <button onClick={() => setExpandedDay(null)}><X size={12} /></button>
                    </div>
                    <div className="flex flex-col gap-0.5">{renderPills(dayEvents)}</div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>
    )
  }

  // ---------------------------------------------------------------------------
  // Week view
  // ---------------------------------------------------------------------------

  function WeekView() {
    const sun = new Date(cursor)
    sun.setDate(sun.getDate() - sun.getDay())
    const days: string[] = []
    for (let i = 0; i < 7; i++) {
      const d = new Date(sun)
      d.setDate(d.getDate() + i)
      days.push(toDateStr(d))
    }
    const todayStr = toDateStr(today)

    return (
      <div className="flex-1 overflow-auto">
        <div className="grid grid-cols-7 border-b border-surface-border">
          {days.map((ds) => {
            const d = parseDate(ds)
            const isToday = ds === todayStr
            return (
              <div key={ds} className="text-center py-2 border-r border-surface-border/50 last:border-r-0">
                <div className="text-xs text-muted-foreground">{DAY_NAMES[d.getDay()]}</div>
                <div className={`text-sm font-medium mx-auto w-7 h-7 flex items-center justify-center rounded-full ${isToday ? 'bg-primary text-primary-foreground' : ''}`}>
                  {d.getDate()}
                </div>
              </div>
            )
          })}
        </div>
        <div className="grid grid-cols-7 min-h-[400px]">
          {days.map((ds) => {
            const dayEvents = byDate[ds] ?? []
            return (
              <div key={ds} className="border-r border-surface-border/50 last:border-r-0 p-1 flex flex-col gap-0.5">
                {renderPills(dayEvents)}
              </div>
            )
          })}
        </div>
      </div>
    )
  }

  // ---------------------------------------------------------------------------
  // Agenda view
  // ---------------------------------------------------------------------------

  function AgendaView() {
    const sorted = [...visibleEvents].sort((a, b) => a.date.localeCompare(b.date))
    const grouped: Record<string, CalEvent[]> = {}
    for (const ev of sorted) {
      if (!grouped[ev.date]) grouped[ev.date] = []
      grouped[ev.date].push(ev)
    }
    const dates = Object.keys(grouped).sort()

    if (dates.length === 0) {
      return <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">No upcoming events.</div>
    }

    return (
      <div className="flex-1 overflow-auto px-4 py-2">
        {dates.map((ds) => (
          <div key={ds} className="mb-4">
            <div className="text-xs font-semibold text-muted-foreground uppercase mb-1">{formatDate(ds)}</div>
            <div className="flex flex-col gap-1">
              {grouped[ds].map((ev) => {
                const color = eventColors[ev.type] ?? '#9CA3AF'
                return (
                  <div key={ev.id} className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
                    <span className="text-sm">{ev.title}</span>
                  </div>
                )
              })}
            </div>
          </div>
        ))}
      </div>
    )
  }

  // ---------------------------------------------------------------------------
  // Color key handlers
  // ---------------------------------------------------------------------------

  const handleColorChange = useCallback((typeKey: string, color: string) => {
    const currentColors = mySettings?.colors ?? {}
    patchSettings.mutate({ colors: { ...currentColors, [typeKey]: color } })
  }, [mySettings, patchSettings])

  const handleDeleteCustomCategory = useCallback((name: string) => {
    const updated = (mySettings?.custom_categories ?? []).filter((c) => c.name !== name)
    patchSettings.mutate({ custom_categories: updated })
  }, [mySettings, patchSettings])

  const handleAddCategory = useCallback(() => {
    if (!newCatName.trim()) return
    const updated = [...(mySettings?.custom_categories ?? []), { name: newCatName.trim(), color: newCatColor }]
    patchSettings.mutate({ custom_categories: updated })
    setNewCatName('')
    setNewCatColor('#3B82F6')
    setAddCatOpen(false)
  }, [newCatName, newCatColor, mySettings, patchSettings])

  // ---------------------------------------------------------------------------
  // Staff filter
  // ---------------------------------------------------------------------------

  function toggleStaff(id: string) {
    setJustMe(false)
    setSelectedStaff((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id])
  }

  function resetToJustMe() {
    setJustMe(true)
    setSelectedStaff([])
  }

  // ---------------------------------------------------------------------------
  // Sidebar upcoming list
  // ---------------------------------------------------------------------------

  const upcomingEvents = [...visibleEvents]
    .filter((ev) => sidebarFilter.includes(ev.type))
    .sort((a, b) => a.date.localeCompare(b.date))
    .slice(0, 50)

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  const allDefaultTypes: EventType[] = ['deadline', 'extension', 'task', 'meeting', 'holiday']

  return (
    <AppShell>
      <div className="flex h-full overflow-hidden">
        {/* MAIN AREA */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Toolbar */}
          <div className="flex items-center justify-between px-4 py-2 border-b border-surface-border flex-shrink-0">
            <div className="flex items-center gap-2">
              <button onClick={prev} className="p-1 rounded hover:bg-surface-card"><ChevronLeft size={16} /></button>
              <span className="text-sm font-medium min-w-[160px] text-center">{cursorLabel()}</span>
              <button onClick={next} className="p-1 rounded hover:bg-surface-card"><ChevronRight size={16} /></button>
              <button
                onClick={() => { setCursor(new Date(today.getFullYear(), today.getMonth(), 1)) }}
                className="text-xs px-2 py-0.5 border border-surface-border rounded hover:bg-surface-card ml-1"
              >
                Today
              </button>
            </div>
            {isFirmOwner && (
              <div ref={dropdownRef} className="relative">
                <button
                  onClick={() => setIsDropdownOpen((o) => !o)}
                  className="flex items-center gap-1 text-xs px-2 py-1 rounded border border-surface-border hover:bg-surface-card"
                >
                  {justMe ? 'Just me' : `${selectedStaff.length} staff selected`}
                  <ChevronDown size={12} />
                </button>
                {isDropdownOpen && (
                  <div
                    className="absolute top-full mt-1 left-0 z-50 bg-surface-card border border-surface-border rounded shadow-lg overflow-y-auto"
                    style={{ width: '220px', maxHeight: '300px' }}
                  >
                    <div className="p-2 border-b border-surface-border">
                      <input
                        type="text"
                        placeholder="Search staff..."
                        value={staffSearch}
                        onChange={(e) => setStaffSearch(e.target.value)}
                        className="w-full text-xs border border-surface-border rounded px-2 py-1 bg-transparent"
                      />
                    </div>
                    <div className="py-1">
                      <button
                        onClick={() => { resetToJustMe(); setIsDropdownOpen(false) }}
                        className="w-full flex items-center gap-2 px-3 py-1.5 text-xs hover:bg-surface-card/80 text-left"
                      >
                        <span className="w-4 text-primary">{justMe ? '✓' : ''}</span>
                        Just me
                      </button>
                      <button
                        onClick={() => { setJustMe(false); setSelectedStaff(filteredStaffList.map((s) => s.id)) }}
                        className="w-full flex items-center gap-2 px-3 py-1.5 text-xs hover:bg-surface-card/80 text-left"
                      >
                        <span className="w-4" />
                        Select all
                      </button>
                      <div className="border-t border-surface-border my-1" />
                      {filteredStaffList
                        .filter((s) => {
                          const q = staffSearch.toLowerCase()
                          return !q || (s.full_name ?? '').toLowerCase().includes(q) || s.email.toLowerCase().includes(q)
                        })
                        .map((s) => {
                          const staffIdx = staffIndexMap[s.id] ?? 0
                          const color = getStaffColor(s.id, staffIdx)
                          const isSelected = selectedStaff.includes(s.id)
                          const isEditingThis = editingStaffColor === s.id
                          return (
                            <div key={s.id} className="flex items-center gap-2 px-3 py-1.5 hover:bg-surface-card/80 relative">
                              <div
                                className="w-3 h-3 rounded-full cursor-pointer border border-white/30 flex-shrink-0"
                                style={{ backgroundColor: color }}
                                onClick={(e) => { e.stopPropagation(); setEditingStaffColor(isEditingThis ? null : s.id) }}
                              />
                              {isEditingThis && (
                                <ColorPicker
                                  value={color}
                                  onChange={(c) => patchStaffColor.mutate({ user_id: s.id, color: c })}
                                  onClose={() => setEditingStaffColor(null)}
                                />
                              )}
                              <button
                                onClick={() => { toggleStaff(s.id) }}
                                className="flex-1 flex items-center justify-between text-xs text-left"
                              >
                                <span className="truncate">{s.full_name ?? s.email}</span>
                                {isSelected && <span className="text-primary flex-shrink-0">✓</span>}
                              </button>
                            </div>
                          )
                        })}
                    </div>
                  </div>
                )}
              </div>
            )}
            <div className="flex items-center gap-1">
              {(['month', 'week', 'agenda'] as ViewMode[]).map((v) => (
                <button
                  key={v}
                  onClick={() => setView(v)}
                  className={`text-xs px-2 py-1 rounded capitalize transition-colors ${
                    view === v ? 'bg-primary text-primary-foreground' : 'hover:bg-surface-card border border-surface-border'
                  }`}
                >
                  {v}
                </button>
              ))}
            </div>
          </div>

          {/* Calendar view */}
          <div className="flex-1 overflow-hidden flex flex-col" onClick={() => setClickedEvent(null)}>
            {view === 'month' && <MonthView />}
            {view === 'week' && <WeekView />}
            {view === 'agenda' && <AgendaView />}
          </div>
        </div>

        {/* RIGHT SIDEBAR */}
        <aside className="w-60 flex-shrink-0 flex flex-col bg-surface-card border-l border-surface-border overflow-hidden">
          {/* Upcoming events */}
          <div className="flex-1 overflow-y-auto p-3">
            <div className="text-[13px] font-medium mb-2">Upcoming</div>
            {/* Filter pills */}
            <div className="flex flex-wrap gap-1 mb-3">
              {allDefaultTypes.map((t) => (
                <button
                  key={t}
                  onClick={() =>
                    setSidebarFilter((prev) =>
                      prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t]
                    )
                  }
                  className={`text-[11px] px-2 py-0.5 rounded-full border transition-colors ${
                    sidebarFilter.includes(t)
                      ? 'border-transparent text-white'
                      : 'border-surface-border text-muted-foreground'
                  }`}
                  style={sidebarFilter.includes(t) ? { backgroundColor: eventColors[t] } : undefined}
                >
                  {TYPE_LABELS[t]}
                </button>
              ))}
            </div>
            {/* List */}
            <div className="flex flex-col gap-1.5">
              {upcomingEvents.map((ev) => (
                <div key={ev.id} className="flex items-start gap-1.5">
                  <div
                    className="w-2 h-2 rounded-full mt-1 flex-shrink-0"
                    style={{ backgroundColor: eventColors[ev.type] ?? '#9CA3AF' }}
                  />
                  <div className="min-w-0">
                    <div className="text-[12px] truncate">{ev.title}</div>
                    <div className="text-[11px] text-muted-foreground">{formatDate(ev.date)}</div>
                  </div>
                </div>
              ))}
              {upcomingEvents.length === 0 && (
                <div className="text-[11px] text-muted-foreground">No events matching filter.</div>
              )}
            </div>
          </div>

          {/* Color key */}
          <div className="border-t border-surface-border p-3">
            <div className="text-[11px] uppercase font-medium text-muted-foreground mb-2 tracking-wide">Color Key</div>
            <div className="flex flex-col gap-1.5">
              {allDefaultTypes.map((t) => {
                const color = eventColors[t]
                const isEditing = editingColor === t
                return (
                  <div key={t} className="flex items-center gap-2 relative">
                    <div
                      className="w-3 h-3 rounded-sm cursor-pointer flex-shrink-0"
                      style={{ backgroundColor: color }}
                      onClick={() => setEditingColor(isEditing ? null : t)}
                    />
                    <span className="text-[12px] flex-1">{TYPE_LABELS[t]}</span>
                    <button onClick={() => setEditingColor(isEditing ? null : t)} className="opacity-40 hover:opacity-100">
                      <Pencil size={10} />
                    </button>
                    {isEditing && (
                      <ColorPicker
                        value={color}
                        onChange={(c) => { handleColorChange(t, c) }}
                        onClose={() => setEditingColor(null)}
                      />
                    )}
                  </div>
                )
              })}
              {/* Custom categories */}
              {customCategories.map((cat) => {
                const catKey = `custom-${cat.name}`
                const isEditing = editingColor === catKey
                return (
                  <div key={catKey} className="flex items-center gap-2 relative">
                    <div
                      className="w-3 h-3 rounded-sm cursor-pointer flex-shrink-0"
                      style={{ backgroundColor: cat.color }}
                      onClick={() => setEditingColor(isEditing ? null : catKey)}
                    />
                    <span className="text-[12px] flex-1 truncate">{cat.name}</span>
                    <button
                      onClick={() => handleDeleteCustomCategory(cat.name)}
                      className="opacity-40 hover:opacity-100"
                    >
                      <X size={10} />
                    </button>
                    {isEditing && (
                      <ColorPicker
                        value={cat.color}
                        onChange={(c) => {
                          const updated = customCategories.map((x) => x.name === cat.name ? { ...x, color: c } : x)
                          patchSettings.mutate({ custom_categories: updated })
                        }}
                        onClose={() => setEditingColor(null)}
                      />
                    )}
                  </div>
                )
              })}
            </div>

            {/* Add category */}
            {addCatOpen ? (
              <div className="mt-2 flex flex-col gap-1">
                <input
                  className="text-[12px] border border-surface-border rounded px-1.5 py-0.5 bg-transparent"
                  placeholder="Category name"
                  value={newCatName}
                  onChange={(e) => setNewCatName(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleAddCategory()}
                  autoFocus
                />
                <div className="flex items-center gap-1">
                  <input
                    type="color"
                    value={newCatColor}
                    onChange={(e) => setNewCatColor(e.target.value)}
                    className="w-6 h-6 border-0 p-0 bg-transparent cursor-pointer"
                  />
                  <button
                    onClick={handleAddCategory}
                    className="text-[11px] text-primary underline"
                  >
                    Add
                  </button>
                  <button
                    onClick={() => { setAddCatOpen(false); setNewCatName('') }}
                    className="text-[11px] text-muted-foreground underline"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <button
                onClick={() => setAddCatOpen(true)}
                className="mt-2 flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground"
              >
                <Plus size={10} /> Add category
              </button>
            )}
          </div>
        </aside>
      </div>
      {clickedEvent && clickedEvent.type === 'meeting' && (
        <MeetingPopover
          event={clickedEvent}
          pos={popoverPos}
          onClose={() => setClickedEvent(null)}
        />
      )}
    </AppShell>
  )
}
