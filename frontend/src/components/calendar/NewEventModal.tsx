// path: frontend/src/components/calendar/NewEventModal.tsx
'use client'

import { useState, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { toast } from 'sonner'
import { Modal } from '@/components/ui/Modal'
import { FormField } from '@/components/ui/FormField'
import { TextInput } from '@/components/ui/TextInput'
import { SelectInput } from '@/components/ui/SelectInput'
import { DatePickerPopover } from '@/components/calendar/DatePickerPopover'
import { calendarEventsApi, type CalendarEvent } from '@/lib/api/calendarEvents'
import { staffApi } from '@/lib/api/staffApi'
import {
  wallTimeToInstant,
  minutesIntoDay,
  snapMinutes,
  SNAP_MINUTES,
} from '@/lib/calendarTime'

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface NewEventModalProps {
  open: boolean
  onClose: () => void
  onCreated: (ev: CalendarEvent) => void
  defaultDateStr: string
  todayDateStr: string
  timeZone: string
  currentUserId: string
  role: 'firm_owner' | 'manager' | 'staff'
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

export function formatMin(m: number): string {
  const h = Math.floor(m / 60) % 12 || 12
  const min = m % 60
  const ampm = m < 720 ? 'AM' : 'PM'
  return `${h}:${String(min).padStart(2, '0')} ${ampm}`
}

function buildStartOptions(): { value: string; label: string }[] {
  const opts: { value: string; label: string }[] = []
  for (let m = 0; m <= 1410; m += SNAP_MINUTES) {
    opts.push({ value: String(m), label: formatMin(m) })
  }
  return opts
}

function buildEndOptions(): { value: string; label: string }[] {
  const opts: { value: string; label: string }[] = []
  for (let m = SNAP_MINUTES; m <= 1425; m += SNAP_MINUTES) {
    opts.push({ value: String(m), label: formatMin(m) })
  }
  return opts
}

export function defaultStartMin(dateStr: string, todayDateStr: string, timeZone: string): number {
  if (dateStr === todayDateStr) {
    try {
      const currentMin = minutesIntoDay(new Date(), timeZone)
      const snapped = snapMinutes(currentMin, 'ceil')
      if (snapped >= 0 && snapped <= 1410) return snapped
    } catch {
      // fall through to default
    }
  }
  return 9 * 60
}

// Validate a wall time for DST issues. Returns an error string or null.
function validateWallTime(dateStr: string, minutes: number, timeZone: string): string | null {
  try {
    const instant = wallTimeToInstant(dateStr, minutes, timeZone)
    const readback = minutesIntoDay(instant, timeZone)
    if (readback !== minutes) return 'That time does not exist on that date (daylight saving).'
    return null
  } catch {
    return 'That time does not exist on that date (daylight saving).'
  }
}

// ---------------------------------------------------------------------------
// Module-level option lists (built once)
// ---------------------------------------------------------------------------

const START_OPTIONS = buildStartOptions()
const END_OPTIONS = buildEndOptions()

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function NewEventModal({
  open,
  onClose,
  onCreated,
  defaultDateStr,
  todayDateStr,
  timeZone,
  currentUserId,
  role,
}: NewEventModalProps) {
  const isManagerOrAbove = role === 'firm_owner' || role === 'manager'

  // Form state
  const [title, setTitle] = useState('')
  const [dateStr, setDateStr] = useState(defaultDateStr)
  const [startMin, setStartMin] = useState(() => defaultStartMin(defaultDateStr, todayDateStr, timeZone))
  const [endMin, setEndMin] = useState(() => Math.min(defaultStartMin(defaultDateStr, todayDateStr, timeZone) + 60, 1425))
  const [categoryId, setCategoryId] = useState('')
  const [ownerValue, setOwnerValue] = useState(currentUserId)
  const [errors, setErrors] = useState<Record<string, string | undefined>>({})
  const [submitting, setSubmitting] = useState(false)

  // Date picker state
  const [datePickerOpen, setDatePickerOpen] = useState(false)
  const [datePickerPos, setDatePickerPos] = useState({ top: 0, left: 0 })
  const dateButtonRef = useRef<HTMLButtonElement>(null)
  const portalRef = useRef<HTMLDivElement>(null)

  // Data
  const [categories, setCategories] = useState<{ value: string; label: string }[]>([])
  const [roster, setRoster] = useState<{ id: string; full_name: string | null }[]>([])

  // Reset form when modal opens
  useEffect(() => {
    if (!open) return
    const s = defaultStartMin(defaultDateStr, todayDateStr, timeZone)
    setTitle('')
    setDateStr(defaultDateStr)
    setStartMin(s)
    setEndMin(Math.min(s + 60, 1425))
    setCategoryId('')
    setOwnerValue(currentUserId)
    setErrors({})
    setDatePickerOpen(false)
  }, [open]) // eslint-disable-line react-hooks/exhaustive-deps

  // Load active categories
  useEffect(() => {
    if (!open) return
    calendarEventsApi.listCategories()
      .then(({ items }) => setCategories(items.map(c => ({ value: c.id, label: c.name }))))
      .catch(() => setCategories([]))
  }, [open])

  // Load roster for managers and owners
  useEffect(() => {
    if (!open || !isManagerOrAbove) return
    staffApi.listFirmRoster()
      .then(people => setRoster(people))
      .catch(() => setRoster([]))
  }, [open, isManagerOrAbove])

  // When picker is open, intercept Escape at window capture so it closes only
  // the picker without triggering Modal's window bubble listener.
  useEffect(() => {
    if (!datePickerOpen) return
    function handleEscape(e: KeyboardEvent) {
      if (e.key !== 'Escape') return
      e.stopImmediatePropagation()
      setDatePickerOpen(false)
    }
    window.addEventListener('keydown', handleEscape, { capture: true })
    return () => window.removeEventListener('keydown', handleEscape, { capture: true })
  }, [datePickerOpen])

  // Close picker on mousedown outside button or portal
  useEffect(() => {
    if (!datePickerOpen) return
    function handleDown(e: MouseEvent) {
      if (dateButtonRef.current?.contains(e.target as Node)) return
      if (portalRef.current?.contains(e.target as Node)) return
      setDatePickerOpen(false)
    }
    document.addEventListener('mousedown', handleDown)
    return () => document.removeEventListener('mousedown', handleDown)
  }, [datePickerOpen])

  function openDatePicker() {
    const rect = dateButtonRef.current?.getBoundingClientRect()
    if (rect) {
      setDatePickerPos({ top: rect.bottom + 4, left: rect.left })
    }
    setDatePickerOpen(v => !v)
  }

  function handleStartChange(val: string) {
    const s = Number(val)
    const length = endMin - startMin
    const idealEnd = s + length
    const newEnd = Math.max(SNAP_MINUTES, Math.min(1425, idealEnd))
    setStartMin(s)
    setEndMin(newEnd > s ? newEnd : Math.min(s + 60, 1425))
    setErrors(prev => { const { start: _s, end: _e, ...rest } = prev; return rest })
  }

  function handleEndChange(val: string) {
    setEndMin(Number(val))
    setErrors(prev => { const { end: _e, ...rest } = prev; return rest })
  }

  function validate(): Record<string, string> {
    const errs: Record<string, string> = {}
    if (!title.trim()) errs.title = 'Title is required.'
    if (endMin <= startMin) errs.end = 'End time must be after start time.'
    const startDstErr = validateWallTime(dateStr, startMin, timeZone)
    if (startDstErr) errs.start = startDstErr
    const endDstErr = validateWallTime(dateStr, endMin, timeZone)
    if (endDstErr) errs.end = errs.end ?? endDstErr
    return errs
  }

  async function handleSubmit() {
    if (submitting) return
    const errs = validate()
    if (Object.keys(errs).length > 0) {
      setErrors(errs)
      return
    }

    const startInstant = wallTimeToInstant(dateStr, startMin, timeZone)
    const endInstant = wallTimeToInstant(dateStr, endMin, timeZone)

    const input: {
      title: string
      startAt: string
      endAt: string
      categoryId?: string | null
      ownerUserId?: string | null
    } = {
      title: title.trim(),
      startAt: startInstant.toISOString(),
      endAt: endInstant.toISOString(),
    }
    if (categoryId) input.categoryId = categoryId
    if (isManagerOrAbove) {
      input.ownerUserId = ownerValue === '' ? null : ownerValue
    }

    setSubmitting(true)
    try {
      const ev = await calendarEventsApi.createEvent(input)
      onCreated(ev)
      onClose()
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(detail ?? 'Could not create the event.')
    } finally {
      setSubmitting(false)
    }
  }

  function handleClose() {
    setDatePickerOpen(false)
    onClose()
  }

  const ownerOptions = [
    { value: currentUserId, label: 'Me' },
    { value: '', label: 'Whole firm' },
    ...roster
      .filter(r => r.id !== currentUserId)
      .map(r => ({ value: r.id, label: r.full_name ?? r.id })),
  ]

  return (
    <>
      <Modal
        open={open}
        onClose={handleClose}
        title="New event"
        size="md"
        footer={
          <>
            <button
              onClick={handleClose}
              className="h-9 px-3 rounded-[6px] border border-[0.5px] border-brand dark:border-[#4A7FA5] text-brand dark:text-[#EDEEF0] text-[13px] font-medium hover:bg-surface-page dark:hover:bg-dark-page transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSubmit}
              disabled={submitting}
              className="h-9 px-3 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[13px] font-medium hover:opacity-90 transition-opacity disabled:opacity-60"
            >
              Save
            </button>
          </>
        }
      >
        <div className="flex flex-col gap-4">

          {/* Title */}
          <FormField label="Title" required error={errors.title}>
            <TextInput
              aria-label="Title"
              placeholder="Meeting title"
              maxLength={255}
              value={title}
              onChange={e => {
                setTitle(e.target.value)
                setErrors(prev => { const { title: _t, ...rest } = prev; return rest })
              }}
              error={!!errors.title}
            />
          </FormField>

          {/* Date */}
          <FormField label="Date" required>
            <button
              ref={dateButtonRef}
              type="button"
              onClick={openDatePicker}
              aria-label="Pick event date"
              className="h-9 w-full px-3 rounded-[6px] text-[13px] text-left bg-surface-input dark:bg-dark-card border border-[0.5px] border-surface-border dark:border-dark-border text-brand dark:text-[#EDEEF0] focus:outline-none focus:border-brand-light transition-colors"
            >
              {dateStr}
            </button>
          </FormField>

          {/* Start / End times */}
          <div className="grid grid-cols-2 gap-3">
            <FormField label="Start time" required error={errors.start}>
              <SelectInput
                aria-label="Start time"
                value={String(startMin)}
                onChange={e => handleStartChange(e.target.value)}
                options={START_OPTIONS}
                error={!!errors.start}
              />
            </FormField>
            <FormField label="End time" required error={errors.end}>
              <SelectInput
                aria-label="End time"
                value={String(endMin)}
                onChange={e => handleEndChange(e.target.value)}
                options={END_OPTIONS}
                error={!!errors.end}
              />
            </FormField>
          </div>

          {/* Category */}
          <FormField label="Category">
            <SelectInput
              aria-label="Category"
              value={categoryId}
              onChange={e => setCategoryId(e.target.value)}
              options={[{ value: '', label: 'No category' }, ...categories]}
            />
          </FormField>

          {/* Owner (managers and owners only) */}
          {isManagerOrAbove && (
            <FormField label="Owner">
              <SelectInput
                aria-label="Owner"
                value={ownerValue}
                onChange={e => setOwnerValue(e.target.value)}
                options={ownerOptions}
              />
            </FormField>
          )}

        </div>
      </Modal>

      {/* DatePickerPopover rendered via portal to escape Modal's overflow-hidden */}
      {datePickerOpen && typeof document !== 'undefined' && createPortal(
        <div
          ref={portalRef}
          style={{ position: 'fixed', top: datePickerPos.top, left: datePickerPos.left, zIndex: 9999 }}
        >
          <DatePickerPopover
            valueDateStr={dateStr}
            todayDateStr={todayDateStr}
            onPick={d => { setDateStr(d); setDatePickerOpen(false) }}
            onClose={() => setDatePickerOpen(false)}
          />
        </div>,
        document.body
      )}
    </>
  )
}
