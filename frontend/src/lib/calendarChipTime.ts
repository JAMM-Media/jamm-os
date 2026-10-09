// path: frontend/src/lib/calendarChipTime.ts

import { hasOffset, isValidTimeZone } from './calendarGridData'
import { minutesIntoDay } from './calendarTime'

export function formatChipTime(
  startAt: string | null | undefined,
  timeZone: string | null | undefined
): string | null {
  if (!startAt || !hasOffset(startAt)) return null
  if (!timeZone || !isValidTimeZone(timeZone)) return null
  const mins = minutesIntoDay(startAt, timeZone)
  const h = Math.floor(mins / 60)
  const m = mins % 60
  const h12 = h % 12 === 0 ? 12 : h % 12
  const suffix = h < 12 ? 'a' : 'p'
  return `${h12}:${String(m).padStart(2, '0')}${suffix}`
}

export function sortDayEvents<T extends { startAt?: string | null; endAt?: string | null }>(
  events: T[],
  timeZone: string | null | undefined
): T[] {
  const validTz = !!(timeZone && isValidTimeZone(timeZone))
  const isTimed = (ev: T): boolean => {
    if (!validTz) return false
    return (
      typeof ev.startAt === 'string' &&
      hasOffset(ev.startAt) &&
      typeof ev.endAt === 'string' &&
      hasOffset(ev.endAt) &&
      Date.parse(ev.endAt) > Date.parse(ev.startAt)
    )
  }
  const untimed: Array<{ ev: T; idx: number }> = []
  const timed: Array<{ ev: T; idx: number; instant: number }> = []
  events.forEach((ev, idx) => {
    if (isTimed(ev)) {
      timed.push({ ev, idx, instant: Date.parse(ev.startAt!) })
    } else {
      untimed.push({ ev, idx })
    }
  })
  timed.sort((a, b) => a.instant !== b.instant ? a.instant - b.instant : a.idx - b.idx)
  return [...untimed.map(x => x.ev), ...timed.map(x => x.ev)]
}
