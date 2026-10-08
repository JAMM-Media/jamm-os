// path: frontend/src/lib/calendarPickDate.ts

// Returns a local Date at noon on the given YYYY-MM-DD string, or null if the
// value is not exactly that format or represents an impossible date. Noon is
// used so that a daylight saving change (which occurs at 02:00) can never move
// the date to a neighbouring day.
export function parsePickedDate(value: string): Date | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  if (!m) return null
  const year = parseInt(m[1]!, 10)
  const month = parseInt(m[2]!, 10)
  const day = parseInt(m[3]!, 10)
  const d = new Date(year, month - 1, day, 12, 0, 0, 0)
  if (d.getFullYear() !== year || d.getMonth() !== month - 1 || d.getDate() !== day) {
    return null
  }
  return d
}
