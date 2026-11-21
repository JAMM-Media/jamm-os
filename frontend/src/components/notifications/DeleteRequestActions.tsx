// path: frontend/src/components/notifications/DeleteRequestActions.tsx
'use client'

import { useRef, useState } from 'react'
import type { MouseEvent } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { calendarEventsApi } from '@/lib/api/calendarEvents'
import {
  getDeleteRequestState,
  isDeleteRequestApplicable,
  type EventResult,
  type LocalOutcome,
} from '@/lib/deleteRequestState'

export interface DeleteRequestNotification {
  id: string
  title: string
  is_read: boolean
  created_at: string
  related_entity_type?: string
  related_entity_id?: string
}

interface DeleteRequestActionsProps {
  notification: DeleteRequestNotification
  role?: string
  onMarkRead: (id: string) => Promise<void>
}

function httpStatus(err: unknown): number | undefined {
  return (err as { response?: { status?: number } })?.response?.status
}

function errorDetail(err: unknown): string | undefined {
  return (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
}

export function DeleteRequestActions({ notification, role, onMarkRead }: DeleteRequestActionsProps) {
  const queryClient = useQueryClient()
  const eventId = notification.related_entity_id ?? ''

  const applicable = isDeleteRequestApplicable({
    title: notification.title,
    entityType: notification.related_entity_type,
    entityId: notification.related_entity_id,
    viewerRole: role,
  })

  const [outcome, setOutcome] = useState<LocalOutcome>(null)
  const [confirmingApprove, setConfirmingApprove] = useState(false)
  const [busy, setBusy] = useState(false)
  const busyRef = useRef(false)

  const query = useQuery<EventResult>({
    queryKey: ['notification-delete-request-event', eventId],
    queryFn: async (): Promise<EventResult> => {
      try {
        const ev = await calendarEventsApi.getEvent(eventId)
        return { kind: 'event', deleteRequestedAt: ev.deleteRequestedAt }
      } catch (err) {
        // A missing event means the request was approved or the event is gone.
        if (httpStatus(err) === 404) return { kind: 'not_found' }
        throw err
      }
    },
    enabled: applicable,
    retry: false,
    staleTime: 30000,
  })

  let result: EventResult | null = null
  if (query.isError) result = { kind: 'error' }
  else if (query.data !== undefined) result = query.data
  else if (applicable) result = { kind: 'loading' }

  const state = getDeleteRequestState({
    title: notification.title,
    entityType: notification.related_entity_type,
    entityId: notification.related_entity_id,
    createdAt: notification.created_at,
    viewerRole: role,
    result,
    localOutcome: outcome,
  })

  if (state === 'not_applicable') return null

  async function run(action: 'approve' | 'deny') {
    if (busyRef.current) return
    busyRef.current = true
    setBusy(true)
    try {
      if (action === 'approve') await calendarEventsApi.approveDeleteRequest(eventId)
      else await calendarEventsApi.denyDeleteRequest(eventId)
    } catch (err) {
      const status = httpStatus(err)
      if (status === 409 || status === 404) {
        setOutcome('already_handled')
        setConfirmingApprove(false)
        toast.info('This request was already handled')
      } else {
        setConfirmingApprove(false)
        toast.error(errorDetail(err) ?? 'Could not update the event')
      }
      busyRef.current = false
      setBusy(false)
      return
    }

    // The decision is made. Nothing after this point may change the status.
    setOutcome(action === 'approve' ? 'approved' : 'denied')
    setConfirmingApprove(false)
    queryClient.invalidateQueries({ queryKey: ['native-calendar-events'] })
    queryClient.invalidateQueries({ queryKey: ['notifications-unread-count'] })
    queryClient.invalidateQueries({ queryKey: ['notification-delete-request-event', eventId] })
    if (!notification.is_read) {
      try {
        await onMarkRead(notification.id)
      } catch {
        // A mark-read failure must not change the status or show an error.
      }
    }
    busyRef.current = false
    setBusy(false)
  }

  function click(handler: () => void) {
    return (e: MouseEvent) => {
      e.preventDefault()
      e.stopPropagation()
      handler()
    }
  }

  const textClass = 'text-[11px] text-[#6B7280] mt-1'

  if (state === 'loading') {
    return <p className={textClass}>Checking request status</p>
  }
  if (state === 'unavailable') {
    return <p className={textClass}>Could not check status</p>
  }
  if (state === 'handled') {
    const label =
      outcome === 'approved' ? 'Approved' : outcome === 'denied' ? 'Denied' : 'Already handled'
    return <p className={`${textClass} font-medium`}>{label}</p>
  }

  const buttonClass =
    'text-[12px] font-medium px-3 py-1 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-brand dark:text-[#EDEEF0] disabled:opacity-60'

  return (
    <div
      className="mt-2 flex items-center gap-2"
      onClick={(e) => e.stopPropagation()}
    >
      {confirmingApprove ? (
        <>
          <span className="text-[12px] text-[#6B7280]">Delete this event?</span>
          <button type="button" className={buttonClass} disabled={busy} onClick={click(() => run('approve'))}>
            Confirm approve
          </button>
          <button type="button" className={buttonClass} disabled={busy} onClick={click(() => setConfirmingApprove(false))}>
            Cancel
          </button>
        </>
      ) : (
        <>
          <button type="button" className={buttonClass} disabled={busy} onClick={click(() => setConfirmingApprove(true))}>
            Approve
          </button>
          <button type="button" className={buttonClass} disabled={busy} onClick={click(() => run('deny'))}>
            Deny
          </button>
        </>
      )}
    </div>
  )
}
