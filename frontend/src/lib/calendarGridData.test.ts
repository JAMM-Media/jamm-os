// path: frontend/src/lib/calendarGridData.test.ts
import { describe, it, expect } from 'vitest'
import {
  FALLBACK_EVENT_COLOR,
  hasOffset,
  buildGridInputs,
  isValidTimeZone,
  formatDayTitle,
} from './calendarGridData'
import { zonedDateStr } from './calendarTime'
import { buildGridDays } from './calendarGrid'
import type { PageEvent } from './calendarGridData'

// ---------------------------------------------------------------------------
// hasOffset
// ---------------------------------------------------------------------------

describe('hasOffset', () => {
  it('returns true for ISO strings with Z or colon offset', () => {
    expect(hasOffset('2026-10-15T14:00:00Z')).toBe(true)
    expect(hasOffset('2026-10-15T14:00:00.000Z')).toBe(true)
    expect(hasOffset('2026-10-15T09:00:00-04:00')).toBe(true)
    expect(hasOffset('2026-10-15T19:30:00+05:30')).toBe(true)
  })

  it('returns false for strings without Z or colon offset', () => {
    expect(hasOffset('2026-10-15T09:00:00')).toBe(false)
    // Outlook format: 7 fractional digits, no offset
    expect(hasOffset('2026-10-15T09:00:00.0000000')).toBe(false)
    // Date-only string
    expect(hasOffset('2026-10-15')).toBe(false)
    // Empty string
    expect(hasOffset('')).toBe(false)
    // Garbage
    expect(hasOffset('garbage')).toBe(false)
    // Offset without colon
    expect(hasOffset('2026-10-15T09:00:00+0530')).toBe(false)
  })

  it('returns false for strings that pass the pattern but are unparseable', () => {
    // Month 13 is invalid; Date.parse returns NaN
    expect(hasOffset('2026-13-45T09:00:00Z')).toBe(false)
  })

  it('cross-check: every string where hasOffset is true does not throw in calendarTime', () => {
    const cases = [
      { s: '2026-10-15T14:00:00Z', expected: true },
      { s: '2026-10-15T14:00:00.000Z', expected: true },
      { s: '2026-10-15T09:00:00-04:00', expected: true },
      { s: '2026-10-15T19:30:00+05:30', expected: true },
      { s: '2026-10-15T09:00:00', expected: false },
      { s: '2026-10-15T09:00:00.0000000', expected: false },
      { s: '2026-10-15', expected: false },
      { s: '', expected: false },
      { s: 'garbage', expected: false },
      { s: '2026-10-15T09:00:00+0530', expected: false },
      { s: '2026-13-45T09:00:00Z', expected: false },
    ]
    for (const { s, expected } of cases) {
      expect(hasOffset(s), `hasOffset('${s}')`).toBe(expected)
      if (expected) {
        // If hasOffset is true, calendarTime must not throw
        expect(() => zonedDateStr(s, 'UTC'), `zonedDateStr('${s}', 'UTC')`).not.toThrow()
      }
    }
  })
})

// ---------------------------------------------------------------------------
// buildGridInputs
// ---------------------------------------------------------------------------

const COLORS = {
  deadline: '#B4534B',
  extension: '#B07D3A',
  task: '#3F6E9A',
  meeting: '#4E8A6B',
  holiday: '#8A94A3',
}

describe('buildGridInputs', () => {
  it('event with valid offsets goes to timed with correct fields', () => {
    const events: PageEvent[] = [{
      id: 'ev1',
      title: 'Client Call',
      date: '2026-10-15',
      type: 'meeting',
      startAt: '2026-10-15T13:00:00-04:00',
      endAt: '2026-10-15T14:00:00-04:00',
    }]
    const { timed, allDay } = buildGridInputs(events, COLORS)
    expect(timed).toHaveLength(1)
    expect(allDay).toHaveLength(0)
    expect(timed[0]).toEqual({
      id: 'ev1',
      title: 'Client Call',
      startAt: '2026-10-15T13:00:00-04:00',
      endAt: '2026-10-15T14:00:00-04:00',
      color: COLORS.meeting,
    })
  })

  it('event without startAt or endAt goes to allDay', () => {
    const events: PageEvent[] = [{
      id: 'ev2', title: 'Holiday', date: '2026-10-15', type: 'holiday',
    }]
    const { timed, allDay } = buildGridInputs(events, COLORS)
    expect(timed).toHaveLength(0)
    expect(allDay[0]!.id).toBe('ev2')
    expect(allDay[0]!.date).toBe('2026-10-15')
  })

  it('event with naive timestamps (no offset) goes to allDay', () => {
    const events: PageEvent[] = [{
      id: 'ev3', title: 'Outlook Event', date: '2026-10-15', type: 'meeting',
      startAt: '2026-10-15T14:00:00.0000000',
      endAt: '2026-10-15T15:00:00.0000000',
    }]
    const { timed, allDay } = buildGridInputs(events, COLORS)
    expect(timed).toHaveLength(0)
    expect(allDay[0]!.date).toBe('2026-10-15')
  })

  it('Outlook style event goes to allDay with correct date, never to timed', () => {
    // Outlook timestamps carry no offset (e.g. "2026-10-15T09:00:00.0000000").
    // They are intentionally not placed on the time grid until the backend supplies one.
    const events: PageEvent[] = [{
      id: 'ev-outlook',
      title: 'Outlook Meeting',
      date: '2026-10-15',
      type: 'meeting',
      startAt: '2026-10-15T09:00:00.0000000',
      endAt: '2026-10-15T10:00:00.0000000',
    }]
    const { timed, allDay } = buildGridInputs(events, COLORS)
    expect(timed).toHaveLength(0)
    expect(allDay).toHaveLength(1)
    expect(allDay[0]!.id).toBe('ev-outlook')
    expect(allDay[0]!.date).toBe('2026-10-15')
  })

  it('event with end equal to start goes to allDay', () => {
    const events: PageEvent[] = [{
      id: 'ev4', title: 'Zero Duration', date: '2026-10-15', type: 'meeting',
      startAt: '2026-10-15T14:00:00Z',
      endAt: '2026-10-15T14:00:00Z',
    }]
    const { timed, allDay } = buildGridInputs(events, COLORS)
    expect(timed).toHaveLength(0)
    expect(allDay).toHaveLength(1)
  })

  it('event with end before start goes to allDay', () => {
    const events: PageEvent[] = [{
      id: 'ev5', title: 'Backwards', date: '2026-10-15', type: 'meeting',
      startAt: '2026-10-15T15:00:00Z',
      endAt: '2026-10-15T14:00:00Z',
    }]
    const { timed, allDay } = buildGridInputs(events, COLORS)
    expect(timed).toHaveLength(0)
    expect(allDay).toHaveLength(1)
  })

  it('event with startAt but no endAt goes to allDay', () => {
    const events: PageEvent[] = [{
      id: 'ev6', title: 'Partial', date: '2026-10-15', type: 'meeting',
      startAt: '2026-10-15T14:00:00Z',
    }]
    const { timed, allDay } = buildGridInputs(events, COLORS)
    expect(timed).toHaveLength(0)
    expect(allDay).toHaveLength(1)
  })

  it('deadline, extension, task and holiday go to allDay with their type colors', () => {
    const events: PageEvent[] = [
      { id: 'd1', title: 'Filing', date: '2026-10-15', type: 'deadline' },
      { id: 'd2', title: 'Extension', date: '2026-10-15', type: 'extension' },
      { id: 'd3', title: 'Task', date: '2026-10-15', type: 'task' },
      { id: 'd4', title: 'Holiday', date: '2026-10-15', type: 'holiday' },
    ]
    const { timed, allDay } = buildGridInputs(events, COLORS)
    expect(timed).toHaveLength(0)
    expect(allDay).toHaveLength(4)
    expect(allDay[0]!.color).toBe(COLORS.deadline)
    expect(allDay[1]!.color).toBe(COLORS.extension)
    expect(allDay[2]!.color).toBe(COLORS.task)
    expect(allDay[3]!.color).toBe(COLORS.holiday)
  })

  it('first duplicate id wins when both are timed', () => {
    const events: PageEvent[] = [
      { id: 'dup', title: 'First', date: '2026-10-15', type: 'meeting', startAt: '2026-10-15T13:00:00Z', endAt: '2026-10-15T14:00:00Z' },
      { id: 'dup', title: 'Second', date: '2026-10-15', type: 'meeting', startAt: '2026-10-15T15:00:00Z', endAt: '2026-10-15T16:00:00Z' },
    ]
    const { timed, allDay } = buildGridInputs(events, COLORS)
    expect(timed).toHaveLength(1)
    expect(timed[0]!.title).toBe('First')
    expect(allDay).toHaveLength(0)
  })

  it('first duplicate id wins when one timed and one allDay share the same id', () => {
    const events: PageEvent[] = [
      { id: 'dup2', title: 'Timed First', date: '2026-10-15', type: 'meeting', startAt: '2026-10-15T13:00:00Z', endAt: '2026-10-15T14:00:00Z' },
      { id: 'dup2', title: 'AllDay Second', date: '2026-10-15', type: 'holiday' },
    ]
    const { timed, allDay } = buildGridInputs(events, COLORS)
    expect(timed).toHaveLength(1)
    expect(timed[0]!.title).toBe('Timed First')
    expect(allDay).toHaveLength(0)
  })

  it('input order is preserved within each list', () => {
    const events: PageEvent[] = [
      { id: 'a', title: 'A', date: '2026-10-15', type: 'meeting', startAt: '2026-10-15T13:00:00Z', endAt: '2026-10-15T14:00:00Z' },
      { id: 'b', title: 'B', date: '2026-10-15', type: 'holiday' },
      { id: 'c', title: 'C', date: '2026-10-15', type: 'meeting', startAt: '2026-10-15T15:00:00Z', endAt: '2026-10-15T16:00:00Z' },
      { id: 'd', title: 'D', date: '2026-10-15', type: 'task' },
    ]
    const { timed, allDay } = buildGridInputs(events, COLORS)
    expect(timed.map(x => x.id)).toEqual(['a', 'c'])
    expect(allDay.map(x => x.id)).toEqual(['b', 'd'])
  })

  it('unknown event type gets FALLBACK_EVENT_COLOR', () => {
    const events: PageEvent[] = [{
      id: 'u1', title: 'Unknown', date: '2026-10-15', type: 'custom',
    }]
    const { allDay } = buildGridInputs(events, COLORS)
    expect(allDay[0]!.color).toBe(FALLBACK_EVENT_COLOR)
  })

  it('invalid color strings all give FALLBACK_EVENT_COLOR', () => {
    const badColors = ['red', '#12', '#GGGGGG', '']
    for (const bad of badColors) {
      const { allDay } = buildGridInputs(
        [{ id: 'x', title: 'T', date: '2026-10-15', type: 'meeting' }],
        { meeting: bad }
      )
      expect(allDay[0]!.color, `color='${bad}'`).toBe(FALLBACK_EVENT_COLOR)
    }
  })

  it('valid color #B4534B is kept', () => {
    const { allDay } = buildGridInputs(
      [{ id: 'x', title: 'T', date: '2026-10-15', type: 'meeting' }],
      { meeting: '#B4534B' }
    )
    expect(allDay[0]!.color).toBe('#B4534B')
  })

  it('user override color is used when valid', () => {
    const override = '#123ABC'
    const { allDay } = buildGridInputs(
      [{ id: 'x', title: 'T', date: '2026-10-15', type: 'deadline' }],
      { deadline: override }
    )
    expect(allDay[0]!.color).toBe(override)
  })

  it('empty input returns two empty lists', () => {
    const { timed, allDay } = buildGridInputs([], COLORS)
    expect(timed).toEqual([])
    expect(allDay).toEqual([])
  })

  it('input array and its objects are not mutated', () => {
    const events: PageEvent[] = [
      { id: 'e1', title: 'Meeting', date: '2026-10-15', type: 'meeting', startAt: '2026-10-15T13:00:00Z', endAt: '2026-10-15T14:00:00Z' },
    ]
    const copy = events.map(e => ({ ...e }))
    buildGridInputs(events, COLORS)
    expect(events[0]).toEqual(copy[0])
    expect(events.length).toBe(1)
  })

  it('titles with angle brackets pass through unchanged', () => {
    const title = '<script> & "test"'
    const events: PageEvent[] = [{ id: 'x', title, date: '2026-10-15', type: 'meeting' }]
    const { allDay } = buildGridInputs(events, COLORS)
    expect(allDay[0]!.title).toBe(title)
  })
})

// ---------------------------------------------------------------------------
// isValidTimeZone
// ---------------------------------------------------------------------------

describe('isValidTimeZone', () => {
  it('returns true for known valid zones', () => {
    expect(isValidTimeZone('America/New_York')).toBe(true)
    expect(isValidTimeZone('Asia/Kolkata')).toBe(true)
    expect(isValidTimeZone('UTC')).toBe(true)
  })

  it('returns false for invalid zones and empty string', () => {
    expect(isValidTimeZone('Not/AZone')).toBe(false)
    expect(isValidTimeZone('')).toBe(false)
    // Common typo: no underscore between New and York
    expect(isValidTimeZone('America/NewYork')).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// formatDayTitle
// ---------------------------------------------------------------------------

describe('formatDayTitle', () => {
  // Weekday verification (from calendarGrid test knowledge):
  // Oct 11 2026 = Sunday, so Oct 15 = Thursday, Oct 14 = Wednesday
  // Dec 31 2026: Nov 1 = Sunday, Dec 1 = Tuesday (Nov has 30 days, +2 days),
  // Dec 31 = Dec 1 + 30 = Tuesday + 30 days = Tuesday + 4*7 + 2 = Thursday
  // Jan 1 2027: Dec 31 2026 = Thursday, so Jan 1 2027 = Friday

  it('2026-10-15 gives "Thursday, October 15, 2026"', () => {
    expect(formatDayTitle('2026-10-15')).toBe('Thursday, October 15, 2026')
  })

  it('2026-12-31 gives "Thursday, December 31, 2026"', () => {
    expect(formatDayTitle('2026-12-31')).toBe('Thursday, December 31, 2026')
  })

  it('2027-01-01 gives "Friday, January 1, 2027"', () => {
    expect(formatDayTitle('2027-01-01')).toBe('Friday, January 1, 2027')
  })

  it('malformed dateStr throws RangeError', () => {
    expect(() => formatDayTitle('2026-10-15x')).toThrow(RangeError)
  })

  it('empty string throws RangeError', () => {
    expect(() => formatDayTitle('')).toThrow(RangeError)
  })
})

// ---------------------------------------------------------------------------
// End to end
// ---------------------------------------------------------------------------

describe('end-to-end: buildGridInputs into buildGridDays', () => {
  it('event 2026-10-15 09:00-04:00 to 10:00-04:00 appears with startMin 540 and endMin 600', () => {
    // 09:00 at UTC-4 is 13:00Z, which is 09:00 in America/New_York, 9 * 60 = 540
    // 10:00 at UTC-4 is 14:00Z, which is 10:00 in America/New_York, 10 * 60 = 600
    const events: PageEvent[] = [{
      id: 'ev-e2e',
      title: 'Morning Meeting',
      date: '2026-10-15',
      type: 'meeting',
      startAt: '2026-10-15T09:00:00-04:00',
      endAt: '2026-10-15T10:00:00-04:00',
    }]
    const { timed, allDay } = buildGridInputs(events, COLORS)
    const days = ['2026-10-14', '2026-10-15', '2026-10-16']
    const gridDays = buildGridDays({
      dates: days,
      timed,
      allDay,
      timeZone: 'America/New_York',
    })
    const oct15 = gridDays.find(d => d.dateStr === '2026-10-15')!
    expect(oct15.blocks).toHaveLength(1)
    expect(oct15.blocks[0]!.startMin).toBe(540)
    expect(oct15.blocks[0]!.endMin).toBe(600)
  })

  it('event 2026-10-15 19:30+05:30 to 20:30+05:30 appears with startMin 1170 and endMin 1230 in Asia/Kolkata', () => {
    // 19:30 at +05:30 is 14:00Z, which is 19:30 in Asia/Kolkata, 19 * 60 + 30 = 1170
    // 20:30 at +05:30 is 15:00Z, which is 20:30 in Asia/Kolkata, 20 * 60 + 30 = 1230
    const events: PageEvent[] = [{
      id: 'ev-kolkata',
      title: 'Kolkata Meeting',
      date: '2026-10-15',
      type: 'meeting',
      startAt: '2026-10-15T19:30:00+05:30',
      endAt: '2026-10-15T20:30:00+05:30',
    }]
    const { timed, allDay } = buildGridInputs(events, COLORS)
    const days = ['2026-10-14', '2026-10-15', '2026-10-16']
    const gridDays = buildGridDays({
      dates: days,
      timed,
      allDay,
      timeZone: 'Asia/Kolkata',
    })
    const oct15 = gridDays.find(d => d.dateStr === '2026-10-15')!
    expect(oct15.blocks).toHaveLength(1)
    expect(oct15.blocks[0]!.startMin).toBe(1170)
    expect(oct15.blocks[0]!.endMin).toBe(1230)
  })
})
