// path: frontend/src/lib/calendarTime.test.ts
import { describe, it, expect } from 'vitest'
import {
  MINUTES_PER_DAY,
  SNAP_MINUTES,
  MIN_DISPLAY_MINUTES,
  zonedDateStr,
  minutesIntoDay,
  wallTimeToInstant,
  snapMinutes,
  daySegment,
  layoutDay,
  formatTimeLabel,
  normalizeSpaces,
  formatHourLabel,
} from './calendarTime'

// ---------------------------------------------------------------------------
// zonedDateStr and minutesIntoDay
// ---------------------------------------------------------------------------

describe('minutesIntoDay', () => {
  it('2026-10-15T14:00:00Z is 600 in America/New_York', () => {
    expect(minutesIntoDay('2026-10-15T14:00:00Z', 'America/New_York')).toBe(600)
  })

  it('2026-10-15T14:00:00Z is 420 in America/Los_Angeles', () => {
    expect(minutesIntoDay('2026-10-15T14:00:00Z', 'America/Los_Angeles')).toBe(420)
  })

  it('2026-10-15T14:00:00Z is 1170 in Asia/Kolkata (half-hour zone)', () => {
    expect(minutesIntoDay('2026-10-15T14:00:00Z', 'Asia/Kolkata')).toBe(1170)
  })

  it('instant just before local midnight gives the old date and 1439', () => {
    // 2026-10-16T03:59:00Z = 2026-10-15T23:59 EDT (UTC-4)
    expect(zonedDateStr('2026-10-16T03:59:00Z', 'America/New_York')).toBe('2026-10-15')
    expect(minutesIntoDay('2026-10-16T03:59:00Z', 'America/New_York')).toBe(1439)
  })

  it('instant at exactly local midnight gives the new date and 0', () => {
    // 2026-10-16T04:00:00Z = 2026-10-16T00:00 EDT (midnight)
    expect(zonedDateStr('2026-10-16T04:00:00Z', 'America/New_York')).toBe('2026-10-16')
    expect(minutesIntoDay('2026-10-16T04:00:00Z', 'America/New_York')).toBe(0)
  })

  it('same instant gives different date in far east zone when day has rolled over', () => {
    // 2026-10-15T14:00:00Z is Oct 15 in NY but Oct 16 in Asia/Kolkata (offset +5:30 = 19:30 local)
    expect(zonedDateStr('2026-10-15T14:00:00Z', 'America/New_York')).toBe('2026-10-15')
    expect(zonedDateStr('2026-10-15T14:00:00Z', 'Asia/Kolkata')).toBe('2026-10-15')
    // Later instant: 2026-10-15T19:30:00Z = Oct 16T01:00 in Kolkata but Oct 15 in NY
    expect(zonedDateStr('2026-10-15T20:00:00Z', 'Asia/Kolkata')).toBe('2026-10-16')
    expect(zonedDateStr('2026-10-15T20:00:00Z', 'America/New_York')).toBe('2026-10-15')
  })

  it('Date and string inputs give the same answer', () => {
    const str = '2026-10-15T14:00:00Z'
    const d = new Date(str)
    expect(minutesIntoDay(str, 'America/New_York')).toBe(minutesIntoDay(d, 'America/New_York'))
    expect(zonedDateStr(str, 'America/New_York')).toBe(zonedDateStr(d, 'America/New_York'))
  })

  it('string without offset throws an Error', () => {
    expect(() => minutesIntoDay('2026-10-15T14:00:00', 'America/New_York')).toThrow('offset')
    expect(() => zonedDateStr('2026-10-15T14:00:00', 'America/New_York')).toThrow('offset')
  })

  it('invalid zone name throws a RangeError from Intl', () => {
    expect(() => minutesIntoDay('2026-10-15T14:00:00Z', 'Not/AZone')).toThrow(RangeError)
    expect(() => zonedDateStr('2026-10-15T14:00:00Z', 'Not/AZone')).toThrow(RangeError)
  })
})

// ---------------------------------------------------------------------------
// wallTimeToInstant
// ---------------------------------------------------------------------------

describe('wallTimeToInstant', () => {
  it('round trip: 2026-10-15 at 600 in America/New_York is 2026-10-15T14:00:00.000Z', () => {
    const result = wallTimeToInstant('2026-10-15', 600, 'America/New_York')
    expect(result.toISOString()).toBe('2026-10-15T14:00:00.000Z')
  })

  it('minutes 1440 equals minutes 0 of the next date', () => {
    const a = wallTimeToInstant('2026-10-15', 1440, 'America/New_York')
    const b = wallTimeToInstant('2026-10-16', 0, 'America/New_York')
    expect(a.toISOString()).toBe(b.toISOString())
  })

  it('2026-03-08 at 150 (02:30, does not exist) resolves to 2026-03-08T07:30:00.000Z', () => {
    const result = wallTimeToInstant('2026-03-08', 150, 'America/New_York')
    expect(result.toISOString()).toBe('2026-03-08T07:30:00.000Z')
  })

  it('2026-03-08 at 90 (01:30 EST before spring forward) is 2026-03-08T06:30:00.000Z', () => {
    const result = wallTimeToInstant('2026-03-08', 90, 'America/New_York')
    expect(result.toISOString()).toBe('2026-03-08T06:30:00.000Z')
  })

  it('2026-11-01 at 90 (01:30 ambiguous) resolves to first occurrence 2026-11-01T05:30:00.000Z', () => {
    const result = wallTimeToInstant('2026-11-01', 90, 'America/New_York')
    expect(result.toISOString()).toBe('2026-11-01T05:30:00.000Z')
  })

  it('minutes -1 throws RangeError', () => {
    expect(() => wallTimeToInstant('2026-10-15', -1, 'America/New_York')).toThrow(RangeError)
  })

  it('minutes 1441 throws RangeError', () => {
    expect(() => wallTimeToInstant('2026-10-15', 1441, 'America/New_York')).toThrow(RangeError)
  })

  it('malformed date "2026-13-40" throws RangeError', () => {
    expect(() => wallTimeToInstant('2026-13-40', 0, 'America/New_York')).toThrow(RangeError)
  })

  it('round trip every 15-min step of 2026-03-08: non-gap steps match, gap steps are at or after 180', () => {
    // Gap: minutes 120, 135, 150, 165 do not exist (spring forward 2:00->3:00 = 120->180)
    const GAP_START = 120
    const GAP_END = 180
    for (let m = 0; m <= 1425; m += 15) {
      const result = wallTimeToInstant('2026-03-08', m, 'America/New_York')
      const roundTrip = minutesIntoDay(result, 'America/New_York')
      if (m >= GAP_START && m < GAP_END) {
        // Gap minutes: result must be at or after gap end
        expect(roundTrip, `gap minute ${m}`).toBeGreaterThanOrEqual(GAP_END)
      } else if (m === 1425) {
        // 23:45 - round trip fine
        expect(roundTrip, `minute ${m}`).toBe(m)
      } else {
        expect(roundTrip, `minute ${m}`).toBe(m)
      }
    }
  })

  it('round trip every 15-min step of 2026-11-01: all steps round trip correctly', () => {
    // Ambiguous: minutes 60-119 happen twice. wallTimeToInstant gives first occurrence,
    // which still has the correct minutesIntoDay value.
    for (let m = 0; m <= 1425; m += 15) {
      const result = wallTimeToInstant('2026-11-01', m, 'America/New_York')
      const roundTrip = minutesIntoDay(result, 'America/New_York')
      expect(roundTrip, `minute ${m}`).toBe(m)
    }
  })
})

// ---------------------------------------------------------------------------
// snapMinutes
// ---------------------------------------------------------------------------

describe('snapMinutes', () => {
  it('round mode: 0->0, 7->0, 8->15, 14->15, 15->15, 16->15', () => {
    expect(snapMinutes(0, 'round')).toBe(0)
    expect(snapMinutes(7, 'round')).toBe(0)
    expect(snapMinutes(8, 'round')).toBe(15)
    expect(snapMinutes(14, 'round')).toBe(15)
    expect(snapMinutes(15, 'round')).toBe(15)
    expect(snapMinutes(16, 'round')).toBe(15)
  })

  it('floor mode: 0->0, 7->0, 8->0, 14->0, 15->15, 16->15', () => {
    expect(snapMinutes(0, 'floor')).toBe(0)
    expect(snapMinutes(7, 'floor')).toBe(0)
    expect(snapMinutes(8, 'floor')).toBe(0)
    expect(snapMinutes(14, 'floor')).toBe(0)
    expect(snapMinutes(15, 'floor')).toBe(15)
    expect(snapMinutes(16, 'floor')).toBe(15)
  })

  it('ceil mode: 0->0, 7->15, 8->15, 14->15, 15->15, 16->30', () => {
    expect(snapMinutes(0, 'ceil')).toBe(0)
    expect(snapMinutes(7, 'ceil')).toBe(15)
    expect(snapMinutes(8, 'ceil')).toBe(15)
    expect(snapMinutes(14, 'ceil')).toBe(15)
    expect(snapMinutes(15, 'ceil')).toBe(15)
    expect(snapMinutes(16, 'ceil')).toBe(30)
  })

  it('exact multiples are returned unchanged in all modes', () => {
    expect(snapMinutes(0)).toBe(0)
    expect(snapMinutes(15)).toBe(15)
    expect(snapMinutes(60)).toBe(60)
  })

  it('custom step of 30', () => {
    expect(snapMinutes(14, 'round', 30)).toBe(0)
    expect(snapMinutes(15, 'round', 30)).toBe(30)
    expect(snapMinutes(29, 'floor', 30)).toBe(0)
    expect(snapMinutes(1, 'ceil', 30)).toBe(30)
  })
})

// ---------------------------------------------------------------------------
// daySegment
// ---------------------------------------------------------------------------

describe('daySegment', () => {
  const TZ = 'America/New_York'

  it('event entirely within one day', () => {
    // Event 10:00 to 11:00 on 2026-10-15 in New York
    const start = wallTimeToInstant('2026-10-15', 600, TZ)
    const end = wallTimeToInstant('2026-10-15', 660, TZ)
    const seg = daySegment(start, end, '2026-10-15', TZ)
    expect(seg).toEqual({ startMin: 600, endMin: 660 })
  })

  it('event from 23:00 to 01:00 next day gives {1380,1440} on first date and {0,60} on second', () => {
    const start = wallTimeToInstant('2026-10-15', 1380, TZ)
    const end = wallTimeToInstant('2026-10-16', 60, TZ)
    expect(daySegment(start, end, '2026-10-15', TZ)).toEqual({ startMin: 1380, endMin: 1440 })
    expect(daySegment(start, end, '2026-10-16', TZ)).toEqual({ startMin: 0, endMin: 60 })
  })

  it('event ending exactly at local midnight: endMin 1440 on own date, null on next', () => {
    const start = wallTimeToInstant('2026-10-15', 1380, TZ)
    const end = wallTimeToInstant('2026-10-16', 0, TZ)
    expect(daySegment(start, end, '2026-10-15', TZ)).toEqual({ startMin: 1380, endMin: 1440 })
    expect(daySegment(start, end, '2026-10-16', TZ)).toBeNull()
  })

  it('event on a different date returns null', () => {
    const start = wallTimeToInstant('2026-10-14', 600, TZ)
    const end = wallTimeToInstant('2026-10-14', 660, TZ)
    expect(daySegment(start, end, '2026-10-15', TZ)).toBeNull()
  })

  it('end equal to start returns null', () => {
    const d = wallTimeToInstant('2026-10-15', 600, TZ)
    expect(daySegment(d, d, '2026-10-15', TZ)).toBeNull()
  })

  it('end before start returns null', () => {
    const start = wallTimeToInstant('2026-10-15', 660, TZ)
    const end = wallTimeToInstant('2026-10-15', 600, TZ)
    expect(daySegment(start, end, '2026-10-15', TZ)).toBeNull()
  })

  it('event spanning three days gives {0,1440} for the middle day', () => {
    const start = wallTimeToInstant('2026-10-14', 600, TZ)
    const end = wallTimeToInstant('2026-10-16', 600, TZ)
    expect(daySegment(start, end, '2026-10-15', TZ)).toEqual({ startMin: 0, endMin: 1440 })
  })

  it('event entirely in future relative to dateStr returns null', () => {
    const start = wallTimeToInstant('2026-10-16', 600, TZ)
    const end = wallTimeToInstant('2026-10-16', 660, TZ)
    expect(daySegment(start, end, '2026-10-15', TZ)).toBeNull()
  })
})

// ---------------------------------------------------------------------------
// layoutDay
// ---------------------------------------------------------------------------

describe('layoutDay', () => {
  const item = (id: string, s: number, e: number): { id: string; startMin: number; endMin: number } =>
    ({ id, startMin: s, endMin: e })

  it('single item: lane 0, laneCount 1', () => {
    const [r] = layoutDay([item('a', 540, 600)])!
    expect(r!.lane).toBe(0)
    expect(r!.laneCount).toBe(1)
  })

  it('two overlapping items get lanes 0 and 1, laneCount 2 for both', () => {
    const result = layoutDay([item('a', 540, 600), item('b', 560, 620)])
    const a = result.find(r => r.id === 'a')!
    const b = result.find(r => r.id === 'b')!
    expect(a.lane).toBe(0)
    expect(b.lane).toBe(1)
    expect(a.laneCount).toBe(2)
    expect(b.laneCount).toBe(2)
  })

  it('two items that only touch (9:00-10:00 and 10:00-11:00) share lane 0 and laneCount 1', () => {
    const result = layoutDay([item('a', 540, 600), item('b', 600, 660)])
    const a = result.find(r => r.id === 'a')!
    const b = result.find(r => r.id === 'b')!
    expect(a.lane).toBe(0)
    expect(b.lane).toBe(0)
    expect(a.laneCount).toBe(1)
    expect(b.laneCount).toBe(1)
  })

  it('chain A 9-11, B 10-12, C 11-13: A lane 0, B lane 1, C lane 0, all laneCount 2', () => {
    const result = layoutDay([item('a', 540, 660), item('b', 600, 720), item('c', 660, 780)])
    const a = result.find(r => r.id === 'a')!
    const b = result.find(r => r.id === 'b')!
    const c = result.find(r => r.id === 'c')!
    expect(a.lane).toBe(0)
    expect(b.lane).toBe(1)
    expect(c.lane).toBe(0)
    expect(a.laneCount).toBe(2)
    expect(b.laneCount).toBe(2)
    expect(c.laneCount).toBe(2)
  })

  it('two items with identical times get lanes by id order', () => {
    const result = layoutDay([item('z', 540, 600), item('a', 540, 600)])
    const a = result.find(r => r.id === 'a')!
    const z = result.find(r => r.id === 'z')!
    expect(a.lane).toBe(0)
    expect(z.lane).toBe(1)
  })

  it('shuffled input gives the same result as sorted input', () => {
    const sorted = layoutDay([item('a', 540, 660), item('b', 600, 720), item('c', 660, 780)])
    const shuffled = layoutDay([item('c', 660, 780), item('a', 540, 660), item('b', 600, 720)])
    // Compare by id
    for (const r of sorted) {
      const s = shuffled.find(x => x.id === r.id)!
      expect(s.lane, `id ${r.id}`).toBe(r.lane)
      expect(s.laneCount, `id ${r.id}`).toBe(r.laneCount)
    }
  })

  it('15-min item at 9:00 and item starting at 9:20 go in different lanes (displayEndMin extends first to 9:30)', () => {
    // Item a: startMin=540, endMin=555, displayEndMin=570
    // Item b: startMin=560, endMin=620, displayEndMin=620
    // a.startMin(540) < b.displayEndMin(620) AND b.startMin(560) < a.displayEndMin(570): overlap
    const result = layoutDay([item('a', 540, 555), item('b', 560, 620)])
    const a = result.find(r => r.id === 'a')!
    const b = result.find(r => r.id === 'b')!
    expect(a.lane).not.toBe(b.lane)
  })

  it('displayEndMin is capped at 1440 for item starting at 23:50', () => {
    const [r] = layoutDay([item('a', 1430, 1435)])!
    expect(r!.displayEndMin).toBe(1440)
  })

  it('input array is not mutated', () => {
    const input = [item('b', 600, 660), item('a', 540, 600)]
    const copy = input.map(x => ({ ...x }))
    layoutDay(input)
    expect(input[0]).toEqual(copy[0])
    expect(input[1]).toEqual(copy[1])
  })
})

// ---------------------------------------------------------------------------
// formatTimeLabel
// ---------------------------------------------------------------------------

describe('formatTimeLabel', () => {
  const TZ = 'America/New_York'

  it('"9:15 AM" in America/New_York', () => {
    // 2026-10-15T13:15:00Z = 9:15 AM EDT
    expect(formatTimeLabel('2026-10-15T13:15:00Z', TZ)).toBe('9:15 AM')
  })

  it('"12:00 PM" in America/New_York', () => {
    // 2026-10-15T16:00:00Z = 12:00 PM EDT
    expect(formatTimeLabel('2026-10-15T16:00:00Z', TZ)).toBe('12:00 PM')
  })

  it('"12:30 AM" in America/New_York', () => {
    // 2026-10-15T04:30:00Z = 12:30 AM EDT
    expect(formatTimeLabel('2026-10-15T04:30:00Z', TZ)).toBe('12:30 AM')
  })

  it('"11:59 PM" in America/New_York', () => {
    // 2026-10-16T03:59:00Z = 11:59 PM EDT
    expect(formatTimeLabel('2026-10-16T03:59:00Z', TZ)).toBe('11:59 PM')
  })

  it('Asia/Kolkata at 2026-10-15T14:00:00Z is "7:30 PM" with a normal space', () => {
    const result = formatTimeLabel('2026-10-15T14:00:00Z', 'Asia/Kolkata')
    expect(result).toBe('7:30 PM')
    // Verify the space is 0x20 (normal space), not a narrow no-break space
    expect(result.charCodeAt(result.indexOf('PM') - 1)).toBe(0x20)
  })
})

// ---------------------------------------------------------------------------
// formatHourLabel
// ---------------------------------------------------------------------------

describe('formatHourLabel', () => {
  it('0 gives "12 AM"', () => { expect(formatHourLabel(0)).toBe('12 AM') })
  it('9 gives "9 AM"', () => { expect(formatHourLabel(9)).toBe('9 AM') })
  it('12 gives "12 PM"', () => { expect(formatHourLabel(12)).toBe('12 PM') })
  it('13 gives "1 PM"', () => { expect(formatHourLabel(13)).toBe('1 PM') })
  it('23 gives "11 PM"', () => { expect(formatHourLabel(23)).toBe('11 PM') })
})
// ---------------------------------------------------------------------------
// normalizeSpaces
// ---------------------------------------------------------------------------

describe('normalizeSpaces', () => {
  it('replaces narrow no-break space (U+202F) with normal space', () => {
    expect(normalizeSpaces('9:15\u202f' + 'AM')).toBe('9:15 AM')
  })

  it('replaces non-breaking space (U+00A0) with normal space', () => {
    expect(normalizeSpaces('9:15\u00a0' + 'AM')).toBe('9:15 AM')
  })

  it('leaves a normal space string unchanged', () => {
    expect(normalizeSpaces('9:15 AM')).toBe('9:15 AM')
  })
})

// ---------------------------------------------------------------------------
// layoutDay duplicate id
// ---------------------------------------------------------------------------

describe('layoutDay duplicate id', () => {
  const item = (id: string, s: number, e: number) => ({ id, startMin: s, endMin: e })

  it('throws an Error naming the duplicate id', () => {
    expect(() => layoutDay([item('a', 540, 600), item('b', 600, 660), item('a', 700, 760)]))
      .toThrow('layoutDay: duplicate item id "a"')
  })

  it('does not throw when all ids are unique', () => {
    expect(() => layoutDay([item('a', 540, 600), item('b', 600, 660), item('c', 700, 760)]))
      .not.toThrow()
  })
})

// ---------------------------------------------------------------------------
// wallTimeToInstant regression (duplicates existing coverage on purpose)
// ---------------------------------------------------------------------------

describe('wallTimeToInstant regression after fallback change', () => {
  it('2026-03-08 at 150 (spring forward gap) still resolves to 07:30Z', () => {
    expect(wallTimeToInstant('2026-03-08', 150, 'America/New_York').toISOString())
      .toBe('2026-03-08T07:30:00.000Z')
  })

  it('2026-03-08 at 90 (before spring forward) still resolves to 06:30Z', () => {
    expect(wallTimeToInstant('2026-03-08', 90, 'America/New_York').toISOString())
      .toBe('2026-03-08T06:30:00.000Z')
  })

  it('2026-11-01 at 90 (fall back, first occurrence) still resolves to 05:30Z', () => {
    expect(wallTimeToInstant('2026-11-01', 90, 'America/New_York').toISOString())
      .toBe('2026-11-01T05:30:00.000Z')
  })

  it('minutes 0 still works (midnight)', () => {
    expect(wallTimeToInstant('2026-10-15', 0, 'America/New_York').toISOString())
      .toBe('2026-10-15T04:00:00.000Z')
  })

  it('minutes 1440 equals minutes 0 of the next date', () => {
    const a = wallTimeToInstant('2026-10-15', 1440, 'America/New_York')
    const b = wallTimeToInstant('2026-10-16', 0, 'America/New_York')
    expect(a.toISOString()).toBe(b.toISOString())
  })
})

// ---------------------------------------------------------------------------
// wallTimeToInstant RangeError fallback reachability
// ---------------------------------------------------------------------------

describe('wallTimeToInstant fallback RangeError', () => {
  // Investigation: searched Pacific/Apia 2011-12-30 (the skipped calendar date),
  // Africa/Casablanca around Ramadan, Australia/Lord_Howe (30-min DST), and
  // extreme dates 0001-01-01 and 9999-12-31.
  //
  // Pacific/Apia 2011-12-30: the oscillation branch fires first (it is a
  //   skipped day treated like a 24-hour DST gap) and returns before the
  //   fallback is reached.
  //
  // Africa/Casablanca, Lord_Howe, 9999-12-31: all converged correctly, no mismatch.
  //
  // 0001-01-01: parseYMD accepts year 1, but Date.UTC(1, 0, 1) maps to 1901
  //   (JS spec: years 0-99 in Date.UTC are treated as 1900+year). The
  //   verification check gets gotDate '1901-01-01' which differs from '0001-01-01',
  //   so the fallback throw is reached.
  it('throws RangeError for year 0001 (Date.UTC maps year 1 to 1901, causing verification mismatch)', () => {
    expect(() => wallTimeToInstant('0001-01-01', 0, 'America/New_York')).toThrow(RangeError)
    expect(() => wallTimeToInstant('0001-01-01', 0, 'America/New_York'))
      .toThrow('wallTimeToInstant: could not resolve "0001-01-01"')
  })
})


// ---------------------------------------------------------------------------
// Formatter cache: interleaved zones give correct answers
// ---------------------------------------------------------------------------

describe('formatter cache: interleaved zones', () => {
  // Three zones called alternately to verify the cache key includes the zone
  // and different zones never receive each other's formatter.
  const inst = '2026-10-15T14:00:00Z'
  const NY = 'America/New_York'
  const KO = 'Asia/Kolkata'
  const LA = 'America/Los_Angeles'

  it('alternating minutesIntoDay calls for three zones return the same values every round', () => {
    for (let round = 0; round < 3; round++) {
      expect(minutesIntoDay(inst, NY), `round ${round} NY`).toBe(600)
      expect(minutesIntoDay(inst, KO), `round ${round} KO`).toBe(1170)
      expect(minutesIntoDay(inst, LA), `round ${round} LA`).toBe(420)
    }
  })

  it('alternating zonedDateStr calls for three zones return correct dates every round', () => {
    for (let round = 0; round < 3; round++) {
      expect(zonedDateStr(inst, NY), `round ${round} NY`).toBe('2026-10-15')
      expect(zonedDateStr(inst, KO), `round ${round} KO`).toBe('2026-10-15')
      // 2026-10-15T14:00:00Z = 2026-10-15T07:00 PDT (UTC-7); date is still Oct 15
      expect(zonedDateStr(inst, LA), `round ${round} LA`).toBe('2026-10-15')
    }
  })
})

// ---------------------------------------------------------------------------
// Formatter cache: invalid zone throws on first and repeat calls
// ---------------------------------------------------------------------------

describe('formatter cache: invalid zone throws every time', () => {
  const inst = '2026-10-15T14:00:00Z'
  const BAD = 'Not/AZone'

  it('zonedDateStr throws RangeError on first call with bad zone', () => {
    expect(() => zonedDateStr(inst, BAD)).toThrow(RangeError)
  })

  it('zonedDateStr throws RangeError on a second call with the same bad zone', () => {
    expect(() => zonedDateStr(inst, BAD)).toThrow(RangeError)
  })

  it('minutesIntoDay throws RangeError on first call with bad zone', () => {
    expect(() => minutesIntoDay(inst, BAD)).toThrow(RangeError)
  })

  it('minutesIntoDay throws RangeError on a second call with the same bad zone', () => {
    expect(() => minutesIntoDay(inst, BAD)).toThrow(RangeError)
  })

  it('formatTimeLabel throws RangeError on first call with bad zone', () => {
    expect(() => formatTimeLabel(inst, BAD)).toThrow(RangeError)
  })

  it('formatTimeLabel throws RangeError on a second call with the same bad zone', () => {
    expect(() => formatTimeLabel(inst, BAD)).toThrow(RangeError)
  })

  it('a valid zone still works correctly after bad zone calls', () => {
    expect(minutesIntoDay(inst, 'America/New_York')).toBe(600)
    expect(zonedDateStr(inst, 'America/New_York')).toBe('2026-10-15')
  })
})

// ---------------------------------------------------------------------------
// Formatter cache: formatTimeLabel normalizes spaces after repeated calls
// ---------------------------------------------------------------------------

describe('formatter cache: formatTimeLabel normalizes spaces after repeated calls', () => {
  it('returns normal-space strings for America/New_York across repeated calls', () => {
    const inst = '2026-10-15T13:15:00Z'  // 9:15 AM EDT
    for (let i = 0; i < 3; i++) {
      const result = formatTimeLabel(inst, 'America/New_York')
      expect(result, `call ${i}`).toBe('9:15 AM')
      expect(result.charCodeAt(result.indexOf('AM') - 1), `call ${i} space code`).toBe(0x20)
    }
  })

  it('returns normal-space strings for Asia/Kolkata across repeated calls', () => {
    const inst = '2026-10-15T14:00:00Z'  // 7:30 PM IST
    for (let i = 0; i < 3; i++) {
      const result = formatTimeLabel(inst, 'Asia/Kolkata')
      expect(result, `call ${i}`).toBe('7:30 PM')
      expect(result.charCodeAt(result.indexOf('PM') - 1), `call ${i} space code`).toBe(0x20)
    }
  })
})
