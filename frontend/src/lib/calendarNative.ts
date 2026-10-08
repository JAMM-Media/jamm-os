// path: frontend/src/lib/calendarNative.ts
import type { CalendarEvent } from './api/calendarEvents'
import { hasOffset } from './calendarGridData'
import { wallTimeToInstant, zonedDateStr } from './calendarTime'
import { weekDates } from './calendarGrid'

export const NATIVE_ID_PREFIX = 'nat-'

export interface NativeCalEvent {
  id: string
  title: string
  date: string
  type: 'meeting'
  assignedTo: string | null
  startAt: string
  endAt: string
  color: string | null
  categoryName: string | null
  clientName: string | null
  ownerName: string | null
}

const _COLOR_RE = /^#[0-9A-Fa-f]{6}$/

export function mapNativeEvents(events: CalendarEvent[], timeZone: string): NativeCalEvent[] {
  if (events.length === 0) return []
  const seen = new Set<string>()
  const result: NativeCalEvent[] = []
  for (const ev of events) {
    if (ev.deletedAt !== null) continue
    if (!hasOffset(ev.startAt) || !hasOffset(ev.endAt)) continue
    if (Date.parse(ev.endAt) <= Date.parse(ev.startAt)) continue
    if (seen.has(ev.id)) continue
    seen.add(ev.id)
    const date = zonedDateStr(ev.startAt, timeZone)
    const color =
      typeof ev.categoryColor === 'string' && _COLOR_RE.test(ev.categoryColor)
        ? ev.categoryColor
        : null
    result.push({
      id: NATIVE_ID_PREFIX + ev.id,
      title: ev.title,
      date,
      type: 'meeting',
      assignedTo: ev.ownerUserId,
      startAt: ev.startAt,
      endAt: ev.endAt,
      color,
      categoryName: ev.categoryName,
      clientName: ev.clientName,
      ownerName: ev.ownerName,
    })
  }
  return result
}

export type NativeViewKind = 'month' | 'week' | 'day' | 'agenda'

const _DATE_RE = /^(\d{4})-(\d{2})-(\d{2})$/

function parseCursorDateStr(s: string): { year: number; month: number; day: number; y: string; m: string; d: string } {
  const match = _DATE_RE.exec(s)
  if (!match) throw new RangeError(`malformed cursorDateStr: ${s}`)
  const year = parseInt(match[1]!, 10)
  const month = parseInt(match[2]!, 10)
  const day = parseInt(match[3]!, 10)
  if (month < 1 || month > 12 || day < 1 || day > 31) {
    throw new RangeError(`invalid date values in cursorDateStr: ${s}`)
  }
  return { year, month, day, y: match[1]!, m: match[2]!, d: match[3]! }
}

export function dateRangeForView(input: {
  view: NativeViewKind
  cursorDateStr: string
  agendaStartStr: string
  agendaEndStr: string
}): { startStr: string; endStr: string } {
  const { view, cursorDateStr, agendaStartStr, agendaEndStr } = input
  if (view === 'agenda') {
    return { startStr: agendaStartStr, endStr: agendaEndStr }
  }
  const { year, month, y, m } = parseCursorDateStr(cursorDateStr)
  if (view === 'month') {
    const startStr = `${y}-${m}-01`
    const lastDayNum = new Date(Date.UTC(year, month, 0)).getUTCDate()
    const endStr = `${y}-${m}-${String(lastDayNum).padStart(2, '0')}`
    return { startStr, endStr }
  }
  if (view === 'week') {
    const days = weekDates(cursorDateStr)
    return { startStr: days[0]!, endStr: days[6]! }
  }
  // day
  return { startStr: cursorDateStr, endStr: cursorDateStr }
}

export function rangeToInstants(
  startStr: string,
  endStr: string,
  timeZone: string
): { from: string; to: string } {
  if (endStr < startStr) {
    throw new RangeError(`endStr (${endStr}) is before startStr (${startStr})`)
  }
  const from = wallTimeToInstant(startStr, 0, timeZone).toISOString()
  const to = wallTimeToInstant(endStr, 1440, timeZone).toISOString()
  return { from, to }
}
