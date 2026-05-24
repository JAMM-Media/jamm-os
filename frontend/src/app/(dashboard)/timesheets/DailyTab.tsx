// frontend/src/app/(dashboard)/timesheets/DailyTab.tsx
'use client'

import { useState, useEffect, useRef } from 'react'
import { toast } from 'sonner'
import { Pencil, Trash2, AlertTriangle, Check, ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'
import api from '@/lib/api'

export interface DailyTabProps {
  selectedUserId: string | null
  currentUserId: string
  userRole: string
  billableFilter?: string
}

const ACTIVITY_TYPES = [
  'Tax Preparation',
  'Client Meeting',
  'Document Review',
  'Review & Sign-off',
  'Client Communication',
  'Research',
  'Admin',
  'Other',
]

function roundToNearest15(date: Date): string {
  const minutes = Math.round(date.getMinutes() / 15) * 15
  const d = new Date(date)
  d.setMinutes(minutes % 60)
  if (minutes === 60) d.setHours(d.getHours() + 1)
  return d.toTimeString().slice(0, 5)
}

function toDateString(d: Date): string {
  return d.toISOString().slice(0, 10)
}

function formatDateLabel(iso: string): string {
  const d = new Date(iso + 'T00:00:00')
  return d.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })
}

function calcDuration(start: string, end: string): string | null {
  if (!start || !end) return null
  const [sh, sm] = start.split(':').map(Number)
  const [eh, em] = end.split(':').map(Number)
  const totalMin = eh * 60 + em - (sh * 60 + sm)
  if (totalMin <= 0) return null
  const h = Math.floor(totalMin / 60)
  const m = totalMin % 60
  return h > 0 ? `${h}h ${m}m` : `${m}m`
}

function timeDiffHours(start: string, end: string): number {
  const [sh, sm] = start.split(':').map(Number)
  const [eh, em] = end.split(':').map(Number)
  const totalMin = eh * 60 + em - (sh * 60 + sm)
  return Math.max(0, Math.round((totalMin / 60) * 4) / 4)
}

interface Engagement {
  id: string
  name: string
  client_id: string
  client_name?: string
  assigned_staff_id?: string
}

interface Task {
  id: string
  title: string
  assigned_to?: string
}

interface TimeEntry {
  id: string
  engagement_id: string
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

interface EntryForm {
  engagementId: string
  taskId: string
  activityType: string
  customActivity: string
  startTime: string
  endTime: string
  hours: string
  isBillable: boolean
  notes: string
  hoursAutoFilled: boolean
}

const EMPTY_FORM: EntryForm = {
  engagementId: '',
  taskId: '',
  activityType: '',
  customActivity: '',
  startTime: '',
  endTime: '',
  hours: '',
  isBillable: true,
  notes: '',
  hoursAutoFilled: false,
}

export default function DailyTab({ selectedUserId, currentUserId, userRole, billableFilter = 'all' }: DailyTabProps) {
  const today = toDateString(new Date())
  const isManagerOrAbove = userRole === 'firm_owner' || userRole === 'manager'
  const effectiveUserId = selectedUserId ?? currentUserId

  const [engagements, setEngagements] = useState<Engagement[]>([])
  const [clients, setClients] = useState<Record<string, string>>({})
  const [tasks, setTasks] = useState<Task[]>([])
  const [entries, setEntries] = useState<TimeEntry[]>([])
  const [approvalRequired, setApprovalRequired] = useState(false)
  const [loadingEntries, setLoadingEntries] = useState(true)

  const [form, setForm] = useState<EntryForm>({ ...EMPTY_FORM, startTime: roundToNearest15(new Date()) })
  const [engSearch, setEngSearch] = useState('')
  const [engDropOpen, setEngDropOpen] = useState(false)
  const [taskOpen, setTaskOpen] = useState(false)
  const [taskHint, setTaskHint] = useState(false)
  const [taskSearch, setTaskSearch] = useState('')
  const [actOpen, setActOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [submittingDay, setSubmittingDay] = useState(false)
  const [endTimeError, setEndTimeError] = useState('')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editForm, setEditForm] = useState<Record<string, unknown>>({})
  const [showSubmittedEditModal, setShowSubmittedEditModal] = useState<string | null>(null)
  const [editNote, setEditNote] = useState('')
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null)
  const [duplicateWarning, setDuplicateWarning] = useState(false)
  const [pendingPayload, setPendingPayload] = useState<Record<string, unknown> | null>(null)
  const engDropRef = useRef<HTMLDivElement>(null)
  const taskRef = useRef<HTMLDivElement>(null)
  const actRef = useRef<HTMLDivElement>(null)

  // Load engagements, clients, settings, entries
  useEffect(() => {
    api.get('/engagements/', { params: { limit: 100 } }).then((r) => {
      const raw = r.data
      const items = Array.isArray(raw) ? raw : (raw?.items ?? raw?.engagements ?? [])
      setEngagements(items)
    }).catch(() => {})

    api.get('/api/v1/clients/?limit=100').then((r) => {
      const map: Record<string, string> = {}
      for (const c of r.data?.items ?? []) map[c.id] = c.name
      setClients(map)
    }).catch(() => {})

    if (isManagerOrAbove) {
      api.get('/api/v1/time-entries/settings').then((r) => {
        setApprovalRequired(r.data?.approval_required ?? false)
      }).catch(() => {})
    }
  }, [isManagerOrAbove])

  useEffect(() => {
    loadEntries()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [effectiveUserId])

  function loadEntries() {
    setLoadingEntries(true)
    const params = new URLSearchParams({ date: today, limit: '100' })
    if (effectiveUserId !== currentUserId) params.set('user_id', effectiveUserId)
    api
      .get(`/api/v1/time-entries/?${params}`)
      .then((r) => {
        setEntries(r.data?.items ?? [])
      })
      .catch(() => {})
      .finally(() => setLoadingEntries(false))
  }

  // Load tasks when engagement changes
  useEffect(() => {
    if (!form.engagementId) { setTasks([]); setTaskSearch(''); setTaskOpen(false); return }
    api
      .get('/tasks/', { params: { engagement_id: form.engagementId, limit: 100 } })
      .then((r) => {
        const raw = r.data
        const items = Array.isArray(raw) ? raw : (raw?.items ?? raw?.tasks ?? [])
        setTasks(items)
      })
      .catch(() => setTasks([]))
  }, [form.engagementId])

  // Auto-calculate hours from start/end
  useEffect(() => {
    if (form.startTime && form.endTime) {
      const dur = calcDuration(form.startTime, form.endTime)
      if (!dur) {
        setEndTimeError('End time must be after start time')
      } else {
        setEndTimeError('')
        if (form.hoursAutoFilled || !form.hours) {
          const h = timeDiffHours(form.startTime, form.endTime)
          setForm((f) => ({ ...f, hours: String(h), hoursAutoFilled: true }))
        }
      }
    } else {
      setEndTimeError('')
    }
  }, [form.startTime, form.endTime, form.hoursAutoFilled, form.hours])

  // Close eng dropdown on outside click
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (engDropRef.current && !engDropRef.current.contains(e.target as Node)) {
        setEngDropOpen(false)
      }
    }
    if (engDropOpen) {
      document.addEventListener('mousedown', handler)
      return () => document.removeEventListener('mousedown', handler)
    }
  }, [engDropOpen])

  // Close task dropdown on outside click
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (taskRef.current && !taskRef.current.contains(e.target as Node)) {
        setTaskOpen(false)
      }
    }
    if (taskOpen) {
      document.addEventListener('mousedown', handler)
      return () => document.removeEventListener('mousedown', handler)
    }
  }, [taskOpen])

  // Close activity dropdown on outside click
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (actRef.current && !actRef.current.contains(e.target as Node)) {
        setActOpen(false)
      }
    }
    if (actOpen) {
      document.addEventListener('mousedown', handler)
      return () => document.removeEventListener('mousedown', handler)
    }
  }, [actOpen])

  function getEngLabel(eng: Engagement) {
    return `${eng.name}${clients[eng.client_id] ? ` — ${clients[eng.client_id]}` : ''}`
  }

  function filteredEngagements(): Engagement[] {
    const q = engSearch.toLowerCase()
    return engagements.filter((e) => getEngLabel(e).toLowerCase().includes(q))
  }

  function assignedEngs() {
    return filteredEngagements().filter((e) => e.assigned_staff_id === currentUserId)
  }
  function otherEngs() {
    return filteredEngagements().filter((e) => e.assigned_staff_id !== currentUserId)
  }

  function selectEngagement(id: string) {
    setForm((f) => ({ ...f, engagementId: id, taskId: '' }))
    const eng = engagements.find((e) => e.id === id)
    if (eng) setEngSearch(getEngLabel(eng))
    setEngDropOpen(false)
    setTaskSearch('')
    setTaskOpen(false)
  }

  function checkDuplicate(payload: Record<string, unknown>): boolean {
    const pending = entries.filter((e) => !e.is_submitted)
    return pending.some(
      (e) =>
        e.engagement_id === payload.engagement_id &&
        e.activity_type === payload.activity_type &&
        e.date === today
    )
  }

  async function submitEntry(payload: Record<string, unknown>) {
    setSubmitting(true)
    try {
      await api.post('/api/v1/time-entries/', payload)
      const engId = form.engagementId
      const actType = form.activityType === 'Other' ? form.customActivity : form.activityType
      setForm({ ...EMPTY_FORM, engagementId: engId, activityType: actType, startTime: roundToNearest15(new Date()), hoursAutoFilled: false })
      const eng = engagements.find((e) => e.id === engId)
      if (eng) setEngSearch(getEngLabel(eng))
      setDuplicateWarning(false)
      setPendingPayload(null)
      loadEntries()
      toast.success('Entry added')
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(detail ?? 'Failed to add entry')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleAddEntry(e: React.FormEvent) {
    e.preventDefault()
    if (!form.engagementId) { toast.error('Engagement is required'); return }
    if (!form.activityType) { toast.error('Activity type is required'); return }
    if (!form.hours || parseFloat(form.hours) <= 0) { toast.error('Hours is required'); return }
    if (endTimeError) return

    const eng = engagements.find((en) => en.id === form.engagementId)
    const hourlyRate = 0

    const payload: Record<string, unknown> = {
      engagement_id: form.engagementId,
      description: form.notes || (form.activityType === 'Other' ? form.customActivity : form.activityType),
      hours: parseFloat(form.hours),
      hourly_rate: eng ? hourlyRate : 0,
      is_billable: form.isBillable,
      date: today,
      start_time: form.startTime || null,
      end_time: form.endTime || null,
      activity_type: form.activityType === 'Other' ? form.customActivity : form.activityType,
    }

    if (checkDuplicate(payload)) {
      setDuplicateWarning(true)
      setPendingPayload(payload)
      return
    }

    await submitEntry(payload)
  }

  async function handleSubmitDay() {
    setSubmittingDay(true)
    try {
      await api.post('/api/v1/time-entries/submit-day', { date: today })
      toast.success('Day submitted')
      loadEntries()
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(detail ?? 'Failed to submit day')
    } finally {
      setSubmittingDay(false)
    }
  }

  async function handleDeleteEntry(id: string) {
    try {
      await api.delete(`/api/v1/time-entries/${id}`)
      setDeleteConfirmId(null)
      loadEntries()
      toast.success('Entry deleted')
    } catch {
      toast.error('Failed to delete entry')
    }
  }

  async function handleEditSubmit(id: string) {
    try {
      await api.patch(`/api/v1/time-entries/${id}`, editForm)
      setEditingId(null)
      loadEntries()
      toast.success('Entry updated')
    } catch {
      toast.error('Failed to update entry')
    }
  }

  async function handleSubmittedEdit(id: string) {
    try {
      await api.patch(`/api/v1/time-entries/${id}/submitted-edit`, {
        ...editForm,
        edit_note: editNote || undefined,
      })
      setShowSubmittedEditModal(null)
      setEditNote('')
      setEditForm({})
      loadEntries()
      toast.success('Entry updated')
    } catch {
      toast.error('Failed to update entry')
    }
  }

  const pending = entries.filter((e) => !e.is_submitted).filter((e) => {
    if (billableFilter === 'billable') return e.is_billable === true
    if (billableFilter === 'non_billable') return e.is_billable === false
    return true
  })
  const submitted = entries.filter((e) => e.is_submitted).filter((e) => {
    if (billableFilter === 'billable') return e.is_billable === true
    if (billableFilter === 'non_billable') return e.is_billable === false
    return true
  })

  const totalHours = pending.reduce((s, e) => s + Number(e.hours), 0)
  const billableValue = pending
    .filter((e) => e.is_billable)
    .reduce((s, e) => s + Number(e.hours) * Number(e.hourly_rate), 0)

  const inputClass =
    'w-full rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[13px] text-brand dark:text-[#EDEEF0] px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-brand'
  const labelClass = 'text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em]'

  return (
    <div className="flex flex-col gap-4">
      {/* Entry form */}
      <div className="bg-surface-card dark:bg-dark-card rounded-[8px] p-4 mb-4 flex flex-col gap-4">
        <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">
          Log time for {formatDateLabel(today)}
        </p>

        <form onSubmit={handleAddEntry} className="flex flex-col gap-3">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {/* Engagement */}
            <div className="flex flex-col gap-1.5 md:col-span-2" ref={engDropRef}>
              <label className={labelClass}>Engagement *</label>
              <div className="relative">
                <input
                  type="text"
                  value={engSearch}
                  onChange={(e) => {
                    setEngSearch(e.target.value)
                    setEngDropOpen(true)
                    if (!e.target.value) setForm((f) => ({ ...f, engagementId: '' }))
                  }}
                  onFocus={() => setEngDropOpen(true)}
                  placeholder="Search engagements..."
                  className={inputClass}
                />
                {engDropOpen && (
                  <div className="absolute z-50 top-full mt-1 w-full bg-white dark:bg-dark-card border border-surface-border dark:border-dark-border rounded-[6px] shadow-lg max-h-56 overflow-y-auto">
                    {assignedEngs().length > 0 && (
                      <>
                        {assignedEngs().map((eng) => (
                          <button
                            key={eng.id}
                            type="button"
                            onMouseDown={() => selectEngagement(eng.id)}
                            className="w-full text-left px-3 py-2 text-[13px] hover:bg-[#F3F4F6] dark:hover:bg-[#2A2A2A]"
                          >
                            {getEngLabel(eng)}
                          </button>
                        ))}
                        {otherEngs().length > 0 && (
                          <div className="px-3 py-1 text-[11px] text-[#9CA3AF] border-t border-surface-border dark:border-dark-border">
                            — Other engagements —
                          </div>
                        )}
                      </>
                    )}
                    {otherEngs().map((eng) => (
                      <button
                        key={eng.id}
                        type="button"
                        onMouseDown={() => selectEngagement(eng.id)}
                        className="w-full text-left px-3 py-2 text-[13px] hover:bg-[#F3F4F6] dark:hover:bg-[#2A2A2A]"
                      >
                        {getEngLabel(eng)}
                      </button>
                    ))}
                    {filteredEngagements().length === 0 && (
                      <div className="px-3 py-2 text-[13px] text-[#9CA3AF]">No active engagements found</div>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Task */}
            <div className="flex flex-col gap-1.5" ref={taskRef}>
              <label className={labelClass}>Task</label>
              <div className="relative">
                <button
                  type="button"
                  onClick={() => {
                    if (!form.engagementId) {
                      setTaskHint(true)
                      setTimeout(() => setTaskHint(false), 3000)
                    } else {
                      setTaskHint(false)
                      setTaskOpen((o) => !o)
                    }
                  }}
                  className={cn(inputClass, 'text-left flex items-center justify-between cursor-pointer')}
                >
                  <span className={form.taskId ? '' : 'text-[#9CA3AF]'}>
                    {form.taskId
                      ? (tasks.find((t) => t.id === form.taskId)?.title ?? 'Select task (optional)')
                      : (form.engagementId ? 'Select task (optional)' : 'Select an engagement first')}
                  </span>
                  <ChevronDown className="h-3.5 w-3.5 text-[#9CA3AF] flex-shrink-0 ml-2" />
                </button>
                {taskHint && (
                  <p className="text-[11px] text-[#F59E0B] mt-1">
                    Please select an engagement first
                  </p>
                )}
                {taskOpen && form.engagementId && (
                  <div className="absolute z-50 top-full mt-1 w-full bg-white dark:bg-dark-card border border-surface-border dark:border-dark-border rounded-[6px] shadow-lg">
                    <div className="p-2 border-b border-surface-border dark:border-dark-border">
                      <input
                        type="text"
                        value={taskSearch}
                        onChange={(e) => setTaskSearch(e.target.value)}
                        placeholder="Search tasks..."
                        className={inputClass}
                        autoFocus
                      />
                    </div>
                    <div className="max-h-48 overflow-y-auto">
                      {tasks
                        .filter((t) => t.assigned_to === currentUserId)
                        .filter((t) => !taskSearch || t.title.toLowerCase().includes(taskSearch.toLowerCase()))
                        .map((t) => (
                          <button
                            key={t.id}
                            type="button"
                            onMouseDown={() => { setForm((f) => ({ ...f, taskId: t.id })); setTaskOpen(false); setTaskSearch('') }}
                            className="w-full text-left px-3 py-2 text-[13px] hover:bg-[#F3F4F6] dark:hover:bg-[#2A2A2A]"
                          >
                            {t.title}
                          </button>
                        ))}
                      {tasks
                        .filter((t) => t.assigned_to !== currentUserId)
                        .filter((t) => !taskSearch || t.title.toLowerCase().includes(taskSearch.toLowerCase()))
                        .map((t) => (
                          <button
                            key={t.id}
                            type="button"
                            onMouseDown={() => { setForm((f) => ({ ...f, taskId: t.id })); setTaskOpen(false); setTaskSearch('') }}
                            className="w-full text-left px-3 py-2 text-[13px] hover:bg-[#F3F4F6] dark:hover:bg-[#2A2A2A]"
                          >
                            {t.title}
                          </button>
                        ))}
                      {tasks.filter((t) => !taskSearch || t.title.toLowerCase().includes(taskSearch.toLowerCase())).length === 0 && (
                        <div className="px-3 py-2 text-[13px] text-[#9CA3AF]">
                          {tasks.length === 0 ? 'No tasks found for this engagement' : 'No matching tasks'}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Activity type */}
            <div className="flex flex-col gap-1.5" ref={actRef}>
              <label className={labelClass}>Activity Type *</label>
              <div className="relative">
                <button
                  type="button"
                  onClick={() => setActOpen((o) => !o)}
                  className={cn(inputClass, 'text-left flex items-center justify-between cursor-pointer')}
                >
                  <span className={form.activityType ? '' : 'text-[#9CA3AF]'}>
                    {form.activityType || 'Select activity...'}
                  </span>
                  <ChevronDown className="h-3.5 w-3.5 text-[#9CA3AF] flex-shrink-0 ml-2" />
                </button>
                {actOpen && (
                  <div className="absolute z-50 top-full mt-1 w-full bg-white dark:bg-dark-card border border-surface-border dark:border-dark-border rounded-[6px] shadow-lg max-h-56 overflow-y-auto">
                    {ACTIVITY_TYPES.map((a) => (
                      <button
                        key={a}
                        type="button"
                        onMouseDown={() => { setForm((f) => ({ ...f, activityType: a })); setActOpen(false) }}
                        className="w-full text-left px-3 py-2 text-[13px] hover:bg-[#F3F4F6] dark:hover:bg-[#2A2A2A]"
                      >
                        {a}
                      </button>
                    ))}
                  </div>
                )}
              </div>
              {form.activityType === 'Other' && (
                <input
                  type="text"
                  placeholder="Describe activity..."
                  value={form.customActivity}
                  onChange={(e) => setForm((f) => ({ ...f, customActivity: e.target.value }))}
                  className={inputClass}
                />
              )}
            </div>

            {/* Start time */}
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Start Time</label>
              <input
                type="time"
                value={form.startTime}
                onChange={(e) => setForm((f) => ({ ...f, startTime: e.target.value }))}
                className={inputClass}
              />
            </div>

            {/* End time */}
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>End Time</label>
              <input
                type="time"
                value={form.endTime}
                onChange={(e) =>
                  setForm((f) => ({ ...f, endTime: e.target.value, hoursAutoFilled: true }))
                }
                className={cn(inputClass, endTimeError ? 'ring-1 ring-red-500 border-red-400' : '')}
              />
              {endTimeError && (
                <span className="text-[11px] text-red-500">{endTimeError}</span>
              )}
              {form.startTime && form.endTime && !endTimeError && (
                <span className="text-[11px] text-[#6B7280]">
                  {calcDuration(form.startTime, form.endTime)}
                </span>
              )}
            </div>

            {/* Hours */}
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Hours *</label>
              <input
                type="number"
                min={0.25}
                max={24}
                step={0.25}
                value={form.hours}
                onChange={(e) =>
                  setForm((f) => ({ ...f, hours: e.target.value, hoursAutoFilled: false }))
                }
                placeholder="0.00"
                className={inputClass}
              />
            </div>

            {/* Billable toggle */}
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Billable</label>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setForm((f) => ({ ...f, isBillable: true }))}
                  className={cn(
                    'px-3 py-1.5 rounded-full text-[12px] font-medium transition-colors',
                    form.isBillable
                      ? 'bg-brand dark:bg-brand-btn text-white'
                      : 'bg-[#E5E7EB] dark:bg-[#374151] text-[#6B7280]'
                  )}
                >
                  Yes
                </button>
                <button
                  type="button"
                  onClick={() => setForm((f) => ({ ...f, isBillable: false }))}
                  className={cn(
                    'px-3 py-1.5 rounded-full text-[12px] font-medium transition-colors',
                    !form.isBillable
                      ? 'bg-brand dark:bg-brand-btn text-white'
                      : 'bg-[#E5E7EB] dark:bg-[#374151] text-[#6B7280]'
                  )}
                >
                  No
                </button>
              </div>
            </div>
          </div>

          {/* Notes */}
          <div className="flex flex-col gap-1.5">
            <label className={labelClass}>Notes</label>
            <textarea
              rows={2}
              maxLength={500}
              value={form.notes}
              onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
              placeholder="What did you work on?"
              className={cn(inputClass, 'resize-none')}
            />
          </div>

          {/* Duplicate warning */}
          {duplicateWarning && pendingPayload && (
            <div className="flex items-start gap-2 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 rounded-[6px] p-3">
              <AlertTriangle className="h-4 w-4 text-amber-500 flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="text-[12px] text-amber-800 dark:text-amber-200">
                  This looks similar to an entry you already logged today. Add anyway?
                </p>
                <div className="flex gap-2 mt-2">
                  <button
                    type="button"
                    onClick={() => submitEntry(pendingPayload)}
                    className="px-3 py-1 text-[12px] bg-amber-600 text-white rounded-[4px] hover:bg-amber-700"
                  >
                    Add anyway
                  </button>
                  <button
                    type="button"
                    onClick={() => { setDuplicateWarning(false); setPendingPayload(null) }}
                    className="px-3 py-1 text-[12px] text-[#6B7280] hover:text-brand"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            </div>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="w-full h-9 rounded-[6px] bg-[#1F3148] text-white text-[13px] font-medium hover:opacity-90 disabled:opacity-60 transition-opacity"
          >
            {submitting ? 'Adding...' : 'Add Entry'}
          </button>
        </form>
      </div>

      {/* Entries */}
      {loadingEntries ? (
        <div className="text-[13px] text-[#6B7280] py-4">Loading...</div>
      ) : entries.length === 0 ? (
        <div className="text-[13px] text-[#6B7280] py-8 text-center">
          Nothing logged yet today. Add your first entry above.
        </div>
      ) : (
        <>
          {/* Pending entries */}
          {pending.length > 0 && (
            <div className="flex flex-col gap-2">
              <span className="text-[11px] uppercase tracking-widest text-[#6B7280] font-medium">
                Pending — not yet submitted
              </span>
              <div className="flex flex-col gap-1">
                {pending.map((entry) => (
                  <EntryRow
                    key={entry.id}
                    entry={entry}
                    engagements={engagements}
                    clients={clients}
                    isManager={isManagerOrAbove}
                    isSubmitted={false}
                    approvalRequired={approvalRequired}
                    editingId={editingId}
                    editForm={editForm}
                    onEdit={() => {
                      setEditingId(entry.id)
                      setEditForm({
                        description: entry.description,
                        hours: String(entry.hours),
                        activity_type: entry.activity_type ?? '',
                        start_time: entry.start_time ?? '',
                        end_time: entry.end_time ?? '',
                        is_billable: entry.is_billable,
                      })
                    }}
                    onEditChange={(k, v) => setEditForm((f) => ({ ...f, [k]: v }))}
                    onEditSave={() => handleEditSubmit(entry.id)}
                    onEditCancel={() => setEditingId(null)}
                    onDelete={() => setDeleteConfirmId(entry.id)}
                    onSubmittedEdit={() => {}}
                  />
                ))}
              </div>
              <div className="text-[12px] text-[#6B7280]">
                {pending.length} {pending.length === 1 ? 'entry' : 'entries'} · {totalHours.toFixed(2)} hours
                {billableValue > 0 && ` · $${billableValue.toFixed(2)} billable value`}
              </div>
              <button
                onClick={handleSubmitDay}
                disabled={submittingDay}
                className="w-full h-9 rounded-[6px] bg-[#1F3148] text-white text-[13px] font-medium hover:opacity-90 disabled:opacity-60 transition-opacity"
              >
                {submittingDay ? 'Submitting...' : 'Submit Day'}
              </button>
            </div>
          )}

          {/* Submitted entries */}
          {submitted.length > 0 && (
            <div className="flex flex-col gap-2">
              <span className="text-[11px] uppercase tracking-widest text-[#6B7280] font-medium">
                Submitted
              </span>
              <div className="flex flex-col gap-1">
                {submitted.map((entry) => (
                  <EntryRow
                    key={entry.id}
                    entry={entry}
                    engagements={engagements}
                    clients={clients}
                    isManager={isManagerOrAbove}
                    isSubmitted={true}
                    approvalRequired={approvalRequired}
                    editingId={editingId}
                    editForm={editForm}
                    onEdit={() => {
                      if (isManagerOrAbove) {
                        setShowSubmittedEditModal(entry.id)
                        setEditForm({
                          description: entry.description,
                          hours: String(entry.hours),
                          activity_type: entry.activity_type ?? '',
                          start_time: entry.start_time ?? '',
                          end_time: entry.end_time ?? '',
                          is_billable: entry.is_billable,
                        })
                      }
                    }}
                    onEditChange={(k, v) => setEditForm((f) => ({ ...f, [k]: v }))}
                    onEditSave={() => handleEditSubmit(entry.id)}
                    onEditCancel={() => setEditingId(null)}
                    onDelete={() => {}}
                    onSubmittedEdit={() => {
                      setShowSubmittedEditModal(entry.id)
                      setEditForm({
                        description: entry.description,
                        hours: String(entry.hours),
                        activity_type: entry.activity_type ?? '',
                        start_time: entry.start_time ?? '',
                        end_time: entry.end_time ?? '',
                        is_billable: entry.is_billable,
                      })
                    }}
                  />
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* Delete confirm modal */}
      {deleteConfirmId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white dark:bg-dark-card rounded-[10px] p-6 shadow-xl max-w-sm w-full mx-4">
            <p className="text-[14px] font-medium text-[#111827] dark:text-[#EDEEF0] mb-2">
              Delete this entry?
            </p>
            <p className="text-[12px] text-[#6B7280] mb-5">This action cannot be undone.</p>
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setDeleteConfirmId(null)}
                className="px-4 py-2 text-[13px] rounded-[6px] border border-surface-border dark:border-dark-border text-[#374151] dark:text-[#D1D5DB]"
              >
                Cancel
              </button>
              <button
                onClick={() => handleDeleteEntry(deleteConfirmId)}
                className="px-4 py-2 text-[13px] rounded-[6px] bg-red-600 text-white hover:bg-red-700"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Submitted edit modal */}
      {showSubmittedEditModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white dark:bg-dark-card rounded-[10px] p-6 shadow-xl max-w-md w-full mx-4">
            <div className="flex items-start gap-2 mb-4">
              <AlertTriangle className="h-5 w-5 text-amber-500 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-[14px] font-medium text-[#111827] dark:text-[#EDEEF0]">
                  Editing a submitted entry
                </p>
                <p className="text-[12px] text-[#6B7280] mt-1">
                  This will notify all managers. Add a note explaining the change (optional):
                </p>
              </div>
            </div>
            <textarea
              rows={2}
              value={editNote}
              onChange={(e) => setEditNote(e.target.value)}
              placeholder="Reason for edit..."
              className="w-full rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[13px] px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-brand resize-none mb-4"
            />
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => { setShowSubmittedEditModal(null); setEditNote('') }}
                className="px-4 py-2 text-[13px] rounded-[6px] border border-surface-border dark:border-dark-border text-[#374151] dark:text-[#D1D5DB]"
              >
                Cancel
              </button>
              <button
                onClick={() => handleSubmittedEdit(showSubmittedEditModal)}
                className="px-4 py-2 text-[13px] rounded-[6px] bg-brand text-white hover:opacity-90"
              >
                Continue
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

interface EntryRowProps {
  entry: TimeEntry
  engagements: Engagement[]
  clients: Record<string, string>
  isManager: boolean
  isSubmitted: boolean
  approvalRequired: boolean
  editingId: string | null
  editForm: Record<string, unknown>
  onEdit: () => void
  onEditChange: (key: string, value: unknown) => void
  onEditSave: () => void
  onEditCancel: () => void
  onDelete: () => void
  onSubmittedEdit: () => void
}

function EntryRow({
  entry,
  engagements,
  clients,
  isManager,
  isSubmitted,
  approvalRequired,
  editingId,
  onEdit,
  onDelete,
}: EntryRowProps) {
  const eng = engagements.find((e) => e.id === entry.engagement_id)
  const clientName = eng ? clients[eng.client_id] : undefined
  const isEditing = editingId === entry.id

  if (isEditing) return null

  return (
    <div className="flex items-center gap-3 px-3 py-2.5 rounded-[6px] bg-surface-card dark:bg-dark-card border border-[0.5px] border-surface-border dark:border-dark-border">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[12px] font-medium text-brand dark:text-[#EDEEF0] truncate">
            {eng?.name ?? '—'}{clientName ? ` — ${clientName}` : ''}
          </span>
          {entry.is_billable && (
            <span className="w-2 h-2 rounded-full bg-green-500 flex-shrink-0" title="Billable" />
          )}
          {isSubmitted && entry.is_approved && (
            <span className="flex items-center gap-0.5 text-[11px] text-green-600">
              <Check className="h-3 w-3" /> Approved
            </span>
          )}
          {isSubmitted && approvalRequired && !entry.is_approved && (
            <span className="text-[11px] text-amber-600 font-medium">Pending approval</span>
          )}
        </div>
        <div className="flex items-center gap-2 mt-0.5 flex-wrap">
          {entry.activity_type && (
            <span className="text-[12px] text-[#6B7280]">{entry.activity_type}</span>
          )}
          <span className="text-[12px] text-[#9CA3AF]">
            {entry.start_time && entry.end_time
              ? `${entry.start_time} – ${entry.end_time}`
              : `${Number(entry.hours).toFixed(2)}h`}
          </span>
        </div>
      </div>
      <div className="flex items-center gap-1 flex-shrink-0">
        {!isSubmitted ? (
          <>
            <button
              onClick={onEdit}
              className="p-1.5 rounded text-[#6B7280] hover:text-brand hover:bg-[#F3F4F6] dark:hover:bg-[#2A2A2A]"
              title="Edit"
            >
              <Pencil className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={onDelete}
              className="p-1.5 rounded text-[#6B7280] hover:text-red-600 hover:bg-[#FEF2F2] dark:hover:bg-[#2A2A2A]"
              title="Delete"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </>
        ) : isManager ? (
          <button
            onClick={onEdit}
            className="p-1.5 rounded text-amber-500 hover:text-amber-700 hover:bg-amber-50 dark:hover:bg-[#2A2A2A]"
            title="Edit submitted entry"
          >
            <Pencil className="h-3.5 w-3.5" />
          </button>
        ) : null}
      </div>
    </div>
  )
}
