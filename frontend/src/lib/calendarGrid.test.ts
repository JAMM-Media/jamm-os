// path: frontend/src/lib/calendarGrid.test.ts
import { describe, it, expect } from 'vitest'
import {
  DEFAULT_FIRST_VISIBLE_MINUTES,
  weekDates,
  buildGridDays,
  nowPosition,
  blockBox,
} from './calendarGrid'

const NY = 'America/New_York'
const KO = 'Asia/Kolkata'
const LA = 'America/Los_Angeles'

// ---------------------------------------------------------------------------
// DEFAULT_FIRST_VISIBLE_MINUTES
// ---------------------------------------------------------------------------

describe('DEFAULT_FIRST_VISIBLE_MINUTES', () => {
  it('is 420', () => {
    expect(DEFAULT_FIRST_VISIBLE_MINUTES).toBe(420)
  })
})

// ---------------------------------------------------------------------------
// weekDates
// ---------------------------------------------------------------------------

describe('weekDates', () => {
  // startOfWeek treats Sunday (day 0) as the first day of the week.
  // Oct 1 2026 = Thursday, so Oct 11 = Sunday.

  it('returns 7 dates starting on the Sunday of the anchor week (anchor on Thursday)', () => {
    // 2026-10-15 is Thursday; the week starts on Sunday 2026-10-11
    const result = weekDates('2026-10-15')
    expect(result).toHaveLength(7)
    expect(result[0]).toBe('2026-10-11')
    expect(result[6]).toBe('2026-10-17')
    expect(result).toEqual([
      '2026-10-11', '2026-10-12', '2026-10-13', '2026-10-14',
      '2026-10-15', '2026-10-16', '2026-10-17',
    ])
  })

  it('returns the same week when the anchor is the first day (Sunday)', () => {
    const result = weekDates('2026-10-11')
    expect(result[0]).toBe('2026-10-11')
    expect(result[6]).toBe('2026-10-17')
  })

  it('returns the same week when the anchor is the last day (Saturday)', () => {
    const result = weekDates('2026-10-17')
    expect(result[0]).toBe('2026-10-11')
    expect(result[6]).toBe('2026-10-17')
  })

  it('handles a week that spans a month boundary (Sep to Oct)', () => {
    // 2026-09-30 is Wednesday; startOfWeek = 2026-09-27 (Sunday)
    // Week: Sep 27, 28, 29, 30, Oct 1, 2, 3
    const result = weekDates('2026-09-30')
    expect(result[0]).toBe('2026-09-27')
    expect(result[6]).toBe('2026-10-03')
  })

  it('handles a week that spans a year boundary (anchor 2026-12-30)', () => {
    // Dec 27 2026 = Sunday; Dec 30 = Wednesday
    // Week: 2026-12-27 to 2027-01-02
    const result = weekDates('2026-12-30')
    expect(result[0]).toBe('2026-12-27')
    expect(result[6]).toBe('2027-01-02')
  })
})

// ---------------------------------------------------------------------------
// buildGridDays: single event
// ---------------------------------------------------------------------------

describe('buildGridDays single event', () => {
  const dates = ['2026-10-14', '2026-10-15', '2026-10-16']
  // 9:00 to 10:00 AM EDT = 13:00Z to 14:00Z
  const timed = [{ id: 'ev1', startAt: '2026-10-15T13:00:00Z', endAt: '2026-10-15T14:00:00Z' }]

  it('places event on its own date only with correct block values', () => {
    const days = buildGridDays({ dates, timed, allDay: [], timeZone: NY })
    const oct14 = days.find(d => d.dateStr === '2026-10-14')!
    const oct15 = days.find(d => d.dateStr === '2026-10-15')!
    const oct16 = days.find(d => d.dateStr === '2026-10-16')!

    expect(oct14.blocks).toHaveLength(0)
    expect(oct16.blocks).toHaveLength(0)

    expect(oct15.blocks).toHaveLength(1)
    const b = oct15.blocks[0]!
    expect(b.id).toBe('ev1')
    expect(b.startMin).toBe(540)   // 9:00 AM = 9 * 60
    expect(b.endMin).toBe(600)     // 10:00 AM = 10 * 60
    expect(b.displayEndMin).toBe(600)
    expect(b.lane).toBe(0)
    expect(b.laneCount).toBe(1)
    expect(b.continuesBefore).toBe(false)
    expect(b.continuesAfter).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// buildGridDays: cross midnight
// ---------------------------------------------------------------------------

describe('buildGridDays cross midnight', () => {
  // 11:00 PM to 1:00 AM next day EDT
  // Oct 15 23:00 EDT = Oct 16T03:00Z; Oct 16 01:00 EDT = Oct 16T05:00Z
  const dates = ['2026-10-15', '2026-10-16']
  const timed = [{ id: 'ev2', startAt: '2026-10-16T03:00:00Z', endAt: '2026-10-16T05:00:00Z' }]

  it('gives {1380,1440} with continuesAfter true on first date', () => {
    const days = buildGridDays({ dates, timed, allDay: [], timeZone: NY })
    const d15 = days.find(d => d.dateStr === '2026-10-15')!
    expect(d15.blocks).toHaveLength(1)
    const b = d15.blocks[0]!
    expect(b.startMin).toBe(1380)   // 23:00
    expect(b.endMin).toBe(1440)
    expect(b.continuesBefore).toBe(false)
    expect(b.continuesAfter).toBe(true)
  })

  it('gives {0,60} with continuesBefore true on second date', () => {
    const days = buildGridDays({ dates, timed, allDay: [], timeZone: NY })
    const d16 = days.find(d => d.dateStr === '2026-10-16')!
    expect(d16.blocks).toHaveLength(1)
    const b = d16.blocks[0]!
    expect(b.startMin).toBe(0)
    expect(b.endMin).toBe(60)     // 1:00 AM
    expect(b.continuesBefore).toBe(true)
    expect(b.continuesAfter).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// buildGridDays: event ending exactly at local midnight
// ---------------------------------------------------------------------------

describe('buildGridDays event ending exactly at midnight', () => {
  // Event: 11:00 PM to midnight (Oct 15 23:00 EDT to Oct 16 00:00 EDT)
  // Oct 15 23:00 EDT = Oct 16 03:00Z; midnight Oct 16 EDT = Oct 16 04:00Z
  const dates = ['2026-10-15', '2026-10-16']
  const timed = [{ id: 'ev3', startAt: '2026-10-16T03:00:00Z', endAt: '2026-10-16T04:00:00Z' }]

  it('appears only on its own date with endMin 1440 and continuesAfter false', () => {
    const days = buildGridDays({ dates, timed, allDay: [], timeZone: NY })
    const d15 = days.find(d => d.dateStr === '2026-10-15')!
    const d16 = days.find(d => d.dateStr === '2026-10-16')!

    expect(d15.blocks).toHaveLength(1)
    const b = d15.blocks[0]!
    expect(b.startMin).toBe(1380)
    expect(b.endMin).toBe(1440)
    expect(b.continuesAfter).toBe(false)

    expect(d16.blocks).toHaveLength(0)
  })
})

// ---------------------------------------------------------------------------
// buildGridDays: event spanning three days
// ---------------------------------------------------------------------------

describe('buildGridDays three days', () => {
  // Event spans Oct 14, 15, 16
  const dates = ['2026-10-14', '2026-10-15', '2026-10-16']
  // Starts 10:00 AM Oct 14 EDT = 14:00Z Oct 14, ends 2:00 PM Oct 16 EDT = 18:00Z Oct 16
  const timed = [{ id: 'ev4', startAt: '2026-10-14T14:00:00Z', endAt: '2026-10-16T18:00:00Z' }]

  it('appears on all three dates with correct flags', () => {
    const days = buildGridDays({ dates, timed, allDay: [], timeZone: NY })
    const d14 = days.find(d => d.dateStr === '2026-10-14')!
    const d15 = days.find(d => d.dateStr === '2026-10-15')!
    const d16 = days.find(d => d.dateStr === '2026-10-16')!

    // First day: starts at 10:00 AM (600), continues after midnight
    expect(d14.blocks[0]!.startMin).toBe(600)
    expect(d14.blocks[0]!.endMin).toBe(1440)
    expect(d14.blocks[0]!.continuesBefore).toBe(false)
    expect(d14.blocks[0]!.continuesAfter).toBe(true)

    // Middle day: full day 0 to 1440, both flags true
    expect(d15.blocks[0]!.startMin).toBe(0)
    expect(d15.blocks[0]!.endMin).toBe(1440)
    expect(d15.blocks[0]!.continuesBefore).toBe(true)
    expect(d15.blocks[0]!.continuesAfter).toBe(true)

    // Last day: 0 to 14:00 (840), continues from before
    expect(d16.blocks[0]!.startMin).toBe(0)
    expect(d16.blocks[0]!.endMin).toBe(840)  // 14:00 = 14 * 60
    expect(d16.blocks[0]!.continuesBefore).toBe(true)
    expect(d16.blocks[0]!.continuesAfter).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// buildGridDays: zone matters
// ---------------------------------------------------------------------------

describe('buildGridDays zone matters', () => {
  // 2026-10-15T01:30:00Z:
  //   NY (EDT, UTC-4):  date 2026-10-14, minutes 1290 (21:30)
  //   Kolkata (UTC+5:30): date 2026-10-15, minutes 420  (07:00)
  //   LA (PDT, UTC-7):  date 2026-10-14, minutes 1110 (18:30)
  // Verified by node. Task listed 390 for Kolkata but real value is 420.
  const timed = [{ id: 'z1', startAt: '2026-10-15T01:30:00Z', endAt: '2026-10-15T02:30:00Z' }]

  it('lands on 2026-10-14 at minute 1290 in America/New_York', () => {
    const days = buildGridDays({ dates: ['2026-10-14', '2026-10-15'], timed, allDay: [], timeZone: NY })
    const d14 = days.find(d => d.dateStr === '2026-10-14')!
    const d15 = days.find(d => d.dateStr === '2026-10-15')!
    expect(d14.blocks).toHaveLength(1)
    expect(d14.blocks[0]!.startMin).toBe(1290)
    expect(d15.blocks).toHaveLength(0)
  })

  it('lands on 2026-10-15 at minute 420 in Asia/Kolkata', () => {
    const days = buildGridDays({ dates: ['2026-10-14', '2026-10-15'], timed, allDay: [], timeZone: KO })
    const d14 = days.find(d => d.dateStr === '2026-10-14')!
    const d15 = days.find(d => d.dateStr === '2026-10-15')!
    expect(d15.blocks).toHaveLength(1)
    expect(d15.blocks[0]!.startMin).toBe(420)
    expect(d14.blocks).toHaveLength(0)
  })

  it('lands on 2026-10-14 at minute 1110 in America/Los_Angeles', () => {
    const days = buildGridDays({ dates: ['2026-10-14', '2026-10-15'], timed, allDay: [], timeZone: LA })
    const d14 = days.find(d => d.dateStr === '2026-10-14')!
    const d15 = days.find(d => d.dateStr === '2026-10-15')!
    expect(d14.blocks).toHaveLength(1)
    expect(d14.blocks[0]!.startMin).toBe(1110)
    expect(d15.blocks).toHaveLength(0)
  })
})

// ---------------------------------------------------------------------------
// buildGridDays: DST spring forward 2026-03-08
// ---------------------------------------------------------------------------

describe('buildGridDays DST spring forward 2026-03-08', () => {
  // Event: 06:30Z to 07:30Z
  //   06:30Z is before spring forward (07:00 UTC) so EST = UTC-5 -> 01:30 AM = 90 min
  //   07:30Z is after spring forward so EDT = UTC-4 -> 03:30 AM = 210 min
  // Expected block: {startMin: 90, endMin: 210}
  const timed = [{ id: 'dst1', startAt: '2026-03-08T06:30:00Z', endAt: '2026-03-08T07:30:00Z' }]

  it('gives startMin 90 (01:30 EST) and endMin 210 (03:30 EDT) spanning the gap', () => {
    const days = buildGridDays({ dates: ['2026-03-08'], timed, allDay: [], timeZone: NY })
    const b = days[0]!.blocks[0]!
    expect(b.startMin).toBe(90)
    expect(b.endMin).toBe(210)
    expect(b.continuesBefore).toBe(false)
    expect(b.continuesAfter).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// buildGridDays: DST fall back 2026-11-01
// ---------------------------------------------------------------------------

describe('buildGridDays DST fall back 2026-11-01', () => {
  // Event: 05:30Z to 07:30Z
  //   05:30Z is before fall back (06:00 UTC) so EDT = UTC-4 -> 01:30 AM = 90 min
  //   07:30Z is after fall back so EST = UTC-5 -> 02:30 AM = 150 min
  // Expected block: {startMin: 90, endMin: 150}
  const timed = [{ id: 'dst2', startAt: '2026-11-01T05:30:00Z', endAt: '2026-11-01T07:30:00Z' }]

  it('gives startMin 90 (01:30 EDT) and endMin 150 (02:30 EST)', () => {
    const days = buildGridDays({ dates: ['2026-11-01'], timed, allDay: [], timeZone: NY })
    const b = days[0]!.blocks[0]!
    expect(b.startMin).toBe(90)
    expect(b.endMin).toBe(150)
    expect(b.continuesBefore).toBe(false)
    expect(b.continuesAfter).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// buildGridDays: overlaps
// ---------------------------------------------------------------------------

describe('buildGridDays overlaps', () => {
  const dates = ['2026-10-15']
  const TZ = NY

  it('two overlapping events get lanes 0 and 1 and laneCount 2', () => {
    const timed = [
      { id: 'a', startAt: '2026-10-15T14:00:00Z', endAt: '2026-10-15T15:00:00Z' },
      { id: 'b', startAt: '2026-10-15T14:30:00Z', endAt: '2026-10-15T15:30:00Z' },
    ]
    const [day] = buildGridDays({ dates, timed, allDay: [], timeZone: TZ })!
    const a = day!.blocks.find(b => b.id === 'a')!
    const bl = day!.blocks.find(b => b.id === 'b')!
    expect(a.lane).toBe(0)
    expect(bl.lane).toBe(1)
    expect(a.laneCount).toBe(2)
    expect(bl.laneCount).toBe(2)
  })

  it('two events that only touch (end equals next start) share lane 0 and laneCount 1', () => {
    const timed = [
      { id: 'a', startAt: '2026-10-15T14:00:00Z', endAt: '2026-10-15T15:00:00Z' },
      { id: 'b', startAt: '2026-10-15T15:00:00Z', endAt: '2026-10-15T16:00:00Z' },
    ]
    const [day] = buildGridDays({ dates, timed, allDay: [], timeZone: TZ })!
    const a = day!.blocks.find(b => b.id === 'a')!
    const bl = day!.blocks.find(b => b.id === 'b')!
    expect(a.lane).toBe(0)
    expect(bl.lane).toBe(0)
    expect(a.laneCount).toBe(1)
    expect(bl.laneCount).toBe(1)
  })

  it('a 15-min event next to an event starting 20 minutes later get different lanes (display minimum)', () => {
    // 9:00-9:15 displays as 9:00-9:30; event at 9:20 starts inside that display window
    const timed = [
      { id: 'a', startAt: '2026-10-15T13:00:00Z', endAt: '2026-10-15T13:15:00Z' },
      { id: 'b', startAt: '2026-10-15T13:20:00Z', endAt: '2026-10-15T14:00:00Z' },
    ]
    const [day] = buildGridDays({ dates, timed, allDay: [], timeZone: TZ })!
    const a = day!.blocks.find(b => b.id === 'a')!
    const bl = day!.blocks.find(b => b.id === 'b')!
    expect(a.lane).not.toBe(bl.lane)
  })
})

// ---------------------------------------------------------------------------
// buildGridDays: allDay placement
// ---------------------------------------------------------------------------

describe('buildGridDays allDay', () => {
  const dates = ['2026-10-14', '2026-10-15', '2026-10-16']

  it('places allDay items on their own date only, sorted by id', () => {
    const allDay = [
      { id: 'c', date: '2026-10-15' },
      { id: 'a', date: '2026-10-15' },
      { id: 'b', date: '2026-10-15' },
    ]
    const days = buildGridDays({ dates, timed: [], allDay, timeZone: NY })
    const d15 = days.find(d => d.dateStr === '2026-10-15')!
    expect(d15.allDayIds).toEqual(['a', 'b', 'c'])
    expect(days.find(d => d.dateStr === '2026-10-14')!.allDayIds).toEqual([])
    expect(days.find(d => d.dateStr === '2026-10-16')!.allDayIds).toEqual([])
  })

  it('ignores allDay items whose date is not in the dates list', () => {
    const allDay = [
      { id: 'x', date: '2026-10-13' },
      { id: 'y', date: '2026-10-17' },
    ]
    const days = buildGridDays({ dates, timed: [], allDay, timeZone: NY })
    for (const d of days) expect(d.allDayIds).toEqual([])
  })

  it('two dates each get their own allDay list', () => {
    const allDay = [
      { id: 'p', date: '2026-10-14' },
      { id: 'q', date: '2026-10-16' },
    ]
    const days = buildGridDays({ dates, timed: [], allDay, timeZone: NY })
    expect(days.find(d => d.dateStr === '2026-10-14')!.allDayIds).toEqual(['p'])
    expect(days.find(d => d.dateStr === '2026-10-15')!.allDayIds).toEqual([])
    expect(days.find(d => d.dateStr === '2026-10-16')!.allDayIds).toEqual(['q'])
  })
})

// ---------------------------------------------------------------------------
// buildGridDays: input order
// ---------------------------------------------------------------------------

describe('buildGridDays input order', () => {
  it('shuffled timed input produces identical GridDay output', () => {
    const dates = ['2026-10-15']
    const timed = [
      { id: 'a', startAt: '2026-10-15T14:00:00Z', endAt: '2026-10-15T15:00:00Z' },
      { id: 'b', startAt: '2026-10-15T14:30:00Z', endAt: '2026-10-15T15:30:00Z' },
      { id: 'c', startAt: '2026-10-15T16:00:00Z', endAt: '2026-10-15T17:00:00Z' },
    ]
    const shuffled = [timed[2]!, timed[0]!, timed[1]!]

    const ref = buildGridDays({ dates, timed, allDay: [], timeZone: NY })
    const got = buildGridDays({ dates, timed: shuffled, allDay: [], timeZone: NY })

    expect(got[0]!.blocks.length).toBe(ref[0]!.blocks.length)
    for (const rb of ref[0]!.blocks) {
      const gb = got[0]!.blocks.find(x => x.id === rb.id)!
      expect(gb.lane).toBe(rb.lane)
      expect(gb.laneCount).toBe(rb.laneCount)
      expect(gb.startMin).toBe(rb.startMin)
    }
  })
})

// ---------------------------------------------------------------------------
// buildGridDays: empty inputs
// ---------------------------------------------------------------------------

describe('buildGridDays empty inputs', () => {
  it('empty timed and allDay gives one empty GridDay per date', () => {
    const days = buildGridDays({ dates: ['2026-10-14', '2026-10-15'], timed: [], allDay: [], timeZone: NY })
    expect(days).toHaveLength(2)
    for (const d of days) {
      expect(d.blocks).toEqual([])
      expect(d.allDayIds).toEqual([])
    }
  })

  it('empty dates list gives an empty array', () => {
    const days = buildGridDays({ dates: [], timed: [], allDay: [], timeZone: NY })
    expect(days).toEqual([])
  })
})

// ---------------------------------------------------------------------------
// buildGridDays: errors propagate
// ---------------------------------------------------------------------------

describe('buildGridDays errors', () => {
  it('a naive startAt string (no offset) throws', () => {
    expect(() =>
      buildGridDays({
        dates: ['2026-10-15'],
        timed: [{ id: 'e1', startAt: '2026-10-15T14:00:00', endAt: '2026-10-15T15:00:00Z' }],
        allDay: [],
        timeZone: NY,
      })
    ).toThrow('offset')
  })

  it('an invalid timeZone throws RangeError', () => {
    expect(() =>
      buildGridDays({
        dates: ['2026-10-15'],
        timed: [{ id: 'e2', startAt: '2026-10-15T14:00:00Z', endAt: '2026-10-15T15:00:00Z' }],
        allDay: [],
        timeZone: 'Not/AZone',
      })
    ).toThrow(RangeError)
  })

  it('two timed items with the same id on the same day throw the layoutDay message', () => {
    expect(() =>
      buildGridDays({
        dates: ['2026-10-15'],
        timed: [
          { id: 'dup', startAt: '2026-10-15T14:00:00Z', endAt: '2026-10-15T15:00:00Z' },
          { id: 'dup', startAt: '2026-10-15T15:00:00Z', endAt: '2026-10-15T16:00:00Z' },
        ],
        allDay: [],
        timeZone: NY,
      })
    ).toThrow('duplicate item id "dup"')
  })
})

// ---------------------------------------------------------------------------
// buildGridDays: input not mutated
// ---------------------------------------------------------------------------

describe('buildGridDays no mutation', () => {
  it('does not mutate the timed or allDay input arrays', () => {
    const timed = [
      { id: 'a', startAt: '2026-10-15T14:00:00Z', endAt: '2026-10-15T15:00:00Z' },
      { id: 'b', startAt: '2026-10-15T15:30:00Z', endAt: '2026-10-15T16:30:00Z' },
    ]
    const allDay = [{ id: 'h', date: '2026-10-15' }]
    const timedCopy = timed.map(x => ({ ...x }))
    const allDayCopy = allDay.map(x => ({ ...x }))

    buildGridDays({ dates: ['2026-10-15'], timed, allDay, timeZone: NY })

    expect(timed[0]).toEqual(timedCopy[0])
    expect(timed[1]).toEqual(timedCopy[1])
    expect(allDay[0]).toEqual(allDayCopy[0])
  })
})

// ---------------------------------------------------------------------------
// nowPosition
// ---------------------------------------------------------------------------

describe('nowPosition', () => {
  it('2026-10-15T14:00:00Z gives {dateStr "2026-10-15", minutes 600} in America/New_York', () => {
    const result = nowPosition(new Date('2026-10-15T14:00:00Z'), NY)
    expect(result.dateStr).toBe('2026-10-15')
    expect(result.minutes).toBe(600)
  })

  it('2026-10-15T14:00:00Z gives {dateStr "2026-10-15", minutes 1170} in Asia/Kolkata', () => {
    // 14:00Z + 5:30 = 19:30 IST = 1170 min
    const result = nowPosition(new Date('2026-10-15T14:00:00Z'), KO)
    expect(result.dateStr).toBe('2026-10-15')
    expect(result.minutes).toBe(1170)
  })

  it('2026-10-15T03:30:00Z gives the previous date in New York', () => {
    // 03:30Z - 4h (EDT) = 23:30 on Oct 14 = 1410 min; verified by node
    const result = nowPosition(new Date('2026-10-15T03:30:00Z'), NY)
    expect(result.dateStr).toBe('2026-10-14')
    expect(result.minutes).toBe(1410)
  })
})

// ---------------------------------------------------------------------------
// blockBox
// ---------------------------------------------------------------------------

describe('blockBox', () => {
  it('with pxPerMinute 0.7, block {540, 600, lane 1, laneCount 3} gives correct geometry', () => {
    const result = blockBox({ startMin: 540, displayEndMin: 600, lane: 1, laneCount: 3 }, 0.7)
    expect(result.top).toBe(378)          // 540 * 0.7
    expect(result.height).toBe(42)         // 60 * 0.7
    expect(result.leftPct).toBeCloseTo(33.333333333333336, 10)
    expect(result.widthPct).toBeCloseTo(33.333333333333336, 10)
  })

  it('with lane 0 and laneCount 1, leftPct is 0 and widthPct is 100', () => {
    const result = blockBox({ startMin: 0, displayEndMin: 60, lane: 0, laneCount: 1 }, 1)
    expect(result.leftPct).toBe(0)
    expect(result.widthPct).toBe(100)
  })
})
