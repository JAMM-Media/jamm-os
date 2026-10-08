// path: frontend/src/lib/calendarMonthGrid.test.ts
import { describe, it, expect } from 'vitest'
import {
  WEEKDAY_LABELS,
  buildMonthGrid,
  shiftMonth,
  monthTitle,
  addDaysUTC,
} from './calendarMonthGrid'

// ---------------------------------------------------------------------------
// WEEKDAY_LABELS
// ---------------------------------------------------------------------------

describe('WEEKDAY_LABELS', () => {
  it('has 7 entries starting with Su', () => {
    expect(WEEKDAY_LABELS).toHaveLength(7)
    expect(WEEKDAY_LABELS[0]).toBe('Su')
    expect(WEEKDAY_LABELS[6]).toBe('Sa')
  })
})

// ---------------------------------------------------------------------------
// buildMonthGrid
// ---------------------------------------------------------------------------

describe('buildMonthGrid', () => {
  it('always returns 6 rows of 7 cells', () => {
    const months = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
    for (const m of months) {
      const grid = buildMonthGrid(2026, m)
      expect(grid).toHaveLength(6)
      for (const row of grid) {
        expect(row).toHaveLength(7)
      }
    }
  })

  it('October 2026 starts on Thursday: first row starts with 2026-09-27', () => {
    const grid = buildMonthGrid(2026, 10)
    // Oct 1 2026 is Thursday (dow = 4), so leading cells come from Sept.
    expect(grid[0]![0]!.dateStr).toBe('2026-09-27')
    expect(grid[0]![0]!.inMonth).toBe(false)
  })

  it('October 2026: first inMonth cell is 2026-10-01 in column 4 (Thursday)', () => {
    const grid = buildMonthGrid(2026, 10)
    expect(grid[0]![4]!.dateStr).toBe('2026-10-01')
    expect(grid[0]![4]!.inMonth).toBe(true)
  })

  it('October 2026: last cell is 2026-11-07', () => {
    const grid = buildMonthGrid(2026, 10)
    const lastRow = grid[5]!
    expect(lastRow[6]!.dateStr).toBe('2026-11-07')
    expect(lastRow[6]!.inMonth).toBe(false)
  })

  it('November 2026 starts on Sunday: first cell is 2026-11-01 and inMonth is true', () => {
    // DST fall-back month; the grid must not be affected by clock changes.
    const grid = buildMonthGrid(2026, 11)
    expect(grid[0]![0]!.dateStr).toBe('2026-11-01')
    expect(grid[0]![0]!.inMonth).toBe(true)
  })

  it('March 2026 first cell is 2026-03-01 (spring-forward month, starts on Sunday)', () => {
    const grid = buildMonthGrid(2026, 3)
    expect(grid[0]![0]!.dateStr).toBe('2026-03-01')
    expect(grid[0]![0]!.inMonth).toBe(true)
  })

  it('February 2027 (not a leap year) has exactly 28 inMonth cells', () => {
    const grid = buildMonthGrid(2027, 2)
    const inMonth = grid.flat().filter((c) => c.inMonth)
    expect(inMonth).toHaveLength(28)
  })

  it('February 2028 (leap year) has exactly 29 inMonth cells', () => {
    const grid = buildMonthGrid(2028, 2)
    const inMonth = grid.flat().filter((c) => c.inMonth)
    expect(inMonth).toHaveLength(29)
  })

  it('every row across all 12 months of 2026 advances exactly one day per cell', () => {
    for (let m = 1; m <= 12; m++) {
      const grid = buildMonthGrid(2026, m)
      const all = grid.flat()
      for (let i = 1; i < all.length; i++) {
        const prev = all[i - 1]!.dateStr
        const curr = all[i]!.dateStr
        expect(addDaysUTC(prev, 1)).toBe(curr)
      }
    }
  })

  it('throws RangeError for month 0', () => {
    expect(() => buildMonthGrid(2026, 0)).toThrow(RangeError)
  })

  it('throws RangeError for month 13', () => {
    expect(() => buildMonthGrid(2026, 13)).toThrow(RangeError)
  })

  it('throws RangeError for non-integer year 2026.5', () => {
    expect(() => buildMonthGrid(2026.5, 10)).toThrow(RangeError)
  })
})

// ---------------------------------------------------------------------------
// shiftMonth
// ---------------------------------------------------------------------------

describe('shiftMonth', () => {
  it('December 2026 +1 gives January 2027', () => {
    expect(shiftMonth(2026, 12, 1)).toEqual({ year: 2027, month: 1 })
  })

  it('January 2027 -1 gives December 2026', () => {
    expect(shiftMonth(2027, 1, -1)).toEqual({ year: 2026, month: 12 })
  })

  it('+13 from some base works across a year boundary', () => {
    // 13 months from October 2026 = November 2027
    expect(shiftMonth(2026, 10, 13)).toEqual({ year: 2027, month: 11 })
  })

  it('-25 from some base works across multiple year boundaries', () => {
    // 25 months before December 2026 = November 2024
    expect(shiftMonth(2026, 12, -25)).toEqual({ year: 2024, month: 11 })
  })

  it('delta 0 returns the same year and month', () => {
    expect(shiftMonth(2026, 5, 0)).toEqual({ year: 2026, month: 5 })
  })
})

// ---------------------------------------------------------------------------
// monthTitle
// ---------------------------------------------------------------------------

describe('monthTitle', () => {
  it('returns October 2026 for month 10', () => {
    expect(monthTitle(2026, 10)).toBe('October 2026')
  })

  it('returns January for month 1', () => {
    expect(monthTitle(2027, 1)).toBe('January 2027')
  })

  it('returns December for month 12', () => {
    expect(monthTitle(2025, 12)).toBe('December 2025')
  })
})
