// path: frontend/src/lib/deleteRequestState.test.ts
import { describe, it, expect } from 'vitest'
import {
  TOLERANCE_MS,
  canResolveDeleteRequests,
  getDeleteRequestState,
  isDeleteRequestRow,
  type DeleteRequestInput,
} from './deleteRequestState'

const CREATED = '2026-10-20T18:30:00.000Z'
const CREATED_MS = Date.parse(CREATED)

function iso(ms: number): string {
  return new Date(ms).toISOString()
}

function input(over: Partial<DeleteRequestInput> = {}): DeleteRequestInput {
  return {
    title: 'Delete request',
    entityType: 'calendar_event',
    entityId: 'ev-1',
    createdAt: CREATED,
    viewerRole: 'manager',
    result: { kind: 'event', deleteRequestedAt: iso(CREATED_MS - 1000) },
    localOutcome: null,
    ...over,
  }
}

describe('getDeleteRequestState: the five states', () => {
  it('not_applicable for a plain row', () => {
    expect(getDeleteRequestState(input({ title: 'Something else' }))).toBe('not_applicable')
  })

  it('loading while the event fetch is in flight', () => {
    expect(getDeleteRequestState(input({ result: { kind: 'loading' } }))).toBe('loading')
    expect(getDeleteRequestState(input({ result: null }))).toBe('loading')
  })

  it('pending when the request is older than the notification', () => {
    expect(getDeleteRequestState(input())).toBe('pending')
  })

  it('handled when the event fetch returned 404', () => {
    expect(getDeleteRequestState(input({ result: { kind: 'not_found' } }))).toBe('handled')
  })

  it('unavailable for any other fetch error', () => {
    expect(getDeleteRequestState(input({ result: { kind: 'error' } }))).toBe('unavailable')
  })
})

describe('getDeleteRequestState: pending versus stale', () => {
  it('handled when deleteRequestedAt is null', () => {
    expect(
      getDeleteRequestState(input({ result: { kind: 'event', deleteRequestedAt: null } })),
    ).toBe('handled')
  })

  it('exactly at TOLERANCE_MS after the notification is still pending', () => {
    const result = { kind: 'event' as const, deleteRequestedAt: iso(CREATED_MS + TOLERANCE_MS) }
    expect(getDeleteRequestState(input({ result }))).toBe('pending')
  })

  it('1 ms over TOLERANCE_MS is handled, a newer request makes the row stale', () => {
    const result = { kind: 'event' as const, deleteRequestedAt: iso(CREATED_MS + TOLERANCE_MS + 1) }
    expect(getDeleteRequestState(input({ result }))).toBe('handled')
  })

  it('a request stamped well before the notification is pending', () => {
    const result = { kind: 'event' as const, deleteRequestedAt: iso(CREATED_MS - 60000) }
    expect(getDeleteRequestState(input({ result }))).toBe('pending')
  })

  it('compares instants, so a UTC offset on either side does not matter', () => {
    const result = { kind: 'event' as const, deleteRequestedAt: '2026-10-20T13:29:59.000-05:00' }
    expect(getDeleteRequestState(input({ result }))).toBe('pending')
    const later = { kind: 'event' as const, deleteRequestedAt: '2026-10-20T13:30:06.000-05:00' }
    expect(getDeleteRequestState(input({ result: later }))).toBe('handled')
  })

  it('an unparseable deleteRequestedAt is unavailable, never pending', () => {
    const result = { kind: 'event' as const, deleteRequestedAt: 'not a date' }
    expect(getDeleteRequestState(input({ result }))).toBe('unavailable')
  })

  it('an unparseable notification created_at is unavailable, never pending', () => {
    expect(getDeleteRequestState(input({ createdAt: '' }))).toBe('unavailable')
    expect(getDeleteRequestState(input({ createdAt: 'garbage' }))).toBe('unavailable')
  })
})

describe('getDeleteRequestState: viewer role', () => {
  it('firm_owner and manager are applicable', () => {
    expect(getDeleteRequestState(input({ viewerRole: 'firm_owner' }))).toBe('pending')
    expect(getDeleteRequestState(input({ viewerRole: 'manager' }))).toBe('pending')
  })

  it.each(['staff', 'client_portal_user', 'system_admin', '', undefined])(
    'role %s is not_applicable',
    (role) => {
      expect(getDeleteRequestState(input({ viewerRole: role }))).toBe('not_applicable')
    },
  )

  it('canResolveDeleteRequests allows only firm_owner and manager', () => {
    expect(canResolveDeleteRequests('firm_owner')).toBe(true)
    expect(canResolveDeleteRequests('manager')).toBe(true)
    expect(canResolveDeleteRequests('staff')).toBe(false)
    expect(canResolveDeleteRequests(undefined)).toBe(false)
  })
})

describe('getDeleteRequestState: which rows qualify', () => {
  it('missing related_entity_id is not_applicable', () => {
    expect(getDeleteRequestState(input({ entityId: undefined }))).toBe('not_applicable')
    expect(getDeleteRequestState(input({ entityId: '' }))).toBe('not_applicable')
  })

  it('wrong title is not_applicable', () => {
    expect(getDeleteRequestState(input({ title: 'Delete request ' }))).toBe('not_applicable')
    expect(getDeleteRequestState(input({ title: 'delete request' }))).toBe('not_applicable')
  })

  it('wrong entity type is not_applicable', () => {
    expect(getDeleteRequestState(input({ entityType: 'task' }))).toBe('not_applicable')
    expect(getDeleteRequestState(input({ entityType: undefined }))).toBe('not_applicable')
  })

  it('isDeleteRequestRow needs title, entity type and id', () => {
    expect(isDeleteRequestRow('Delete request', 'calendar_event', 'ev-1')).toBe(true)
    expect(isDeleteRequestRow('Delete request', 'calendar_event', undefined)).toBe(false)
    expect(isDeleteRequestRow('Other', 'calendar_event', 'ev-1')).toBe(false)
    expect(isDeleteRequestRow('Delete request', 'task', 'ev-1')).toBe(false)
  })
})

describe('getDeleteRequestState: local outcome', () => {
  it.each(['approved', 'denied', 'already_handled'] as const)(
    'a %s click makes the row handled even while the event still looks pending',
    (localOutcome) => {
      expect(getDeleteRequestState(input({ localOutcome }))).toBe('handled')
    },
  )

  it('a local outcome never reveals a row to a non-eligible viewer', () => {
    expect(
      getDeleteRequestState(input({ viewerRole: 'staff', localOutcome: 'approved' })),
    ).toBe('not_applicable')
  })
})
