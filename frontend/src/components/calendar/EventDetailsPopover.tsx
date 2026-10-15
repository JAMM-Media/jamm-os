// path: frontend/src/components/calendar/EventDetailsPopover.tsx
'use client'

import { useState, useRef, useEffect } from 'react'
import { X } from 'lucide-react'
import { toast } from 'sonner'
import { calendarEventsApi, buildEventPatch, type CalendarEvent } from '@/lib/api/calendarEvents'
import { getEventActions } from '@/lib/calendarEventPermissions'
import type { EventUser } from '@/lib/calendarEventPermissions'
import { NewEventModal } from '@/components/calendar/NewEventModal'
import { formatTimeLabel } from '@/lib/calendarTime'

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface EventDetailsPopoverProps {
  event: CalendarEvent
  pos: { x: number; y: number }
  onClose: () => void
  onMutated: () => void
  timeZone: string
  user: EventUser
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatEventDate(isoStr: string, tz: string): string {
  try {
    return new Intl.DateTimeFormat('en-US', {
      month: 'short', day: 'numeric', year: 'numeric', timeZone: tz,
    }).format(new Date(isoStr))
  } catch {
    return isoStr
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function EventDetailsPopover({
  event,
  pos,
  onClose,
  onMutated,
  timeZone,
  user,
}: EventDetailsPopoverProps) {
  const actions = getEventActions(event, user)
  const popoverRef = useRef<HTMLDivElement>(null)
  const submittingRef = useRef(false)

  const [deleteConfirm, setDeleteConfirm] = useState(false)
  const [editOpen, setEditOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  // Annotation state (only relevant when canAnnotate)
  const [staffNotes, setStaffNotes] = useState(event.staffNotes ?? '')
  const [isDone, setIsDone] = useState(event.isDone)

  // Escape: only active when edit modal is closed
  useEffect(() => {
    if (editOpen) return
    function handler(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [editOpen, onClose])

  // Outside click: only active when edit modal is closed
  useEffect(() => {
    if (editOpen) return
    function handler(e: MouseEvent) {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        onClose()
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [editOpen, onClose])

  // ---------------------------------------------------------------------------
  // Actions
  // ---------------------------------------------------------------------------

  async function handleDelete() {
    if (submittingRef.current) return
    submittingRef.current = true
    setSubmitting(true)
    try {
      await calendarEventsApi.deleteEvent(event.id)
      onMutated()
      onClose()
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(detail ?? 'Could not update the event')
    } finally {
      submittingRef.current = false
      setSubmitting(false)
    }
  }

  async function handleSaveNotes() {
    if (submittingRef.current) return
    submittingRef.current = true
    setSubmitting(true)
    try {
      await calendarEventsApi.updateEvent(event.id, buildEventPatch({ staffNotes }))
      onMutated()
      onClose()
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(detail ?? 'Could not update the event')
    } finally {
      submittingRef.current = false
      setSubmitting(false)
    }
  }

  async function handleToggleDone() {
    if (submittingRef.current) return
    submittingRef.current = true
    setSubmitting(true)
    const next = !isDone
    setIsDone(next)
    try {
      await calendarEventsApi.updateEvent(event.id, buildEventPatch({ isDone: next }))
      onMutated()
      onClose()
    } catch (err: unknown) {
      setIsDone(!next)
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(detail ?? 'Could not update the event')
    } finally {
      submittingRef.current = false
      setSubmitting(false)
    }
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  const ownerLabel = event.ownerUserId === null ? 'Whole firm' : (event.ownerName ?? event.ownerUserId ?? 'Unknown')

  return (
    <>
      <div
        ref={popoverRef}
        data-testid="event-details-popover"
        className="fixed z-50 bg-surface-card dark:bg-dark-card border border-surface-border dark:border-dark-border rounded-[10px] shadow-lg p-4 w-80"
        style={{
          top: Math.min(pos.y, window.innerHeight - 320),
          left: Math.min(pos.x, window.innerWidth - 340),
        }}
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-2 mb-3">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0] leading-snug">
              {event.title}
            </p>
            {event.isDone && (
              <span
                data-testid="done-badge"
                className="text-[10px] font-medium bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 px-1.5 py-0.5 rounded"
              >
                Done
              </span>
            )}
          </div>
          <button
            onClick={onClose}
            className="text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] flex-shrink-0"
            aria-label="Close"
          >
            <X size={14} />
          </button>
        </div>

        {/* Date and time */}
        <p className="text-[12px] text-[#6B7280] mb-1">{formatEventDate(event.startAt, timeZone)}</p>
        <p className="text-[12px] text-[#6B7280] mb-2">
          {formatTimeLabel(event.startAt, timeZone)} to {formatTimeLabel(event.endAt, timeZone)}
        </p>

        {/* Category */}
        {event.categoryName && (
          <p className="text-[12px] text-[#6B7280] mb-1">Category: {event.categoryName}</p>
        )}

        {/* Owner */}
        <p className="text-[12px] text-[#6B7280] mb-1">Owner: {ownerLabel}</p>

        {/* Client */}
        {event.clientName && (
          <p className="text-[12px] text-[#6B7280] mb-1">Client: {event.clientName}</p>
        )}

        {/* Staff notes (read-only for everyone who can view) */}
        {event.staffNotes && (
          <p className="text-[12px] text-[#6B7280] mb-2 whitespace-pre-wrap">
            Notes: {event.staffNotes}
          </p>
        )}

        {/* Action buttons */}
        <div className="flex flex-col gap-2 mt-3">
          {actions.canEdit && !deleteConfirm && (
            <button
              onClick={() => setEditOpen(true)}
              className="h-8 px-3 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[12px] font-medium hover:opacity-90 transition-opacity"
            >
              Edit
            </button>
          )}

          {actions.canDelete && !deleteConfirm && (
            <button
              onClick={() => setDeleteConfirm(true)}
              className="h-8 px-3 rounded-[6px] border border-red-400 text-red-600 dark:text-red-400 text-[12px] font-medium hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
            >
              Delete
            </button>
          )}

          {actions.canDelete && deleteConfirm && (
            <div className="flex gap-2">
              <button
                onClick={() => setDeleteConfirm(false)}
                className="flex-1 h-8 px-3 rounded-[6px] border border-surface-border text-[12px] font-medium text-brand dark:text-[#EDEEF0] hover:bg-surface-page dark:hover:bg-dark-page transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                disabled={submitting}
                className="flex-1 h-8 px-3 rounded-[6px] bg-red-600 text-white text-[12px] font-medium hover:bg-red-700 transition-colors disabled:opacity-60"
              >
                Confirm
              </button>
            </div>
          )}

          {actions.canAnnotate && (
            <>
              <textarea
                aria-label="Staff notes"
                value={staffNotes}
                onChange={e => setStaffNotes(e.target.value)}
                rows={3}
                className="w-full text-[12px] px-2 py-1.5 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-input dark:bg-dark-card text-brand dark:text-[#EDEEF0] resize-none focus:outline-none focus:border-brand-light"
              />
              <button
                onClick={handleSaveNotes}
                disabled={submitting}
                className="h-8 px-3 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[12px] font-medium hover:opacity-90 transition-opacity disabled:opacity-60"
              >
                Save notes
              </button>
              <label className="flex items-center gap-2 text-[12px] text-brand dark:text-[#EDEEF0] cursor-pointer">
                <input
                  type="checkbox"
                  aria-label="Mark done"
                  checked={isDone}
                  onChange={handleToggleDone}
                  disabled={submitting}
                  className="rounded"
                />
                Mark done
              </label>
            </>
          )}
        </div>
      </div>

      {editOpen && (
        <NewEventModal
          open={editOpen}
          onClose={() => setEditOpen(false)}
          onCreated={() => { onMutated(); onClose() }}
          editEvent={event}
          defaultDateStr={''}
          todayDateStr={''}
          timeZone={timeZone}
          currentUserId={user.id}
          role={user.role}
        />
      )}
    </>
  )
}
