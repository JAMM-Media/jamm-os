// path: frontend/src/lib/calendarEventPermissions.ts
import type { CalendarEvent } from './api/calendarEvents'

export interface EventUser {
  id: string
  role: 'firm_owner' | 'manager' | 'staff'
}

export interface EventActions {
  canView: boolean
  canEdit: boolean
  canDelete: boolean
  canAnnotate: boolean
}

export interface DeleteRequestActions {
  canRequestDelete: boolean
  canResolveRequest: boolean
  isPending: boolean
}

function isManagerOrAbove(user: EventUser): boolean {
  return user.role === 'firm_owner' || user.role === 'manager'
}

export function getEventActions(event: CalendarEvent, user: EventUser): EventActions {
  if (isManagerOrAbove(user)) {
    return { canView: true, canEdit: true, canDelete: true, canAnnotate: false }
  }

  // staff
  const canView = event.ownerUserId === null || event.ownerUserId === user.id
  if (!canView) {
    return { canView: false, canEdit: false, canDelete: false, canAnnotate: false }
  }

  // _can_edit_or_delete: created_by must not be null, must equal user.id, and owner must be user.id
  const canEditOrDelete =
    event.createdBy !== null &&
    event.createdBy === user.id &&
    event.ownerUserId === user.id

  if (canEditOrDelete) {
    return { canView: true, canEdit: true, canDelete: true, canAnnotate: false }
  }

  // _can_annotate_only: owner is the user AND created_by is someone else (including null)
  const canAnnotate = event.ownerUserId === user.id && event.createdBy !== user.id

  return { canView: true, canEdit: false, canDelete: false, canAnnotate }
}

export function getDeleteRequestActions(event: CalendarEvent, user: EventUser): DeleteRequestActions {
  const isPending = event.deleteRequestedAt !== null

  const canRequestDelete =
    !isManagerOrAbove(user) &&
    event.ownerUserId === user.id &&
    event.createdBy !== user.id &&
    !isPending

  const canResolveRequest = isManagerOrAbove(user) && isPending

  return { canRequestDelete, canResolveRequest, isPending }
}
