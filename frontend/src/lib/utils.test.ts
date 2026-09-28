// frontend/src/lib/utils.test.ts
import { describe, it, expect, vi, afterEach } from 'vitest'
import { localDateStr, formatLocalDate, getEffectiveDueDate, filterUpcomingByDate, startOfWeek, addDaysStr, filterByDateRange } from './utils'

// ---------------------------------------------------------------------------
// localDateStr
// ---------------------------------------------------------------------------

describe('localDateStr', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('returns YYYY-MM-DD matching local year/month/day, not UTC', () => {
    // 2026-09-28T01:00:00Z = Sep 27 at 9pm in America/New_York (UTC-4)
    // The old toISOString() implementation returns the UTC date "2026-09-28",
    // while localDateStr must return the local date "2026-09-27" when run
    // in a UTC-behind timezone.
    // We test the contract: result must equal the local-method date string.
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-09-28T01:00:00.000Z'))
    const d = new Date()
    const result = localDateStr(d)
    // Must match local date methods, not UTC
    const expected = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
    expect(result).toBe(expected)
  })

  it('returns Sep 27 for a Date constructed as local Sep 27', () => {
    const d = new Date(2026, 8, 27)
    expect(localDateStr(d)).toBe('2026-09-27')
  })

  it('zero-pads month and day', () => {
    expect(localDateStr(new Date(2026, 0, 5))).toBe('2026-01-05')
  })

  it('returns the local date even at a late-local-time that is already next day in UTC', () => {
    // Construct a Date that is end of day in UTC-behind timezone.
    // new Date(2026, 8, 27, 23, 0, 0) = Sep 27 local, but toISOString
    // converts to UTC which, in a UTC-behind env, would be "2026-09-28".
    // localDateStr reads getDate() (local) so always returns "2026-09-27".
    const d = new Date(2026, 8, 27, 23, 0, 0)
    expect(localDateStr(d)).toBe('2026-09-27')
    // toISOString would give the UTC date, which may differ in UTC-behind zones.
    // In UTC itself both are "2026-09-27", so we cannot assert inequality here
    // without TZ control. What we CAN assert is that localDateStr is consistent
    // with the local date methods.
    const viaLocalMethods = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
    expect(localDateStr(d)).toBe(viaLocalMethods)
  })
})

// ---------------------------------------------------------------------------
// formatLocalDate
// ---------------------------------------------------------------------------

describe('formatLocalDate', () => {
  it('renders 2026-06-09 as Jun 9, 2026 regardless of timezone', () => {
    // The old formatDate used new Date("2026-06-09") which parses as UTC midnight,
    // causing off-by-one in US timezones. formatLocalDate splits the string and
    // uses the multi-arg constructor, so the result is always Jun 9.
    expect(formatLocalDate('2026-06-09')).toBe('Jun 9, 2026')
  })

  it('renders 2026-04-15 as Apr 15, 2026', () => {
    expect(formatLocalDate('2026-04-15')).toBe('Apr 15, 2026')
  })

  it('returns fallback for null', () => {
    expect(formatLocalDate(null)).toBe('—')
  })

  it('returns fallback for undefined', () => {
    expect(formatLocalDate(undefined)).toBe('—')
  })

  it('returns custom fallback when provided', () => {
    expect(formatLocalDate(null, undefined, 'N/A')).toBe('N/A')
  })

  it('uses provided options', () => {
    const result = formatLocalDate('2026-06-09', { month: 'long', day: 'numeric', year: 'numeric' })
    expect(result).toContain('June')
    expect(result).toContain('2026')
  })
})

// ---------------------------------------------------------------------------
// getEffectiveDueDate
// ---------------------------------------------------------------------------

describe('getEffectiveDueDate', () => {
  it('returns extendedDeadline when all three are set', () => {
    expect(getEffectiveDueDate({
      extendedDeadline: '2026-10-15',
      filingDeadline: '2026-04-15',
      endDate: '2026-06-09',
    })).toBe('2026-10-15')
  })

  it('falls back to filingDeadline when extendedDeadline is null', () => {
    expect(getEffectiveDueDate({
      extendedDeadline: null,
      filingDeadline: '2026-04-15',
      endDate: '2026-06-09',
    })).toBe('2026-04-15')
  })

  it('falls back to endDate when both extended and filing are null', () => {
    expect(getEffectiveDueDate({
      extendedDeadline: null,
      filingDeadline: null,
      endDate: '2026-06-09',
    })).toBe('2026-06-09')
  })

  it('returns null when all three are null', () => {
    expect(getEffectiveDueDate({
      extendedDeadline: null,
      filingDeadline: null,
      endDate: null,
    })).toBeNull()
  })
})

// ---------------------------------------------------------------------------
// filterUpcomingByDate
// ---------------------------------------------------------------------------

describe('filterUpcomingByDate', () => {
  const events = [
    { id: '1', date: '2026-09-26', type: 'holiday' as const },
    { id: '2', date: '2026-09-27', type: 'deadline' as const },
    { id: '3', date: '2026-09-28', type: 'task' as const },
    { id: '4', date: '2026-09-29', type: 'holiday' as const },
    { id: '5', date: '2026-10-01', type: 'meeting' as const },
  ]

  it('excludes events dated before today', () => {
    const result = filterUpcomingByDate(events, '2026-09-28')
    expect(result.map(e => e.date)).toEqual(['2026-09-28', '2026-09-29', '2026-10-01'])
  })

  it('includes events on today', () => {
    const result = filterUpcomingByDate(events, '2026-09-28')
    expect(result.some(e => e.date === '2026-09-28')).toBe(true)
  })

  it('excludes all past events when todayStr is the last date', () => {
    const result = filterUpcomingByDate(events, '2026-10-01')
    expect(result.map(e => e.date)).toEqual(['2026-10-01'])
  })

  it('returns empty array when all events are in the past', () => {
    expect(filterUpcomingByDate(events, '2026-11-01')).toEqual([])
  })
})

// ---------------------------------------------------------------------------
// startOfWeek
// ---------------------------------------------------------------------------

describe('startOfWeek', () => {
  it('returns the same day when that day is already Sunday', () => {
    const sun = new Date(2026, 8, 27)  // Sep 27, Sunday
    expect(localDateStr(startOfWeek(sun))).toBe('2026-09-27')
  })

  it('returns Sunday Sep 27 for Monday Sep 28', () => {
    const mon = new Date(2026, 8, 28)  // Sep 28, Monday
    expect(localDateStr(startOfWeek(mon))).toBe('2026-09-27')
  })

  it('week starting from today contains today', () => {
    const today = new Date(2026, 8, 28)
    const sun = startOfWeek(today)
    const days: string[] = []
    for (let i = 0; i < 7; i++) {
      const d = new Date(sun)
      d.setDate(d.getDate() + i)
      days.push(localDateStr(d))
    }
    expect(days).toContain('2026-09-28')
  })

  it('week starting from first-of-month does NOT contain mid-month today', () => {
    const firstOfMonth = new Date(2026, 8, 1)  // Sep 1, Tuesday
    const today = new Date(2026, 8, 28)
    const sun = startOfWeek(firstOfMonth)
    const days: string[] = []
    for (let i = 0; i < 7; i++) {
      const d = new Date(sun)
      d.setDate(d.getDate() + i)
      days.push(localDateStr(d))
    }
    expect(days).not.toContain(localDateStr(today))
  })

  it('does not mutate the input date', () => {
    const d = new Date(2026, 8, 28)
    const original = localDateStr(d)
    startOfWeek(d)
    expect(localDateStr(d)).toBe(original)
  })
})

// ---------------------------------------------------------------------------
// addDaysStr
// ---------------------------------------------------------------------------

describe('addDaysStr', () => {
  it('adds positive days within the same month', () => {
    expect(addDaysStr('2026-09-28', 3)).toBe('2026-10-01')
  })

  it('crosses a month end correctly', () => {
    expect(addDaysStr('2026-01-29', 3)).toBe('2026-02-01')
  })

  it('crosses a year end correctly', () => {
    expect(addDaysStr('2026-12-30', 3)).toBe('2027-01-02')
  })

  it('handles negative n (moves backward)', () => {
    expect(addDaysStr('2026-10-01', -3)).toBe('2026-09-28')
  })

  it('zero n returns the same date', () => {
    expect(addDaysStr('2026-09-28', 0)).toBe('2026-09-28')
  })
})

// ---------------------------------------------------------------------------
// filterByDateRange
// ---------------------------------------------------------------------------

describe('filterByDateRange', () => {
  const events = [
    { id: '1', date: '2026-09-27' },
    { id: '2', date: '2026-09-28' },
    { id: '3', date: '2026-10-05' },
    { id: '4', date: '2026-10-11' },
    { id: '5', date: '2026-10-12' },
  ]

  it('includes both boundary dates', () => {
    const result = filterByDateRange(events, '2026-09-28', '2026-10-11')
    expect(result.map(e => e.date)).toEqual(['2026-09-28', '2026-10-05', '2026-10-11'])
  })

  it('excludes items before startStr', () => {
    const result = filterByDateRange(events, '2026-09-28', '2026-10-11')
    expect(result.some(e => e.date === '2026-09-27')).toBe(false)
  })

  it('excludes items after endStr', () => {
    const result = filterByDateRange(events, '2026-09-28', '2026-10-11')
    expect(result.some(e => e.date === '2026-10-12')).toBe(false)
  })

  it('returns empty array when no events fall in range', () => {
    expect(filterByDateRange(events, '2026-11-01', '2026-11-14')).toEqual([])
  })

  it('returns all events when range covers everything', () => {
    const result = filterByDateRange(events, '2026-09-27', '2026-10-12')
    expect(result).toHaveLength(5)
  })
})
