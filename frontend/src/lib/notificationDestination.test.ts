// path: frontend/src/lib/notificationDestination.test.ts
import { describe, it, expect } from 'vitest'
import {
  NOTIFICATION_ENTITY_TYPES,
  getEntityDestinationLabel,
  getEntityPath,
} from './notificationPaths'

describe('getEntityDestinationLabel', () => {
  it('has a label exactly when there is a path, for every type in the shared table', () => {
    expect(NOTIFICATION_ENTITY_TYPES.length).toBeGreaterThan(0)
    for (const type of NOTIFICATION_ENTITY_TYPES) {
      for (const id of ['some-id', undefined, '']) {
        const path = getEntityPath(type, id)
        const label = getEntityDestinationLabel(type, id)
        expect(label === null).toBe(path === null)
      }
    }
  })

  it('gives the expected label for each type that has a path', () => {
    expect(getEntityDestinationLabel('engagement', '1')).toBe('Engagement')
    expect(getEntityDestinationLabel('task', '2')).toBe('Task')
    expect(getEntityDestinationLabel('client', '3')).toBe('Client')
    expect(getEntityDestinationLabel('lead', '4')).toBe('Lead')
    expect(getEntityDestinationLabel('document', '5')).toBe('Document')
    expect(getEntityDestinationLabel('message', '6')).toBe('Firm chat')
    expect(getEntityDestinationLabel('time_entry')).toBe('Timesheets')
    expect(getEntityDestinationLabel('staff_credential')).toBe('Staff')
    expect(getEntityDestinationLabel('calendar_event')).toBe('Calendar')
  })

  it('is null for id-based types without an id', () => {
    for (const type of ['engagement', 'task', 'client', 'lead', 'document', 'message']) {
      expect(getEntityDestinationLabel(type)).toBeNull()
    }
  })

  it('is null for irs_authorization, unknown types, inherited keys and a missing type', () => {
    expect(getEntityDestinationLabel('irs_authorization', '9')).toBeNull()
    expect(getEntityDestinationLabel('unknown_type', '10')).toBeNull()
    expect(getEntityDestinationLabel('constructor', '11')).toBeNull()
    expect(getEntityDestinationLabel()).toBeNull()
    expect(getEntityDestinationLabel(undefined, '1')).toBeNull()
  })
})
