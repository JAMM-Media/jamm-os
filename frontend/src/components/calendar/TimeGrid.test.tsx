// path: frontend/src/components/calendar/TimeGrid.test.tsx
import { describe, it, expect } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { TimeGrid } from './TimeGrid'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const NY = 'America/New_York'
const KO = 'Asia/Kolkata'

// Render TimeGrid to a static HTML string.
function render(props: React.ComponentProps<typeof TimeGrid>): string {
  return renderToStaticMarkup(<TimeGrid {...props} />)
}

// Count occurrences of a substring.
function countOccurrences(str: string, sub: string): number {
  let count = 0
  let pos = 0
  while ((pos = str.indexOf(sub, pos)) !== -1) { count++; pos += sub.length }
  return count
}

// ---------------------------------------------------------------------------
// Header
// ---------------------------------------------------------------------------

describe('TimeGrid header', () => {
  it('renders seven header cells for seven days', () => {
    const days = ['2026-10-11', '2026-10-12', '2026-10-13', '2026-10-14',
      '2026-10-15', '2026-10-16', '2026-10-17']
    const markup = render({ days, timeZone: NY, timed: [], allDay: [], now: null })
    // Each day cell contains the day number; seven distinct numbers
    expect(countOccurrences(markup, '>11<')).toBeGreaterThanOrEqual(1)
    expect(countOccurrences(markup, '>17<')).toBeGreaterThanOrEqual(1)
    // Seven days means all weekday names appear
    expect(markup).toContain('>Sun<')
    expect(markup).toContain('>Sat<')
  })

  it('shows correct weekday names for 2026-10-11 (Sun) to 2026-10-17 (Sat)', () => {
    const days = ['2026-10-11', '2026-10-12', '2026-10-13', '2026-10-14',
      '2026-10-15', '2026-10-16', '2026-10-17']
    const markup = render({ days, timeZone: NY, timed: [], allDay: [], now: null })
    // Oct 11 2026 = Sunday
    expect(markup).toContain('>Sun<')
    expect(markup).toContain('>Mon<')
    expect(markup).toContain('>Tue<')
    expect(markup).toContain('>Wed<')
    expect(markup).toContain('>Thu<')
    expect(markup).toContain('>Fri<')
    expect(markup).toContain('>Sat<')
  })

  it('renders one header cell for one day', () => {
    const markup = render({ days: ['2026-10-15'], timeZone: NY, timed: [], allDay: [], now: null })
    // Only Thu appears as a day name
    expect(markup).toContain('>Thu<')
    expect(markup).not.toContain('>Wed<')
    expect(markup).not.toContain('>Fri<')
  })

  it('marks the today cell with data-today="true" when now falls on a day in view', () => {
    // 2026-10-15T14:00:00Z = Oct 15 in NY (EDT, UTC-4)
    const now = new Date('2026-10-15T14:00:00Z')
    const days = ['2026-10-14', '2026-10-15', '2026-10-16']
    const markup = render({ days, timeZone: NY, timed: [], allDay: [], now })
    expect(markup).toContain('data-today="true"')
    // Only one cell carries data-today
    expect(countOccurrences(markup, 'data-today="true"')).toBe(1)
  })

  it('no cell carries data-today when now is null', () => {
    const days = ['2026-10-14', '2026-10-15', '2026-10-16']
    const markup = render({ days, timeZone: NY, timed: [], allDay: [], now: null })
    expect(markup).not.toContain('data-today')
  })

  it('no now-line renders when now is null', () => {
    const markup = render({ days: ['2026-10-15'], timeZone: NY, timed: [], allDay: [], now: null })
    expect(markup).not.toContain('data-now-line')
  })
})

// ---------------------------------------------------------------------------
// Hour labels
// ---------------------------------------------------------------------------

describe('TimeGrid hour labels', () => {
  it('renders labels 1 AM through 12 PM and 11 PM, but not 12 AM', () => {
    const markup = render({ days: ['2026-10-15'], timeZone: NY, timed: [], allDay: [], now: null })
    expect(markup).toContain('1 AM')
    expect(markup).toContain('11 AM')
    expect(markup).toContain('12 PM')
    expect(markup).toContain('1 PM')
    expect(markup).toContain('11 PM')
    // Hour 0 (12 AM) label must not appear
    expect(markup).not.toMatch(/12 AM/)
  })
})

// ---------------------------------------------------------------------------
// Timed events
// ---------------------------------------------------------------------------

describe('TimeGrid timed events', () => {
  // 9:00 to 10:00 AM EDT = 13:00Z to 14:00Z
  const event9to10 = {
    id: 'ev1',
    title: 'Morning Call',
    startAt: '2026-10-15T13:00:00Z',
    endAt: '2026-10-15T14:00:00Z',
    color: '#3B82F6',
  }

  it('renders a NY 9-10am event on 2026-10-15 with correct data attributes', () => {
    const markup = render({
      days: ['2026-10-15'],
      timeZone: NY,
      timed: [event9to10],
      allDay: [],
      now: null,
    })
    expect(markup).toContain('data-start-min="540"')
    expect(markup).toContain('data-end-min="600"')
    expect(markup).toContain('data-continues-before="false"')
    expect(markup).toContain('data-continues-after="false"')
    expect(markup).toContain('data-block-id="ev1"')
  })

  it('aria-label contains the formatted start and end times in NY zone', () => {
    const markup = render({
      days: ['2026-10-15'],
      timeZone: NY,
      timed: [event9to10],
      allDay: [],
      now: null,
    })
    // 13:00Z = 9:00 AM EDT, 14:00Z = 10:00 AM EDT
    expect(markup).toContain('9:00 AM to 10:00 AM')
  })

  it('event is not rendered on neighboring days', () => {
    const markup = render({
      days: ['2026-10-14', '2026-10-15', '2026-10-16'],
      timeZone: NY,
      timed: [event9to10],
      allDay: [],
      now: null,
    })
    // Block appears exactly once
    expect(countOccurrences(markup, 'data-block-id="ev1"')).toBe(1)
  })

  it('zone matters: 14:00Z event in Kolkata has data-start-min="1170"', () => {
    // 14:00Z + 5:30 IST = 19:30 = 1170 minutes
    const event = {
      id: 'ev2',
      title: 'Evening Block',
      startAt: '2026-10-15T14:00:00Z',
      endAt: '2026-10-15T15:00:00Z',
      color: '#10B981',
    }
    const markup = render({
      days: ['2026-10-15'],
      timeZone: KO,
      timed: [event],
      allDay: [],
      now: null,
    })
    expect(markup).toContain('data-start-min="1170"')
  })

  it('zone matters: aria-label uses the Kolkata times', () => {
    // 14:00Z in KO = 7:30 PM IST; 15:00Z = 8:30 PM IST
    const event = {
      id: 'ev2',
      title: 'Evening Block',
      startAt: '2026-10-15T14:00:00Z',
      endAt: '2026-10-15T15:00:00Z',
      color: '#10B981',
    }
    const markup = render({
      days: ['2026-10-15'],
      timeZone: KO,
      timed: [event],
      allDay: [],
      now: null,
    })
    expect(markup).toContain('7:30 PM to 8:30 PM')
  })

  it('two overlapping events get data-lane 0 and 1 with data-lane-count 2', () => {
    const timed = [
      { id: 'a', title: 'A', startAt: '2026-10-15T14:00:00Z', endAt: '2026-10-15T15:00:00Z', color: '#f00' },
      { id: 'b', title: 'B', startAt: '2026-10-15T14:30:00Z', endAt: '2026-10-15T15:30:00Z', color: '#0f0' },
    ]
    const markup = render({ days: ['2026-10-15'], timeZone: NY, timed, allDay: [], now: null })
    expect(markup).toContain('data-lane="0"')
    expect(markup).toContain('data-lane="1"')
    expect(countOccurrences(markup, 'data-lane-count="2"')).toBe(2)
  })

  it('two touching events (end equals next start) both have data-lane-count 1', () => {
    const timed = [
      { id: 'a', title: 'A', startAt: '2026-10-15T14:00:00Z', endAt: '2026-10-15T15:00:00Z', color: '#f00' },
      { id: 'b', title: 'B', startAt: '2026-10-15T15:00:00Z', endAt: '2026-10-15T16:00:00Z', color: '#0f0' },
    ]
    const markup = render({ days: ['2026-10-15'], timeZone: NY, timed, allDay: [], now: null })
    expect(countOccurrences(markup, 'data-lane-count="1"')).toBe(2)
  })

  it('cross-midnight event has continues-after on first date and continues-before on second', () => {
    // 23:00 EDT Oct 15 = 03:00Z Oct 16; 01:00 EDT Oct 16 = 05:00Z Oct 16
    const timed = [{
      id: 'cx',
      title: 'Late Event',
      startAt: '2026-10-16T03:00:00Z',
      endAt: '2026-10-16T05:00:00Z',
      color: '#999',
    }]
    const markup = render({
      days: ['2026-10-15', '2026-10-16'],
      timeZone: NY,
      timed,
      allDay: [],
      now: null,
    })
    expect(countOccurrences(markup, 'data-block-id="cx"')).toBe(2)
    // Find the continues-after block
    expect(markup).toContain('data-continues-after="true"')
    expect(markup).toContain('data-continues-before="true"')
  })

  it('a 30-minute block does not show the start time as visible text', () => {
    // 13:00Z-13:30Z = 9:00-9:30 AM EDT; displayMin=30 < 45
    const timed = [{
      id: 'short',
      title: 'Short Event',
      startAt: '2026-10-15T13:00:00Z',
      endAt: '2026-10-15T13:30:00Z',
      color: '#888',
    }]
    const markup = render({ days: ['2026-10-15'], timeZone: NY, timed, allDay: [], now: null })
    // aria-label contains "9:00 AM" but it should NOT be a text node
    expect(markup).toContain('9:00 AM')  // in aria-label
    expect(markup).not.toMatch(/>9:00 AM</)  // not as visible text
  })

  it('a 90-minute block shows the start time as visible text', () => {
    // 13:00Z-14:30Z = 9:00-10:30 AM EDT; displayMin=90 >= 45
    const timed = [{
      id: 'long',
      title: 'Long Event',
      startAt: '2026-10-15T13:00:00Z',
      endAt: '2026-10-15T14:30:00Z',
      color: '#888',
    }]
    const markup = render({ days: ['2026-10-15'], timeZone: NY, timed, allDay: [], now: null })
    // "9:00 AM" should appear as a visible text node
    expect(markup).toMatch(/>9:00 AM</)
  })
})

// ---------------------------------------------------------------------------
// All day strip
// ---------------------------------------------------------------------------

describe('TimeGrid all day strip', () => {
  it('absent when there are no all day items', () => {
    const markup = render({ days: ['2026-10-15'], timeZone: NY, timed: [], allDay: [], now: null })
    expect(markup).not.toContain('data-allday-id')
  })

  it('renders chips with correct data-allday-id in the right day cells', () => {
    const allDay = [
      { id: 'h1', date: '2026-10-15', title: 'Holiday', color: '#f00' },
    ]
    const markup = render({
      days: ['2026-10-14', '2026-10-15', '2026-10-16'],
      timeZone: NY,
      timed: [],
      allDay,
      now: null,
    })
    expect(markup).toContain('data-allday-id="h1"')
    // Should appear exactly once
    expect(countOccurrences(markup, 'data-allday-id="h1"')).toBe(1)
  })

  it('all day item with date outside the days list is not rendered', () => {
    const allDay = [
      { id: 'out', date: '2026-10-13', title: 'Outside', color: '#f00' },
    ]
    const markup = render({
      days: ['2026-10-14', '2026-10-15', '2026-10-16'],
      timeZone: NY,
      timed: [],
      allDay,
      now: null,
    })
    expect(markup).not.toContain('data-allday-id="out"')
  })
})

// ---------------------------------------------------------------------------
// Now line
// ---------------------------------------------------------------------------

describe('TimeGrid now line', () => {
  const now = new Date('2026-10-15T14:00:00Z')

  it('renders the now line exactly once when now falls in the view', () => {
    const markup = render({
      days: ['2026-10-14', '2026-10-15', '2026-10-16'],
      timeZone: NY,
      timed: [],
      allDay: [],
      now,
    })
    expect(countOccurrences(markup, 'data-now-line="true"')).toBe(1)
  })

  it('does not render the now line when now is outside the days list', () => {
    const markup = render({
      days: ['2026-10-14', '2026-10-16'],
      timeZone: NY,
      timed: [],
      allDay: [],
      now,
    })
    expect(markup).not.toContain('data-now-line="true"')
  })

  it('now line top equals nowMinutes * pxPerMinute', () => {
    // 14:00Z - 4h EDT = 10:00 AM = 600 min; 600 * 0.8 = 480
    const markup = render({
      days: ['2026-10-15'],
      timeZone: NY,
      timed: [],
      allDay: [],
      now,
    })
    expect(markup).toContain('data-now-line="true"')
    // The top value is 480px (600 * 0.8)
    expect(markup).toMatch(/data-now-line="true"[^>]*style="top:480px"/)
  })
})

// ---------------------------------------------------------------------------
// Escaping
// ---------------------------------------------------------------------------

describe('TimeGrid escaping', () => {
  it('angle brackets and ampersands in titles are escaped in the markup', () => {
    const timed = [{
      id: 'sc',
      title: '<script> & "test"',
      startAt: '2026-10-15T13:00:00Z',
      endAt: '2026-10-15T14:00:00Z',
      color: '#f00',
    }]
    const markup = render({ days: ['2026-10-15'], timeZone: NY, timed, allDay: [], now: null })
    // Raw angle brackets and ampersand must not appear as literal characters in text nodes
    expect(markup).not.toContain('><script><')
    expect(markup).not.toContain('> & <')
    // Escaped forms must be present
    expect(markup).toContain('&lt;script&gt;')
    expect(markup).toContain('&amp;')
  })
})

// ---------------------------------------------------------------------------
// Errors
// ---------------------------------------------------------------------------

describe('TimeGrid errors', () => {
  it('rendering with an invalid time zone throws a RangeError', () => {
    expect(() =>
      render({
        days: ['2026-10-15'],
        timeZone: 'Not/AZone',
        timed: [],
        allDay: [],
        now: null,
      })
    ).toThrow(RangeError)
  })

  it('rendering two timed items with the same id throws', () => {
    const timed = [
      { id: 'dup', title: 'A', startAt: '2026-10-15T13:00:00Z', endAt: '2026-10-15T14:00:00Z', color: '#f00' },
      { id: 'dup', title: 'B', startAt: '2026-10-15T15:00:00Z', endAt: '2026-10-15T16:00:00Z', color: '#0f0' },
    ]
    expect(() =>
      render({ days: ['2026-10-15'], timeZone: NY, timed, allDay: [], now: null })
    ).toThrow('duplicate item id "dup"')
  })

  it('rendering without onItemClick does not throw', () => {
    expect(() =>
      render({ days: ['2026-10-15'], timeZone: NY, timed: [], allDay: [], now: null })
    ).not.toThrow()
  })
})

// ---------------------------------------------------------------------------
// Empty inputs
// ---------------------------------------------------------------------------

describe('TimeGrid empty inputs', () => {
  it('empty timed and allDay render the grid with no blocks and no errors', () => {
    const markup = render({ days: ['2026-10-14', '2026-10-15'], timeZone: NY, timed: [], allDay: [], now: null })
    expect(markup).not.toContain('data-block-id')
    expect(markup).not.toContain('data-allday-id')
    // Hour labels are still present
    expect(markup).toContain('1 AM')
  })
})

// ---------------------------------------------------------------------------
// Input mutation
// ---------------------------------------------------------------------------

describe('TimeGrid input mutation', () => {
  it('does not mutate the timed or allDay input arrays', () => {
    const timed = [
      { id: 'a', title: 'A', startAt: '2026-10-15T13:00:00Z', endAt: '2026-10-15T14:00:00Z', color: '#f00' },
    ]
    const allDay = [{ id: 'h', date: '2026-10-15', title: 'H', color: '#aaa' }]
    const timedCopy = timed.map(x => ({ ...x }))
    const allDayCopy = allDay.map(x => ({ ...x }))

    render({ days: ['2026-10-15'], timeZone: NY, timed, allDay, now: null })

    expect(timed[0]).toEqual(timedCopy[0])
    expect(allDay[0]).toEqual(allDayCopy[0])
  })
})
