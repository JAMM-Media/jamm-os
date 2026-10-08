// path: frontend/src/lib/calendarMonthGrid.ts
// Pure UTC date arithmetic throughout: no local-time Date constructors, so
// a daylight saving change cannot affect the output.

export const WEEKDAY_LABELS = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'] as const

const MONTH_NAMES_FULL = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
]

export interface MonthGridCell {
  dateStr: string
  day: number
  inMonth: boolean
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function buildUTCDate(year: number, month: number, day: number): Date {
  return new Date(Date.UTC(year, month - 1, day))
}

function formatUTCDate(d: Date): string {
  return (
    `${d.getUTCFullYear()}-` +
    `${String(d.getUTCMonth() + 1).padStart(2, '0')}-` +
    `${String(d.getUTCDate()).padStart(2, '0')}`
  )
}

// ---------------------------------------------------------------------------
// Exported utilities
// ---------------------------------------------------------------------------

// Pure UTC add-days for use by callers that must not be affected by DST.
export function addDaysUTC(dateStr: string, n: number): string {
  const parts = dateStr.split('-')
  const d = buildUTCDate(
    parseInt(parts[0]!, 10),
    parseInt(parts[1]!, 10),
    parseInt(parts[2]!, 10) + n,
  )
  return formatUTCDate(d)
}

export function shiftMonth(year: number, month: number, delta: number): { year: number; month: number } {
  const total = year * 12 + (month - 1) + delta
  return {
    year: Math.floor(total / 12),
    month: ((total % 12) + 12) % 12 + 1,
  }
}

export function monthTitle(year: number, month: number): string {
  return `${MONTH_NAMES_FULL[month - 1]} ${year}`
}

// Always returns 6 rows of 7 cells. Weeks start on Sunday.
// Leading cells from the previous month and trailing cells from the next
// month have inMonth = false.
export function buildMonthGrid(year: number, month: number): MonthGridCell[][] {
  if (!Number.isInteger(year)) {
    throw new RangeError(`year must be an integer, got: ${year}`)
  }
  if (month < 1 || month > 12) {
    throw new RangeError(`month must be 1 to 12, got: ${month}`)
  }

  // Day of week of the 1st (0 = Sunday, 6 = Saturday), computed in UTC.
  const startDow = buildUTCDate(year, month, 1).getUTCDay()

  const grid: MonthGridCell[][] = []
  for (let row = 0; row < 6; row++) {
    const cells: MonthGridCell[] = []
    for (let col = 0; col < 7; col++) {
      const i = row * 7 + col
      const absoluteDay = 1 - startDow + i
      const d = buildUTCDate(year, month, absoluteDay)
      const curMonth = d.getUTCMonth() + 1
      const curYear = d.getUTCFullYear()
      cells.push({
        dateStr: formatUTCDate(d),
        day: d.getUTCDate(),
        inMonth: curMonth === month && curYear === year,
      })
    }
    grid.push(cells)
  }
  return grid
}
