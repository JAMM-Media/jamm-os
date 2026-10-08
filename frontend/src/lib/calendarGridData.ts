// path: frontend/src/lib/calendarGridData.ts
import type { TimeGridTimedEvent, TimeGridAllDayItem } from '../components/calendar/TimeGrid'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

export const FALLBACK_EVENT_COLOR = '#9CA3AF'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface PageEvent {
  id: string
  title: string
  date: string
  type: string
  startAt?: string | null
  endAt?: string | null
  color?: string | null
}

// ---------------------------------------------------------------------------
// hasOffset
// ---------------------------------------------------------------------------

// Returns true only when s ends with Z or a numeric offset written with a
// colon (+05:30 or -04:00) AND Date.parse(s) is not NaN.
// This is at least as strict as the toDate guard inside calendarTime.ts, so
// any string this accepts will not throw there.
export function hasOffset(s: string): boolean {
  if (typeof s !== 'string' || s.length === 0) return false
  if (!/Z$/.test(s) && !/[+-]\d{2}:\d{2}$/.test(s)) return false
  return !isNaN(Date.parse(s))
}

// ---------------------------------------------------------------------------
// buildGridInputs
// ---------------------------------------------------------------------------

const COLOR_RE = /^#[0-9A-Fa-f]{6}$/

export function buildGridInputs(
  events: PageEvent[],
  colors: Record<string, string>
): { timed: TimeGridTimedEvent[]; allDay: TimeGridAllDayItem[] } {
  const timed: TimeGridTimedEvent[] = []
  const allDay: TimeGridAllDayItem[] = []
  const seen = new Set<string>()

  for (const ev of events) {
    // Rule a: first occurrence wins; subsequent ids are skipped.
    if (seen.has(ev.id)) continue
    seen.add(ev.id)

    // Rule c: an event's own color wins when it matches COLOR_RE; otherwise the
    // type color from the colors map when that matches COLOR_RE; otherwise FALLBACK_EVENT_COLOR.
    const ownColor = typeof ev.color === 'string' && COLOR_RE.test(ev.color) ? ev.color : null
    const typeColor = (() => { const r = colors[ev.type]; return typeof r === 'string' && COLOR_RE.test(r) ? r : null })()
    const color = ownColor ?? typeColor ?? FALLBACK_EVENT_COLOR

    // Rule b: timed only when both startAt and endAt have an offset and
    // endAt is strictly after startAt.
    if (
      typeof ev.startAt === 'string' &&
      typeof ev.endAt === 'string' &&
      hasOffset(ev.startAt) &&
      hasOffset(ev.endAt) &&
      Date.parse(ev.endAt) > Date.parse(ev.startAt)
    ) {
      timed.push({
        id: ev.id,
        title: ev.title,
        startAt: ev.startAt,
        endAt: ev.endAt,
        color,
      })
    } else {
      // Rule b fallback: nothing disappears.
      allDay.push({
        id: ev.id,
        date: ev.date,
        title: ev.title,
        color,
      })
    }
  }

  return { timed, allDay }
}

// ---------------------------------------------------------------------------
// isValidTimeZone
// ---------------------------------------------------------------------------

export function isValidTimeZone(tz: string): boolean {
  if (!tz) return false
  try {
    new Intl.DateTimeFormat('en-US', { timeZone: tz })
    return true
  } catch {
    return false
  }
}

// ---------------------------------------------------------------------------
// formatDayTitle
// ---------------------------------------------------------------------------

export function formatDayTitle(dateStr: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(dateStr)
  if (!m) throw new RangeError(`malformed dateStr: ${dateStr}`)
  const year = parseInt(m[1]!, 10)
  const month = parseInt(m[2]!, 10)
  const day = parseInt(m[3]!, 10)
  if (month < 1 || month > 12 || day < 1 || day > 31) {
    throw new RangeError(`invalid date values in dateStr: ${dateStr}`)
  }
  return new Intl.DateTimeFormat('en-US', {
    timeZone: 'UTC',
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  }).format(new Date(Date.UTC(year, month - 1, day)))
}
