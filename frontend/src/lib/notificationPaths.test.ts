// path: frontend/src/lib/notificationPaths.test.ts
import { describe, it, expect } from 'vitest'
import { getEntityPath } from './notificationPaths'

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
})
