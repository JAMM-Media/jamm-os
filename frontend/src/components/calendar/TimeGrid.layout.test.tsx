// path: frontend/src/components/calendar/TimeGrid.layout.test.tsx
import { describe, it, expect } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { TimeGrid } from './TimeGrid'

// ---------------------------------------------------------------------------
// Helpers (same pattern as TimeGrid.zone.test.tsx)
// ---------------------------------------------------------------------------

function render(props: React.ComponentProps<typeof TimeGrid>): string {
  return renderToStaticMarkup(<TimeGrid {...props} />)
}

function countOccurrences(str: string, sub: string): number {
  let count = 0
  let pos = 0
  while ((pos = str.indexOf(sub, pos)) !== -1) { count++; pos += sub.length }
  return count
}

// Extract the opening <div> tag that contains a given data attribute.
function openingTag(markup: string, attr: string): string | null {
  const re = new RegExp(`<div[^>]*${attr}[^>]*>`)
  const match = re.exec(markup)
  return match ? match[0] : null
}

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const DAYS_7 = [
  '2026-10-11', '2026-10-12', '2026-10-13', '2026-10-14',
  '2026-10-15', '2026-10-16', '2026-10-17',
]
const TZ = 'America/New_York'
const ALLDAY_ITEM = { id: 'a1', date: '2026-10-16', title: 'Deadline', color: '#B4534B' }

const baseProps: React.ComponentProps<typeof TimeGrid> = {
  days: DAYS_7,
  timeZone: TZ,
  timed: [],
  allDay: [ALLDAY_ITEM],
  now: null,
}

const noAllDayProps: React.ComponentProps<typeof TimeGrid> = {
  ...baseProps,
  allDay: [],
}

// ---------------------------------------------------------------------------
// Layout marker tests
// ---------------------------------------------------------------------------

describe('TimeGrid layout markers and scrollbar gutter', () => {
  it('a: with allDay items all three markers are present and each opening tag contains scrollbar-gutter:stable', () => {
    const markup = render(baseProps)
    const headerTag = openingTag(markup, 'data-grid-header')
    const alldayTag = openingTag(markup, 'data-grid-allday')
    const scrollTag = openingTag(markup, 'data-grid-scroll')

    expect(headerTag, 'data-grid-header missing').toBeTruthy()
    expect(alldayTag, 'data-grid-allday missing').toBeTruthy()
    expect(scrollTag, 'data-grid-scroll missing').toBeTruthy()

    expect(headerTag).toContain('scrollbar-gutter:stable')
    expect(alldayTag).toContain('scrollbar-gutter:stable')
    expect(scrollTag).toContain('scrollbar-gutter:stable')
  })

  it('b: without allDay items header and scroll markers are present and data-grid-allday does not appear', () => {
    const markup = render(noAllDayProps)

    expect(openingTag(markup, 'data-grid-header'), 'data-grid-header missing').toBeTruthy()
    expect(openingTag(markup, 'data-grid-scroll'), 'data-grid-scroll missing').toBeTruthy()
    expect(markup).not.toContain('data-grid-allday')
  })

  it('c: header and allday tags contain overflow-y-hidden; scroll tag contains overflow-y-auto and not overflow-y-hidden', () => {
    const markup = render(baseProps)
    const headerTag = openingTag(markup, 'data-grid-header')!
    const alldayTag = openingTag(markup, 'data-grid-allday')!
    const scrollTag = openingTag(markup, 'data-grid-scroll')!

    expect(headerTag).toContain('overflow-y-hidden')
    expect(alldayTag).toContain('overflow-y-hidden')
    expect(scrollTag).toContain('overflow-y-auto')
    expect(scrollTag).not.toContain('overflow-y-hidden')
  })

  it('d: 7-day render has one header cell per day; 1-day render has exactly one', () => {
    const markup7 = render(baseProps)

    // Oct 11-17 2026 is Sun-Sat; each name must appear exactly once
    for (const name of ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']) {
      expect(countOccurrences(markup7, `>${name}<`), `${name} count in 7-day render`).toBe(1)
    }

    // Oct 15 2026 = Thursday; only Thu should appear
    const markup1 = render({ ...baseProps, days: ['2026-10-15'] })
    expect(countOccurrences(markup1, '>Thu<')).toBe(1)
    for (const name of ['Sun', 'Mon', 'Tue', 'Wed', 'Fri', 'Sat']) {
      expect(countOccurrences(markup1, `>${name}<`), `${name} must not appear in 1-day render`).toBe(0)
    }
  })

  it('e: header opening tag is identical whether or not allDay items are present', () => {
    const tagWith = openingTag(render(baseProps), 'data-grid-header')
    const tagWithout = openingTag(render(noAllDayProps), 'data-grid-header')
    expect(tagWith).toBe(tagWithout)
  })
})
