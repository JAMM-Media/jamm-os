// path: frontend/src/components/calendar/EventDetailsPopover.tsx
'use client'

import { useState, useRef, useEffect } from 'react'
import { X } from 'lucide-react'
import { toast } from 'sonner'
import { calendarEventsApi, buildEventPatch, type CalendarEvent } from '@/lib/api/calendarEvents'
import { getEventActions, getDeleteRequestActions } from '@/lib/calendarEventPermissions'
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
  const [localEvent, setLocalEvent] = useState(event)
  const actions = getEventActions(localEvent, user)
  const drActions = getDeleteRequestActions(localEvent, user)

  const popoverRef = useRef<HTMLDivElement>(null)
  const submittingRef = useRef(false)

  const [deleteConfirm, setDeleteConfirm] = useState(false)
  const [editOpen, setEditOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  // Annotation state
  const [staffNotes, setStaffNotes] = useState(localEvent.staffNotes ?? '')
  const [isDone, setIsDone] = useState(localEvent.isDone)

  // Delete request state
  const [requestStep, setRequestStep] = useState(false)
  const [reason, setReason] = useState('')

  // Approve/deny confirm state
  const [confirmAction, setConfirmAction] = useState<'approve' | 'deny' | null>(null)

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
      await calendarEventsApi.deleteEvent(localEvent.id)
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
      const updated = await calendarEventsApi.updateEvent(localEvent.id, buildEventPatch({ staffNotes }))
      setLocalEvent(updated)
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
      const updated = await calendarEventsApi.updateEvent(localEvent.id, buildEventPatch({ isDone: next }))
      setLocalEvent(updated)
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

  async function handleRequestDelete() {
    if (submittingRef.current) return
    if (reason.length > 500) return
    submittingRef.current = true
    setSubmitting(true)
    try {
      const updated = await calendarEventsApi.requestDelete(localEvent.id, reason || undefined)
      setLocalEvent(updated)
      setRequestStep(false)
      setReason('')
      onMutated()
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(detail ?? 'Could not update the event')
    } finally {
      submittingRef.current = false
      setSubmitting(false)
    }
  }

  async function handleApproveDeleteRequest() {
    if (submittingRef.current) return
    submittingRef.current = true
    setSubmitting(true)
    try {
      await calendarEventsApi.approveDeleteRequest(localEvent.id)
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

  async function handleDenyDeleteRequest() {
    if (submittingRef.current) return
    submittingRef.current = true
    setSubmitting(true)
    try {
      const updated = await calendarEventsApi.denyDeleteRequest(localEvent.id)
      setLocalEvent(updated)
      setConfirmAction(null)
      onMutated()
    } catch (err: unknown) {
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

  const ownerLabel = localEvent.ownerUserId === null
    ? 'Whole firm'
    : (localEvent.ownerName ?? localEvent.ownerUserId ?? 'Unknown')
  const requesterLabel = localEvent.ownerName ?? 'A staff member'
  const reasonOverLimit = reason.length > 500

  return (
    <>
      <div
        ref={popoverRef}
        hidden={editOpen}
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
              {localEvent.title}
            </p>
            {localEvent.isDone && (
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
        <p className="text-[12px] text-[#6B7280] mb-1">{formatEventDate(localEvent.startAt, timeZone)}</p>
        <p className="text-[12px] text-[#6B7280] mb-2">
          {formatTimeLabel(localEvent.startAt, timeZone)} to {formatTimeLabel(localEvent.endAt, timeZone)}
        </p>

        {/* Category */}
        {localEvent.categoryName && (
          <p className="text-[12px] text-[#6B7280] mb-1">Category: {localEvent.categoryName}</p>
        )}

        {/* Owner */}
        <p className="text-[12px] text-[#6B7280] mb-1">Owner: {ownerLabel}</p>

        {/* Client */}
        {localEvent.clientName && (
          <p className="text-[12px] text-[#6B7280] mb-1">Client: {localEvent.clientName}</p>
        )}

        {/* Staff notes (read-only for all viewers) */}
        {localEvent.staffNotes && (
          <p className="text-[12px] text-[#6B7280] mb-2 whitespace-pre-wrap">
            Notes: {localEvent.staffNotes}
          </p>
        )}

        {/* Action buttons */}
        <div className="flex flex-col gap-2 mt-3">

          {/* Edit */}
          {actions.canEdit && !deleteConfirm && (
            <button
              onClick={() => setEditOpen(true)}
              className="h-8 px-3 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[12px] font-medium hover:opacity-90 transition-opacity"
            >
              Edit
            </button>
          )}

          {/* Delete */}
          {actions.canDelete && !deleteConfirm && (
            <button
              onClick={() => setDeleteConfirm(true)}
              className="h-8 px-3 rounded-[6px] border border-red-400 text-red-600 dark:text-red-400 text-[12px] font-medium hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
            >
              Delete
            </button>
          )}

          {/* Delete confirm */}
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

          {/* Annotate controls */}
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

          {/* Request deletion button */}
          {drActions.canRequestDelete && !requestStep && (
            <button
              onClick={() => setRequestStep(true)}
              className="h-8 px-3 rounded-[6px] border border-[#6B7280] text-[#6B7280] text-[12px] font-medium hover:bg-surface-page dark:hover:bg-dark-page transition-colors"
            >
              Request deletion
            </button>
          )}

          {/* Request deletion inline step */}
          {drActions.canRequestDelete && requestStep && (
            <div className="flex flex-col gap-2">
              <textarea
                aria-label="Reason for deletion request"
                value={reason}
                onChange={e => setReason(e.target.value)}
                rows={3}
                placeholder="Reason (optional)"
                className="w-full text-[12px] px-2 py-1.5 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-input dark:bg-dark-card text-brand dark:text-[#EDEEF0] resize-none focus:outline-none focus:border-brand-light"
              />
              {reasonOverLimit && (
                <p className="text-[11px] text-red-600 dark:text-red-400">Reason must be 500 characters or fewer.</p>
              )}
              <div className="flex gap-2">
                <button
                  onClick={() => { setRequestStep(false); setReason('') }}
                  className="flex-1 h-8 px-3 rounded-[6px] border border-surface-border text-[12px] font-medium text-brand dark:text-[#EDEEF0] hover:bg-surface-page dark:hover:bg-dark-page transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleRequestDelete}
                  disabled={submitting || reasonOverLimit}
                  className="flex-1 h-8 px-3 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[12px] font-medium hover:opacity-90 transition-opacity disabled:opacity-60"
                >
                  Send
                </button>
              </div>
            </div>
          )}

          {/* Pending: staff view */}
          {drActions.isPending && !drActions.canResolveRequest && (
            <div className="mt-1">
              <p
                className="text-[12px] text-[#6B7280]"
                data-testid="deletion-requested-msg"
              >
                Deletion requested
              </p>
              {localEvent.deleteRequestReason && (
                <p className="text-[12px] text-[#6B7280] mt-0.5">
                  Reason: {localEvent.deleteRequestReason}
                </p>
              )}
            </div>
          )}

          {/* Pending: manager/owner view */}
          {drActions.canResolveRequest && (
            <div className="flex flex-col gap-2 mt-1">
              <p
                className="text-[12px] text-[#6B7280]"
                data-testid="resolve-request-msg"
              >
                {requesterLabel} asked to delete this event
              </p>
              {localEvent.deleteRequestReason && (
                <p className="text-[12px] text-[#6B7280]">
                  Reason: {localEvent.deleteRequestReason}
                </p>
              )}
              {confirmAction === null && (
                <div className="flex gap-2">
                  <button
                    onClick={() => setConfirmAction('approve')}
                    className="flex-1 h-8 px-3 rounded-[6px] bg-red-600 text-white text-[12px] font-medium hover:bg-red-700 transition-colors"
                  >
                    Approve
                  </button>
                  <button
                    onClick={() => setConfirmAction('deny')}
                    className="flex-1 h-8 px-3 rounded-[6px] border border-surface-border text-[12px] font-medium text-brand dark:text-[#EDEEF0] hover:bg-surface-page dark:hover:bg-dark-page transition-colors"
                  >
                    Deny
                  </button>
                </div>
              )}
              {confirmAction === 'approve' && (
                <div className="flex gap-2">
                  <button
                    onClick={() => setConfirmAction(null)}
                    className="flex-1 h-8 px-3 rounded-[6px] border border-surface-border text-[12px] font-medium text-brand dark:text-[#EDEEF0] hover:bg-surface-page dark:hover:bg-dark-page transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleApproveDeleteRequest}
                    disabled={submitting}
                    className="flex-1 h-8 px-3 rounded-[6px] bg-red-600 text-white text-[12px] font-medium hover:bg-red-700 transition-colors disabled:opacity-60"
                  >
                    Confirm
                  </button>
                </div>
              )}
              {confirmAction === 'deny' && (
                <div className="flex gap-2">
                  <button
                    onClick={() => setConfirmAction(null)}
                    className="flex-1 h-8 px-3 rounded-[6px] border border-surface-border text-[12px] font-medium text-brand dark:text-[#EDEEF0] hover:bg-surface-page dark:hover:bg-dark-page transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleDenyDeleteRequest}
                    disabled={submitting}
                    className="flex-1 h-8 px-3 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[12px] font-medium hover:opacity-90 transition-opacity disabled:opacity-60"
                  >
                    Confirm
                  </button>
                </div>
              )}
            </div>
          )}

        </div>
      </div>

      {editOpen && (
        <NewEventModal
          open={editOpen}
          onClose={() => setEditOpen(false)}
          onCreated={() => { onMutated(); onClose() }}
          editEvent={localEvent}
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
