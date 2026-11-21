// path: frontend/src/lib/deleteRequestState.ts

// Pure state for a delete-request notification row. No React, no network.
//
// A notification points at a calendar event, not at one specific request, so a
// row can outlive the request it announced. The rule below treats a request
// stamped later than the notification as a newer request, which makes the row
// stale. The backend stamps delete_requested_at before it creates the
// notification, so a current request is never later than created_at; the
// tolerance only absorbs clock noise.

export const TOLERANCE_MS = 5000

export const DELETE_REQUEST_TITLE = 'Delete request'
export const DELETE_REQUEST_ENTITY = 'calendar_event'

export type DeleteRequestState =
  | 'not_applicable'
  | 'loading'
  | 'pending'
  | 'handled'
  | 'unavailable'

// What the event fetch produced. A 404 is mapped to not_found by the caller.
export type EventResult =
  | { kind: 'loading' }
  | { kind: 'event'; deleteRequestedAt: string | null }
  | { kind: 'not_found' }
  | { kind: 'error' }

// Set by a click on this row. Component state only, so it resets on reload.
export type LocalOutcome = 'approved' | 'denied' | 'already_handled' | null

export interface DeleteRequestInput {
  title: string
  entityType?: string
  entityId?: string
  createdAt: string
  viewerRole?: string
  result: EventResult | null
  localOutcome: LocalOutcome
}

export function isDeleteRequestRow(
  title: string,
  entityType?: string,
  entityId?: string,
): boolean {
  return title === DELETE_REQUEST_TITLE && entityType === DELETE_REQUEST_ENTITY && !!entityId
}

// Only firm owners and managers see the buttons. Every other role, including
// system_admin, gets the plain row.
export function canResolveDeleteRequests(role?: string): boolean {
  return role === 'firm_owner' || role === 'manager'
}

export function isDeleteRequestApplicable(input: {
  title: string
  entityType?: string
  entityId?: string
  viewerRole?: string
}): boolean {
  return (
    isDeleteRequestRow(input.title, input.entityType, input.entityId) &&
    canResolveDeleteRequests(input.viewerRole)
  )
}

export function getDeleteRequestState(input: DeleteRequestInput): DeleteRequestState {
  if (!isDeleteRequestApplicable(input)) return 'not_applicable'

  if (input.localOutcome !== null) return 'handled'

  const result = input.result
  if (result === null || result.kind === 'loading') return 'loading'
  if (result.kind === 'not_found') return 'handled'
  if (result.kind === 'error') return 'unavailable'

  if (result.deleteRequestedAt === null) return 'handled'

  const requested = Date.parse(result.deleteRequestedAt)
  const created = Date.parse(input.createdAt)
  // An unreadable timestamp is never treated as pending.
  if (Number.isNaN(requested) || Number.isNaN(created)) return 'unavailable'

  return requested <= created + TOLERANCE_MS ? 'pending' : 'handled'
}
