// path: frontend/src/lib/calendarEventPermissions.test.ts
import { describe, it, expect } from 'vitest'
import { getEventActions, getDeleteRequestActions } from './calendarEventPermissions'
import type { CalendarEvent } from './api/calendarEvents'
import type { EventUser, EventActions, DeleteRequestActions } from './calendarEventPermissions'

const SELF = 'user-self'
const MANAGER = 'user-manager'
const OTHER = 'user-other'

function makeEvent(overrides: Partial<CalendarEvent>): CalendarEvent {
  return {
    id: 'ev-1',
    title: 'Test event',
    startAt: '2026-10-14T14:00:00Z',
    endAt: '2026-10-14T15:00:00Z',
    eventTimezone: 'America/New_York',
    categoryId: null,
    categoryName: null,
    categoryColor: null,
    clientId: null,
    clientName: null,
    ownerUserId: null,
    ownerName: null,
    createdBy: null,
    createdAt: '2026-10-01T00:00:00Z',
    updatedAt: '2026-10-01T00:00:00Z',
    deletedAt: null,
    staffNotes: null,
    completedAt: null,
    isDone: false,
    deleteRequestedAt: null,
    deleteRequestedBy: null,
    deleteRequestReason: null,
    ...overrides,
  }
}

const firmOwner: EventUser = { id: SELF, role: 'firm_owner' }
const manager: EventUser = { id: SELF, role: 'manager' }
const staff: EventUser = { id: SELF, role: 'staff' }

type Case = {
  label: string
  event: CalendarEvent
  user: EventUser
  expected: EventActions
  chosen?: string
}

const cases: Case[] = [
  // --- firm_owner ---
  {
    label: 'firm_owner on own event',
    event: makeEvent({ createdBy: SELF, ownerUserId: SELF }),
    user: firmOwner,
    expected: { canView: true, canEdit: true, canDelete: true, canAnnotate: false },
  },
  {
    label: 'firm_owner on manager-assigned event',
    event: makeEvent({ createdBy: MANAGER, ownerUserId: OTHER }),
    user: firmOwner,
    expected: { canView: true, canEdit: true, canDelete: true, canAnnotate: false },
  },
  {
    label: 'firm_owner on firm-wide event',
    event: makeEvent({ createdBy: null, ownerUserId: null }),
    user: firmOwner,
    expected: { canView: true, canEdit: true, canDelete: true, canAnnotate: false },
  },
  {
    label: 'firm_owner on another user event',
    event: makeEvent({ createdBy: OTHER, ownerUserId: OTHER }),
    user: firmOwner,
    expected: { canView: true, canEdit: true, canDelete: true, canAnnotate: false },
  },

  // --- manager ---
  {
    label: 'manager on own event',
    event: makeEvent({ createdBy: SELF, ownerUserId: SELF }),
    user: manager,
    expected: { canView: true, canEdit: true, canDelete: true, canAnnotate: false },
  },
  {
    label: 'manager on manager-assigned event',
    event: makeEvent({ createdBy: MANAGER, ownerUserId: OTHER }),
    user: manager,
    expected: { canView: true, canEdit: true, canDelete: true, canAnnotate: false },
  },
  {
    label: 'manager on firm-wide event',
    event: makeEvent({ createdBy: null, ownerUserId: null }),
    user: manager,
    expected: { canView: true, canEdit: true, canDelete: true, canAnnotate: false },
  },
  {
    label: 'manager on another user event',
    event: makeEvent({ createdBy: OTHER, ownerUserId: OTHER }),
    user: manager,
    expected: { canView: true, canEdit: true, canDelete: true, canAnnotate: false },
  },

  // --- staff ---
  {
    label: 'staff on own event (createdBy=self, ownerUserId=self)',
    event: makeEvent({ createdBy: SELF, ownerUserId: SELF }),
    user: staff,
    expected: { canView: true, canEdit: true, canDelete: true, canAnnotate: false },
  },
  {
    label: 'staff on manager-assigned event (createdBy=manager, ownerUserId=self)',
    event: makeEvent({ createdBy: MANAGER, ownerUserId: SELF }),
    user: staff,
    expected: { canView: true, canEdit: false, canDelete: false, canAnnotate: true },
  },
  // [chosen] createdBy=null, ownerUserId=self: _can_annotate_only fires because
  // owner_user_id==user.id and created_by(null)!=user.id; canAnnotate=true
  {
    label: 'staff on event with createdBy=null and ownerUserId=self',
    event: makeEvent({ createdBy: null, ownerUserId: SELF }),
    user: staff,
    expected: { canView: true, canEdit: false, canDelete: false, canAnnotate: true },
    chosen: '_can_annotate_only fires: owner==self, created_by null!=self',
  },
  // [chosen] firm-wide, createdBy=self: _can_edit_or_delete requires ownerUserId==self
  // which fails (null!=self); _can_annotate_only requires ownerUserId==self which also
  // fails; so no actions despite being the creator
  {
    label: 'staff on firm-wide event they created (ownerUserId=null, createdBy=self)',
    event: makeEvent({ createdBy: SELF, ownerUserId: null }),
    user: staff,
    expected: { canView: true, canEdit: false, canDelete: false, canAnnotate: false },
    chosen: '_can_edit_or_delete: ownerUserId(null)!=self fails; _can_annotate_only: ownerUserId(null)!=self fails',
  },
  {
    label: 'staff on firm-wide event (ownerUserId=null, createdBy=null)',
    event: makeEvent({ createdBy: null, ownerUserId: null }),
    user: staff,
    expected: { canView: true, canEdit: false, canDelete: false, canAnnotate: false },
  },
  {
    label: 'staff on another user event (ownerUserId=other)',
    event: makeEvent({ createdBy: OTHER, ownerUserId: OTHER }),
    user: staff,
    expected: { canView: false, canEdit: false, canDelete: false, canAnnotate: false },
  },
]

describe('getEventActions', () => {
  for (const { label, event, user, expected } of cases) {
    it(label, () => {
      expect(getEventActions(event, user)).toEqual(expected)
    })
  }
})


type DRCase = {
  label: string
  event: CalendarEvent
  user: EventUser
  expected: DeleteRequestActions
}

const PENDING_AT = '2026-10-14T10:00:00Z'

const drCases: DRCase[] = [
  {
    label: 'staff on manager-assigned event can request deletion',
    event: makeEvent({ createdBy: MANAGER, ownerUserId: SELF, deleteRequestedAt: null }),
    user: staff,
    expected: { canRequestDelete: true, canResolveRequest: false, isPending: false },
  },
  {
    label: 'staff on own event cannot request (can delete directly)',
    event: makeEvent({ createdBy: SELF, ownerUserId: SELF, deleteRequestedAt: null }),
    user: staff,
    expected: { canRequestDelete: false, canResolveRequest: false, isPending: false },
  },
  {
    label: 'staff on firm-wide event cannot request',
    event: makeEvent({ createdBy: null, ownerUserId: null, deleteRequestedAt: null }),
    user: staff,
    expected: { canRequestDelete: false, canResolveRequest: false, isPending: false },
  },
  {
    label: 'staff on another person event cannot request (not owner)',
    event: makeEvent({ createdBy: OTHER, ownerUserId: OTHER, deleteRequestedAt: null }),
    user: staff,
    expected: { canRequestDelete: false, canResolveRequest: false, isPending: false },
  },
  {
    label: 'staff with pending request cannot request again',
    event: makeEvent({ createdBy: MANAGER, ownerUserId: SELF, deleteRequestedAt: PENDING_AT }),
    user: staff,
    expected: { canRequestDelete: false, canResolveRequest: false, isPending: true },
  },
  {
    label: 'manager on pending event can resolve',
    event: makeEvent({ deleteRequestedAt: PENDING_AT }),
    user: manager,
    expected: { canRequestDelete: false, canResolveRequest: true, isPending: true },
  },
  {
    label: 'manager on non-pending event cannot resolve',
    event: makeEvent({ deleteRequestedAt: null }),
    user: manager,
    expected: { canRequestDelete: false, canResolveRequest: false, isPending: false },
  },
  {
    label: 'firm_owner on pending event can resolve',
    event: makeEvent({ deleteRequestedAt: PENDING_AT }),
    user: firmOwner,
    expected: { canRequestDelete: false, canResolveRequest: true, isPending: true },
  },
  {
    label: 'staff cannot resolve even when pending',
    event: makeEvent({ createdBy: MANAGER, ownerUserId: SELF, deleteRequestedAt: PENDING_AT }),
    user: staff,
    expected: { canRequestDelete: false, canResolveRequest: false, isPending: true },
  },
]

describe('getDeleteRequestActions', () => {
  for (const { label, event, user, expected } of drCases) {
    it(label, () => {
      expect(getDeleteRequestActions(event, user)).toEqual(expected)
    })
  }
})
