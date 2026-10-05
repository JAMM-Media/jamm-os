// path: frontend/src/components/calendar/TimeGrid.zone.test.tsx
import { describe, it, expect } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { TimeGrid } from './TimeGrid'

// ---------------------------------------------------------------------------
// Helpers (same pattern as TimeGrid.test.tsx)
// ---------------------------------------------------------------------------

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

// Return the ~200 characters of markup starting at data-today, so we can
// check which cell carries it without parsing a full DOM tree.
function todayCellContext(markup: string): string {
  const idx = markup.indexOf('data-today="true"')
  if (idx === -1) return ''
  return markup.slice(idx, idx + 200)
}

const DAYS = ['2026-10-14', '2026-10-15', '2026-10-16']

// ---------------------------------------------------------------------------
// Near-midnight zone proofs
// ---------------------------------------------------------------------------

describe('TimeGrid firm zone near midnight: today highlight', () => {
  it('a: 02:00Z Oct 16 is 22:00 Oct 15 in New York -- today is Oct 15', () => {
    // 2026-10-16T02:00:00Z - 4h (EDT) = 22:00 on 2026-10-15
    // today = '2026-10-15', Oct 15 = Thursday
    const now = new Date('2026-10-16T02:00:00Z')
    const markup = render({ days: DAYS, timeZone: 'America/New_York', timed: [], allDay: [], now })
    expect(countOccurrences(markup, 'data-today="true"')).toBe(1)
    // The cell with data-today must contain '15' (the day number for Oct 15)
    expect(todayCellContext(markup)).toContain('>15<')
    // Oct 15 is Thursday
    expect(todayCellContext(markup)).toContain('>Thu<')
  })

  it('b: 02:00Z Oct 16 is 07:30 Oct 16 in Kolkata -- today is Oct 16', () => {
    // 2026-10-16T02:00:00Z + 5:30 (IST) = 07:30 on 2026-10-16
    // today = '2026-10-16', Oct 16 = Friday
    const now = new Date('2026-10-16T02:00:00Z')
    const markup = render({ days: DAYS, timeZone: 'Asia/Kolkata', timed: [], allDay: [], now })
    expect(countOccurrences(markup, 'data-today="true"')).toBe(1)
    expect(todayCellContext(markup)).toContain('>16<')
    // Oct 16 is Friday
    expect(todayCellContext(markup)).toContain('>Fri<')
  })

  it('c: 03:30Z Oct 15 is 23:30 Oct 14 in New York -- today is Oct 14', () => {
    // 2026-10-15T03:30:00Z - 4h (EDT) = 23:30 on 2026-10-14
    // today = '2026-10-14', Oct 14 = Wednesday
    const now = new Date('2026-10-15T03:30:00Z')
    const markup = render({ days: DAYS, timeZone: 'America/New_York', timed: [], allDay: [], now })
    expect(countOccurrences(markup, 'data-today="true"')).toBe(1)
    expect(todayCellContext(markup)).toContain('>14<')
    // Oct 14 is Wednesday
    expect(todayCellContext(markup)).toContain('>Wed<')
  })

  it('d: 04:00Z Oct 15 is exactly midnight Oct 15 in New York -- today is Oct 15', () => {
    // 2026-10-15T04:00:00Z - 4h (EDT) = 00:00 on 2026-10-15 (local midnight)
    // today = '2026-10-15', Oct 15 = Thursday
    const now = new Date('2026-10-15T04:00:00Z')
    const markup = render({ days: DAYS, timeZone: 'America/New_York', timed: [], allDay: [], now })
    expect(countOccurrences(markup, 'data-today="true"')).toBe(1)
    expect(todayCellContext(markup)).toContain('>15<')
    expect(todayCellContext(markup)).toContain('>Thu<')
  })

  it('e: 02:00Z Oct 16 is 19:00 Oct 15 in Los Angeles -- today is Oct 15', () => {
    // 2026-10-16T02:00:00Z - 7h (PDT) = 19:00 on 2026-10-15
    // today = '2026-10-15', Oct 15 = Thursday
    const now = new Date('2026-10-16T02:00:00Z')
    const markup = render({ days: DAYS, timeZone: 'America/Los_Angeles', timed: [], allDay: [], now })
    expect(countOccurrences(markup, 'data-today="true"')).toBe(1)
    expect(todayCellContext(markup)).toContain('>15<')
    expect(todayCellContext(markup)).toContain('>Thu<')
  })
})

describe('TimeGrid firm zone near midnight: now line position', () => {
  it('a: 02:00Z Oct 16 in New York: now line top = 1320 * 0.8 = 1056px', () => {
    // 22:00 = 22 * 60 = 1320 minutes; 1320 * 0.8 = 1056
    const now = new Date('2026-10-16T02:00:00Z')
    const markup = render({ days: DAYS, timeZone: 'America/New_York', timed: [], allDay: [], now })
    expect(countOccurrences(markup, 'data-now-line="true"')).toBe(1)
    expect(markup).toMatch(/data-now-line="true"[^>]*style="top:1056px"/)
  })

  it('b: 02:00Z Oct 16 in Kolkata: now line top = 450 * 0.8 = 360px', () => {
    // 07:30 = 7 * 60 + 30 = 450 minutes; 450 * 0.8 = 360
    const now = new Date('2026-10-16T02:00:00Z')
    const markup = render({ days: DAYS, timeZone: 'Asia/Kolkata', timed: [], allDay: [], now })
    expect(countOccurrences(markup, 'data-now-line="true"')).toBe(1)
    expect(markup).toMatch(/data-now-line="true"[^>]*style="top:360px"/)
  })

  it('c: 03:30Z Oct 15 in New York: now line top = 1410 * 0.8 = 1128px', () => {
    // 23:30 = 23 * 60 + 30 = 1410 minutes; 1410 * 0.8 = 1128
    const now = new Date('2026-10-15T03:30:00Z')
    const markup = render({ days: DAYS, timeZone: 'America/New_York', timed: [], allDay: [], now })
    expect(countOccurrences(markup, 'data-now-line="true"')).toBe(1)
    expect(markup).toMatch(/data-now-line="true"[^>]*style="top:1128px"/)
  })

  it('d: 04:00Z Oct 15 in New York (midnight): now line top = 0 * 0.8 = 0', () => {
    // 00:00 = 0 minutes; 0 * 0.8 = 0; React renders 0 without px unit
    const now = new Date('2026-10-15T04:00:00Z')
    const markup = render({ days: DAYS, timeZone: 'America/New_York', timed: [], allDay: [], now })
    expect(countOccurrences(markup, 'data-now-line="true"')).toBe(1)
    expect(markup).toMatch(/data-now-line="true"[^>]*style="top:0"/)
  })

  it('e: 02:00Z Oct 16 in Los Angeles: now line top = 1140 * 0.8 = 912px', () => {
    // 19:00 = 19 * 60 = 1140 minutes; 1140 * 0.8 = 912
    const now = new Date('2026-10-16T02:00:00Z')
    const markup = render({ days: DAYS, timeZone: 'America/Los_Angeles', timed: [], allDay: [], now })
    expect(countOccurrences(markup, 'data-now-line="true"')).toBe(1)
    expect(markup).toMatch(/data-now-line="true"[^>]*style="top:912px"/)
  })
})
