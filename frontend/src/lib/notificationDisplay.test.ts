// path: frontend/src/lib/notificationDisplay.test.ts
import { describe, it, expect } from 'vitest'
import {
  DAY_GROUP_LABELS,
  NOTIFICATION_TYPE_LABELS,
  dedupeById,
  getDayGroup,
  getNotificationTypeLabel,
  humanizeNotificationType,
  splitDeleteRequestBody,
} from './notificationDisplay'

const EXPECTED_LABELS: Array<[string, string]> = [
  ['task_assigned', 'Task assigned'],
  ['doc_request_ready', 'Document request'],
  ['esign_needed', 'Signature needed'],
  ['payment_due', 'Payment due'],
  ['system', 'General'],
  ['deadline_alert', 'Deadline alert'],
  ['irs_auth_expiry', 'IRS authorization expiring'],
  ['irs_auth_missing', 'IRS authorization missing'],
  ['extension_deadline', 'Extension deadline'],
  ['client_anniversary', 'Client anniversary'],
  ['document_expiry_alert', 'Document expiring'],
  ['peer_network_mention', 'Peer Network'],
  ['lead_replied', 'Lead replied'],
  ['nurture_hold_for_approval', 'Approval needed'],
  ['lead_hot_alert', 'Hot lead'],
  ['nurture_dead_end_reached', 'Lead needs attention'],
]

describe('getNotificationTypeLabel', () => {
  it('covers exactly the 16 real notification types', () => {
    expect(Object.keys(NOTIFICATION_TYPE_LABELS).sort()).toEqual(
      EXPECTED_LABELS.map(([k]) => k).sort(),
    )
    expect(EXPECTED_LABELS).toHaveLength(16)
  })

  it.each(EXPECTED_LABELS)('labels %s as %s', (type, label) => {
    expect(getNotificationTypeLabel(type)).toBe(label)
  })

  it('humanizes an unknown type: underscores and dots become spaces, first letter capitalized', () => {
    expect(getNotificationTypeLabel('some_new_type')).toBe('Some new type')
    expect(getNotificationTypeLabel('invoice.paid')).toBe('Invoice paid')
    expect(humanizeNotificationType('task.assigned_late')).toBe('Task assigned late')
    expect(getNotificationTypeLabel('')).toBe('')
  })

  it('does not treat inherited object keys as labels', () => {
    expect(getNotificationTypeLabel('constructor')).toBe('Constructor')
    expect(getNotificationTypeLabel('toString')).toBe('ToString')
  })
})

describe('getDayGroup', () => {
  const iso = (d: Date) => d.toISOString()

  it('labels the four groups', () => {
    expect(DAY_GROUP_LABELS).toEqual({
      today: 'Today',
      yesterday: 'Yesterday',
      last7: 'Last 7 days',
      older: 'Older',
    })
  })

  it('same calendar day is today, even at 00:05 against a noon now', () => {
    const now = new Date(2026, 10, 2, 12, 0)
    expect(getDayGroup(iso(new Date(2026, 10, 2, 0, 5)), now)).toBe('today')
    expect(getDayGroup(iso(new Date(2026, 10, 2, 11, 59)), now)).toBe('today')
  })

  it('the previous calendar day is yesterday', () => {
    const now = new Date(2026, 10, 2, 12, 0)
    expect(getDayGroup(iso(new Date(2026, 10, 1, 9, 0)), now)).toBe('yesterday')
  })

  it('6 days ago is last7 and 8 days ago is older; 7 days ago is last7', () => {
    const now = new Date(2026, 10, 2, 12, 0)
    expect(getDayGroup(iso(new Date(2026, 9, 27, 12, 0)), now)).toBe('last7')
    expect(getDayGroup(iso(new Date(2026, 9, 26, 12, 0)), now)).toBe('last7')
    expect(getDayGroup(iso(new Date(2026, 9, 25, 12, 0)), now)).toBe('older')
  })

  it('late last night is yesterday even when only one hour has passed (DST fall back day)', () => {
    const now = new Date(2026, 10, 2, 0, 30)
    expect(getDayGroup(iso(new Date(2026, 10, 1, 23, 30)), now)).toBe('yesterday')
  })

  it('late last night is yesterday on the spring forward day too', () => {
    const now = new Date(2026, 2, 9, 0, 30)
    expect(getDayGroup(iso(new Date(2026, 2, 8, 23, 30)), now)).toBe('yesterday')
  })

  it('counts calendar days across the DST change, not 24 hour blocks', () => {
    const now = new Date(2026, 10, 9, 0, 30)
    expect(getDayGroup(iso(new Date(2026, 10, 2, 23, 30)), now)).toBe('last7')
    expect(getDayGroup(iso(new Date(2026, 10, 1, 23, 30)), now)).toBe('older')
  })

  it('a timestamp later than now counts as today, and an unparseable one as older', () => {
    const now = new Date(2026, 10, 2, 12, 0)
    expect(getDayGroup(iso(new Date(2026, 10, 3, 9, 0)), now)).toBe('today')
    expect(getDayGroup('not a date', now)).toBe('older')
  })
})

describe('splitDeleteRequestBody', () => {
  const T = 'Delete request'
  const E = 'calendar_event'

  it('returns the body unchanged when there is no reason', () => {
    const body = 'Sam Lee has requested to delete "Team lunch".'
    expect(splitDeleteRequestBody(T, body, E)).toEqual({ main: body, reason: null })
  })

  it('splits off a reason after the closing quote and period', () => {
    const body = 'Sam Lee has requested to delete "Team lunch". Double booked with the audit.'
    expect(splitDeleteRequestBody(T, body, E)).toEqual({
      main: 'Sam Lee has requested to delete "Team lunch".',
      reason: 'Double booked with the audit.',
    })
  })

  it('handles an event title that contains quotes and a period', () => {
    const body = 'Sam Lee has requested to delete "Meet "Bob" at 3.". Moved to Friday.'
    expect(splitDeleteRequestBody(T, body, E)).toEqual({
      main: 'Sam Lee has requested to delete "Meet "Bob" at 3.".',
      reason: 'Moved to Friday.',
    })
  })

  it('leaves the body unchanged when the sentence end is ambiguous', () => {
    const body = 'Sam Lee has requested to delete "Q4 "kickoff". Review". Too early.'
    expect(splitDeleteRequestBody(T, body, E)).toEqual({ main: body, reason: null })
  })

  it('leaves other notifications unchanged', () => {
    const body = 'Sam Lee has requested to delete "Team lunch". Double booked.'
    expect(splitDeleteRequestBody('General', body, E)).toEqual({ main: body, reason: null })
    expect(splitDeleteRequestBody(T, body, 'task')).toEqual({ main: body, reason: null })
    expect(splitDeleteRequestBody(T, body, undefined)).toEqual({ main: body, reason: null })
  })

  it('leaves an unparseable delete request body unchanged', () => {
    const body = 'Something else entirely.'
    expect(splitDeleteRequestBody(T, body, E)).toEqual({ main: body, reason: null })
  })
})

describe('dedupeById', () => {
  it('keeps the first occurrence of each id and preserves order', () => {
    const rows = [
      { id: 'a', n: 1 },
      { id: 'b', n: 2 },
      { id: 'a', n: 3 },
      { id: 'c', n: 4 },
      { id: 'b', n: 5 },
    ]
    expect(dedupeById(rows)).toEqual([
      { id: 'a', n: 1 },
      { id: 'b', n: 2 },
      { id: 'c', n: 4 },
    ])
  })

  it('returns an empty list for an empty list', () => {
    expect(dedupeById([])).toEqual([])
  })
})
