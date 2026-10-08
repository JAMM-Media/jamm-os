// path: frontend/src/lib/calendarNative.test.ts
import { describe, it, expect } from 'vitest'
import {
  NATIVE_ID_PREFIX,
  mapNativeEvents,
  dateRangeForView,
  rangeToInstants,
} from './calendarNative'
import { buildGridInputs, hasOffset } from './calendarGridData'
import { buildGridDays } from './calendarGrid'
import type { CalendarEvent } from './api/calendarEvents'
import type { NativeCalEvent } from './calendarNative'

// ---------------------------------------------------------------------------
// Test helper
// ---------------------------------------------------------------------------

function makeEvent(overrides: Partial<CalendarEvent> = {}): CalendarEvent {
  return {
    id: 'backend-id-1',
    title: 'Client Call',
    startAt: '2026-10-15T13:00:00Z',
    endAt: '2026-10-15T14:00:00Z',
    eventTimezone: 'America/New_York',
    categoryId: 'cat-1',
    categoryName: 'Tax',
    categoryColor: '#3F6E9A',
    clientId: 'client-1',
    clientName: 'Acme Corp',
    ownerUserId: 'user-1',
    ownerName: 'Alice Smith',
    createdBy: 'user-1',
    createdAt: '2026-10-01T00:00:00Z',
    updatedAt: '2026-10-01T00:00:00Z',
    deletedAt: null,
    ...overrides,
  }
}

const NY = 'America/New_York'
const KOL = 'Asia/Kolkata'

// ---------------------------------------------------------------------------
// mapNativeEvents
// ---------------------------------------------------------------------------

describe('mapNativeEvents', () => {
  it('maps all fields with nat- prefix, type meeting, assignedTo from ownerUserId', () => {
    const ev = makeEvent()
    const [result] = mapNativeEvents([ev], NY)
    expect(result!.id).toBe(NATIVE_ID_PREFIX + 'backend-id-1')
    expect(result!.title).toBe('Client Call')
    expect(result!.type).toBe('meeting')
    expect(result!.assignedTo).toBe('user-1')
    expect(result!.startAt).toBe('2026-10-15T13:00:00Z')
    expect(result!.endAt).toBe('2026-10-15T14:00:00Z')
    expect(result!.color).toBe('#3F6E9A')
    expect(result!.categoryName).toBe('Tax')
    expect(result!.clientName).toBe('Acme Corp')
    expect(result!.ownerName).toBe('Alice Smith')
  })

  it('date is from the firm zone, not UTC: 2026-10-16T02:00:00Z is Oct 15 in NY (22:00 EDT)', () => {
    // 02:00 UTC - 4h = 22:00 EDT on Oct 15
    const ev = makeEvent({ startAt: '2026-10-16T02:00:00Z', endAt: '2026-10-16T03:00:00Z' })
    const [r] = mapNativeEvents([ev], NY)
    expect(r!.date).toBe('2026-10-15')
  })

  it('date is from the firm zone, not UTC: 2026-10-16T02:00:00Z is Oct 16 in Asia/Kolkata (07:30 IST)', () => {
    // 02:00 UTC + 5:30 = 07:30 IST on Oct 16
    const ev = makeEvent({ startAt: '2026-10-16T02:00:00Z', endAt: '2026-10-16T03:00:00Z' })
    const [r] = mapNativeEvents([ev], KOL)
    expect(r!.date).toBe('2026-10-16')
  })

  it('date is from the firm zone: 2026-10-15T03:30:00Z is Oct 14 in NY (23:30 EDT on the 14th)', () => {
    // 03:30 UTC - 4h = 23:30 EDT on Oct 14
    const ev = makeEvent({ startAt: '2026-10-15T03:30:00Z', endAt: '2026-10-15T04:30:00Z' })
    const [r] = mapNativeEvents([ev], NY)
    expect(r!.date).toBe('2026-10-14')
  })

  it('accepts a +00:00 offset form', () => {
    const ev = makeEvent({ startAt: '2026-10-15T13:00:00+00:00', endAt: '2026-10-15T14:00:00+00:00' })
    const [r] = mapNativeEvents([ev], NY)
    expect(r).toBeDefined()
    expect(r!.startAt).toBe('2026-10-15T13:00:00+00:00')
  })

  it('null category gives color null and categoryName null', () => {
    const ev = makeEvent({ categoryId: null, categoryName: null, categoryColor: null })
    const [r] = mapNativeEvents([ev], NY)
    expect(r!.color).toBeNull()
    expect(r!.categoryName).toBeNull()
  })

  it('null owner gives assignedTo null and ownerName null', () => {
    const ev = makeEvent({ ownerUserId: null, ownerName: null })
    const [r] = mapNativeEvents([ev], NY)
    expect(r!.assignedTo).toBeNull()
    expect(r!.ownerName).toBeNull()
  })

  it('invalid category colors give null; #3F6E9A is kept', () => {
    for (const bad of ['red', '#12', '', '#GGGGGG']) {
      const ev = makeEvent({ id: `id-${bad}`, categoryColor: bad })
      const [r] = mapNativeEvents([ev], NY)
      expect(r!.color).toBeNull()
    }
    const ev = makeEvent({ categoryColor: '#3F6E9A' })
    const [r] = mapNativeEvents([ev], NY)
    expect(r!.color).toBe('#3F6E9A')
  })

  it('skips without throwing: deletedAt set', () => {
    const ev = makeEvent({ deletedAt: '2026-10-02T00:00:00Z' })
    expect(mapNativeEvents([ev], NY)).toEqual([])
  })

  it('skips without throwing: naive startAt (no offset)', () => {
    const ev = makeEvent({ startAt: '2026-10-15T09:00:00' })
    expect(mapNativeEvents([ev], NY)).toEqual([])
  })

  it('skips without throwing: naive endAt (no offset)', () => {
    const ev = makeEvent({ endAt: '2026-10-15T14:00:00' })
    expect(mapNativeEvents([ev], NY)).toEqual([])
  })

  it('skips without throwing: end equal to start', () => {
    const ev = makeEvent({ endAt: '2026-10-15T13:00:00Z' })
    expect(mapNativeEvents([ev], NY)).toEqual([])
  })

  it('skips without throwing: end before start', () => {
    const ev = makeEvent({ endAt: '2026-10-15T12:00:00Z' })
    expect(mapNativeEvents([ev], NY)).toEqual([])
  })

  it('repeated backend id keeps the first', () => {
    const ev1 = makeEvent({ title: 'First' })
    const ev2 = makeEvent({ title: 'Second' })
    const result = mapNativeEvents([ev1, ev2], NY)
    expect(result).toHaveLength(1)
    expect(result[0]!.title).toBe('First')
  })

  it('preserves input order', () => {
    const ev1 = makeEvent({ id: 'id-a', title: 'A' })
    const ev2 = makeEvent({ id: 'id-b', title: 'B' })
    const result = mapNativeEvents([ev1, ev2], NY)
    expect(result[0]!.title).toBe('A')
    expect(result[1]!.title).toBe('B')
  })

  it('does not mutate the input array or objects', () => {
    const ev = makeEvent()
    const original = JSON.stringify(ev)
    const arr = [ev]
    mapNativeEvents(arr, NY)
    expect(JSON.stringify(ev)).toBe(original)
    expect(arr).toHaveLength(1)
  })

  it('empty input with an invalid zone returns []', () => {
    expect(mapNativeEvents([], 'Not/AZone')).toEqual([])
  })

  it('non-empty input with an invalid zone throws RangeError', () => {
    const ev = makeEvent()
    expect(() => mapNativeEvents([ev], 'Not/AZone')).toThrow(RangeError)
  })
})

// ---------------------------------------------------------------------------
// dateRangeForView
// ---------------------------------------------------------------------------

describe('dateRangeForView', () => {
  it('month 2026-10-01 gives 2026-10-01 to 2026-10-31', () => {
    const r = dateRangeForView({ view: 'month', cursorDateStr: '2026-10-01', agendaStartStr: '', agendaEndStr: '' })
    expect(r).toEqual({ startStr: '2026-10-01', endStr: '2026-10-31' })
  })

  it('month 2026-10-15 gives 2026-10-01 to 2026-10-31', () => {
    const r = dateRangeForView({ view: 'month', cursorDateStr: '2026-10-15', agendaStartStr: '', agendaEndStr: '' })
    expect(r).toEqual({ startStr: '2026-10-01', endStr: '2026-10-31' })
  })

  it('month 2026-10-31 gives 2026-10-01 to 2026-10-31', () => {
    const r = dateRangeForView({ view: 'month', cursorDateStr: '2026-10-31', agendaStartStr: '', agendaEndStr: '' })
    expect(r).toEqual({ startStr: '2026-10-01', endStr: '2026-10-31' })
  })

  it('February 2026 gives 2026-02-01 to 2026-02-28', () => {
    const r = dateRangeForView({ view: 'month', cursorDateStr: '2026-02-15', agendaStartStr: '', agendaEndStr: '' })
    expect(r).toEqual({ startStr: '2026-02-01', endStr: '2026-02-28' })
  })

  it('February 2028 gives 2028-02-01 to 2028-02-29 (2028 is a leap year)', () => {
    const r = dateRangeForView({ view: 'month', cursorDateStr: '2028-02-15', agendaStartStr: '', agendaEndStr: '' })
    expect(r).toEqual({ startStr: '2028-02-01', endStr: '2028-02-29' })
  })

  it('September gives 30 as the last day', () => {
    const r = dateRangeForView({ view: 'month', cursorDateStr: '2026-09-15', agendaStartStr: '', agendaEndStr: '' })
    expect(r.endStr).toBe('2026-09-30')
  })

  it('December gives 31 as the last day', () => {
    const r = dateRangeForView({ view: 'month', cursorDateStr: '2026-12-15', agendaStartStr: '', agendaEndStr: '' })
    expect(r.endStr).toBe('2026-12-31')
  })

  it('week for Thursday 2026-10-15 gives 2026-10-11 to 2026-10-17', () => {
    // Oct 15 is Thursday. Sunday of that week is Oct 11. Saturday is Oct 17.
    const r = dateRangeForView({ view: 'week', cursorDateStr: '2026-10-15', agendaStartStr: '', agendaEndStr: '' })
    expect(r).toEqual({ startStr: '2026-10-11', endStr: '2026-10-17' })
  })

  it('week for Sunday 2026-10-11 gives the same range 2026-10-11 to 2026-10-17', () => {
    // Oct 11 is Sunday, so it is the start of its own week.
    const r = dateRangeForView({ view: 'week', cursorDateStr: '2026-10-11', agendaStartStr: '', agendaEndStr: '' })
    expect(r).toEqual({ startStr: '2026-10-11', endStr: '2026-10-17' })
  })

  it('week for 2026-12-30 gives 2026-12-27 to 2027-01-02', () => {
    // Dec 30, 2026 is Wednesday. Sunday of that week is Dec 27. Saturday is Jan 2, 2027.
    // Dec has 31 days: Dec 27 + 6 = Jan 2, 2027.
    const r = dateRangeForView({ view: 'week', cursorDateStr: '2026-12-30', agendaStartStr: '', agendaEndStr: '' })
    expect(r).toEqual({ startStr: '2026-12-27', endStr: '2027-01-02' })
  })

  it('day gives cursorDateStr for both start and end', () => {
    const r = dateRangeForView({ view: 'day', cursorDateStr: '2026-10-15', agendaStartStr: '', agendaEndStr: '' })
    expect(r).toEqual({ startStr: '2026-10-15', endStr: '2026-10-15' })
  })

  it('agenda passes agendaStartStr and agendaEndStr through even when cursorDateStr is garbage', () => {
    const r = dateRangeForView({ view: 'agenda', cursorDateStr: 'garbage', agendaStartStr: '2026-10-01', agendaEndStr: '2026-10-14' })
    expect(r).toEqual({ startStr: '2026-10-01', endStr: '2026-10-14' })
  })

  it('malformed cursors throw RangeError for month', () => {
    for (const bad of ['', '2026-10', '2026-13-01', '2026-10-32', '2026-10-15x']) {
      expect(() => dateRangeForView({ view: 'month', cursorDateStr: bad, agendaStartStr: '', agendaEndStr: '' })).toThrow(RangeError)
    }
  })

  it('malformed cursors throw RangeError for week', () => {
    for (const bad of ['', '2026-10', '2026-13-01', '2026-10-32', '2026-10-15x']) {
      expect(() => dateRangeForView({ view: 'week', cursorDateStr: bad, agendaStartStr: '', agendaEndStr: '' })).toThrow(RangeError)
    }
  })

  it('malformed cursors throw RangeError for day', () => {
    for (const bad of ['', '2026-10', '2026-13-01', '2026-10-32', '2026-10-15x']) {
      expect(() => dateRangeForView({ view: 'day', cursorDateStr: bad, agendaStartStr: '', agendaEndStr: '' })).toThrow(RangeError)
    }
  })
})

// ---------------------------------------------------------------------------
// rangeToInstants
// ---------------------------------------------------------------------------

describe('rangeToInstants', () => {
  it('America/New_York month 2026-10-01 to 2026-10-31: from Oct 1 midnight EDT to Nov 1 midnight EDT', () => {
    // EDT is UTC-4. Clocks fall back at 02:00 on 2026-11-01 so local midnight on Nov 1
    // is still EDT. from = 2026-10-01T00:00 EDT = 2026-10-01T04:00:00.000Z.
    // to = wallTimeToInstant('2026-11-01', 0, NY) because minutes 1440 => next day minute 0.
    // Nov 1 midnight is EDT (00:00 before the 02:00 fallback) = 2026-11-01T04:00:00.000Z.
    const { from, to } = rangeToInstants('2026-10-01', '2026-10-31', NY)
    expect(from).toBe('2026-10-01T04:00:00.000Z')
    expect(to).toBe('2026-11-01T04:00:00.000Z')
  })

  it('America/New_York week 2026-10-11 to 2026-10-17: from Sunday midnight to next Sunday midnight', () => {
    // Both dates in EDT (UTC-4).
    // from = 2026-10-11T04:00:00.000Z, to = wallTimeToInstant('2026-10-18', 0, NY) = 2026-10-18T04:00:00.000Z.
    const { from, to } = rangeToInstants('2026-10-11', '2026-10-17', NY)
    expect(from).toBe('2026-10-11T04:00:00.000Z')
    expect(to).toBe('2026-10-18T04:00:00.000Z')
  })

  it('spring forward 2026-03-08 alone: 23 hours (EST midnight to EDT midnight)', () => {
    // Mar 8 midnight is EST (UTC-5): from = 2026-03-08T05:00:00.000Z.
    // Clocks spring forward at 02:00 EST to 03:00 EDT.
    // to = wallTimeToInstant('2026-03-09', 0, NY): Mar 9 midnight is EDT (UTC-4) = 2026-03-09T04:00:00.000Z.
    // Duration: 23 hours.
    const { from, to } = rangeToInstants('2026-03-08', '2026-03-08', NY)
    expect(from).toBe('2026-03-08T05:00:00.000Z')
    expect(to).toBe('2026-03-09T04:00:00.000Z')
  })

  it('fall back 2026-11-01 alone: 25 hours (EDT midnight to EST midnight)', () => {
    // Nov 1 midnight is EDT (UTC-4) because clocks fall back at 02:00: from = 2026-11-01T04:00:00.000Z.
    // to = wallTimeToInstant('2026-11-02', 0, NY): Nov 2 midnight is EST (UTC-5) = 2026-11-02T05:00:00.000Z.
    // Duration: 25 hours.
    const { from, to } = rangeToInstants('2026-11-01', '2026-11-01', NY)
    expect(from).toBe('2026-11-01T04:00:00.000Z')
    expect(to).toBe('2026-11-02T05:00:00.000Z')
  })

  it('Asia/Kolkata month 2026-10-01 to 2026-10-31: IST is UTC+5:30', () => {
    // from = midnight Oct 1 IST = 2026-09-30T18:30:00.000Z.
    // to = wallTimeToInstant('2026-11-01', 0, KOL) = midnight Nov 1 IST = 2026-10-31T18:30:00.000Z.
    const { from, to } = rangeToInstants('2026-10-01', '2026-10-31', KOL)
    expect(from).toBe('2026-09-30T18:30:00.000Z')
    expect(to).toBe('2026-10-31T18:30:00.000Z')
  })

  it('outputs satisfy hasOffset', () => {
    const { from, to } = rangeToInstants('2026-10-01', '2026-10-31', NY)
    expect(hasOffset(from)).toBe(true)
    expect(hasOffset(to)).toBe(true)
  })

  it('end before start throws RangeError', () => {
    expect(() => rangeToInstants('2026-10-15', '2026-10-01', NY)).toThrow(RangeError)
  })

  it('malformed date throws RangeError through wallTimeToInstant', () => {
    expect(() => rangeToInstants('not-a-date', '2026-10-31', NY)).toThrow(RangeError)
  })

  it('invalid zone throws RangeError', () => {
    expect(() => rangeToInstants('2026-10-01', '2026-10-31', 'Not/AZone')).toThrow(RangeError)
  })
})

// ---------------------------------------------------------------------------
// End to end: mapNativeEvents -> buildGridInputs -> buildGridDays
// ---------------------------------------------------------------------------

describe('end-to-end: mapNativeEvents into buildGridInputs into buildGridDays', () => {
  const COLORS = { meeting: '#4E8A6B' }
  const DAYS = ['2026-10-14', '2026-10-15', '2026-10-16']

  it('event with categoryColor #3F6E9A gets that color; block on 2026-10-15 with startMin 540 endMin 600', () => {
    // startAt 2026-10-15T13:00:00Z in NY: 13:00 UTC - 4h EDT = 09:00 EDT, min 9*60=540
    // endAt   2026-10-15T14:00:00Z in NY: 14:00 UTC - 4h EDT = 10:00 EDT, min 10*60=600
    const ev = makeEvent({ startAt: '2026-10-15T13:00:00Z', endAt: '2026-10-15T14:00:00Z', categoryColor: '#3F6E9A' })
    const native: NativeCalEvent[] = mapNativeEvents([ev], NY)
    const { timed, allDay } = buildGridInputs(native, COLORS)
    const days = buildGridDays({ dates: DAYS, timed, allDay, timeZone: NY })
    const oct15 = days.find(d => d.dateStr === '2026-10-15')!
    expect(oct15.blocks).toHaveLength(1)
    expect(oct15.blocks[0]!.startMin).toBe(540)
    expect(oct15.blocks[0]!.endMin).toBe(600)
    expect(timed[0]!.color).toBe('#3F6E9A')
  })

  it('second event with null categoryColor gets the type color from the colors map', () => {
    const ev = makeEvent({ id: 'id-2', startAt: '2026-10-15T13:00:00Z', endAt: '2026-10-15T14:00:00Z', categoryColor: null })
    const native: NativeCalEvent[] = mapNativeEvents([ev], NY)
    const { timed } = buildGridInputs(native, COLORS)
    expect(timed[0]!.color).toBe('#4E8A6B')
  })

  it('event with startAt 2026-10-16T02:00:00Z lands on 2026-10-15 at startMin 1320 in NY', () => {
    // 02:00 UTC - 4h EDT = 22:00 EDT on Oct 15, min 22*60=1320
    // 03:00 UTC - 4h EDT = 23:00 EDT on Oct 15, min 23*60=1380
    const ev = makeEvent({ id: 'id-3', startAt: '2026-10-16T02:00:00Z', endAt: '2026-10-16T03:00:00Z' })
    const native: NativeCalEvent[] = mapNativeEvents([ev], NY)
    const { timed, allDay } = buildGridInputs(native, COLORS)
    const days = buildGridDays({ dates: DAYS, timed, allDay, timeZone: NY })
    const oct15 = days.find(d => d.dateStr === '2026-10-15')!
    expect(oct15.blocks).toHaveLength(1)
    expect(oct15.blocks[0]!.startMin).toBe(1320)
    expect(oct15.blocks[0]!.endMin).toBe(1380)
  })
})
