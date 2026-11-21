// path: frontend/src/lib/notificationPaths.test.ts
import { describe, it, expect } from 'vitest'
import { getEntityPath, isAsyncDestination } from './notificationPaths'

describe('getEntityPath', () => {
  it('returns existing paths for engagement, task, client, message', () => {
    expect(getEntityPath('engagement', '1')).toBe('/engagements/1')
    expect(getEntityPath('task', '2')).toBe('/tasks/2')
    expect(getEntityPath('client', '3')).toBe('/clients/3')
    expect(getEntityPath('message', '4')).toBe('/firm-chat')
  })

  it('returns detail paths for lead and document', () => {
    expect(getEntityPath('lead', '5')).toBe('/leads/5')
    expect(getEntityPath('document', '6')).toBe('/documents/6')
  })

  it('returns /timesheets for time_entry with and without id', () => {
    expect(getEntityPath('time_entry', '7')).toBe('/timesheets')
    expect(getEntityPath('time_entry')).toBe('/timesheets')
  })

  it('returns /staff for staff_credential with and without id', () => {
    expect(getEntityPath('staff_credential', '8')).toBe('/staff')
    expect(getEntityPath('staff_credential')).toBe('/staff')
  })

  it('returns null for irs_authorization and unknown types', () => {
    expect(getEntityPath('irs_authorization', '9')).toBeNull()
    expect(getEntityPath('unknown_type', '10')).toBeNull()
  })

  it('returns null for missing type and missing id for id-based types', () => {
    expect(getEntityPath()).toBeNull()
    expect(getEntityPath(undefined, '1')).toBeNull()
    expect(getEntityPath('engagement')).toBeNull()
    expect(getEntityPath('task')).toBeNull()
    expect(getEntityPath('client')).toBeNull()
    expect(getEntityPath('lead')).toBeNull()
    expect(getEntityPath('document')).toBeNull()
    expect(getEntityPath('message')).toBeNull()
  })

  it('returns /calendar for calendar_event with and without id', () => {
    expect(getEntityPath('calendar_event', 'some-uuid')).toBe('/calendar')
    expect(getEntityPath('calendar_event')).toBe('/calendar')
  })
})

describe('isAsyncDestination', () => {
  it('is true for irs_authorization, whose path stays null because it needs a lookup', () => {
    expect(isAsyncDestination('irs_authorization')).toBe(true)
    expect(getEntityPath('irs_authorization', '9')).toBeNull()
  })

  it('is false for synchronous types, unknown types, inherited keys and a missing type', () => {
    for (const type of ['engagement', 'task', 'client', 'lead', 'document', 'message', 'time_entry', 'staff_credential', 'calendar_event']) {
      expect(isAsyncDestination(type)).toBe(false)
    }
    expect(isAsyncDestination('unknown_type')).toBe(false)
    expect(isAsyncDestination('constructor')).toBe(false)
    expect(isAsyncDestination()).toBe(false)
    expect(isAsyncDestination('')).toBe(false)
  })
})
