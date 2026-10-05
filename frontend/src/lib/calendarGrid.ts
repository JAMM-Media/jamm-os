// path: frontend/src/lib/calendarGrid.ts
import {
  daySegment,
  layoutDay,
  wallTimeToInstant,
  zonedDateStr,
  minutesIntoDay,
} from './calendarTime'
import { startOfWeek, addDaysStr, localDateStr } from './utils'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

export const DEFAULT_FIRST_VISIBLE_MINUTES = 420

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type GridTimedInput = { id: string; startAt: string | Date; endAt: string | Date }
export type GridAllDayInput = { id: string; date: string }

export type GridBlock = {
  id: string
  startMin: number
  endMin: number
  displayEndMin: number
  lane: number
  laneCount: number
  continuesBefore: boolean
  continuesAfter: boolean
}

export type GridDay = {
  dateStr: string
  blocks: GridBlock[]
  allDayIds: string[]
}

// ---------------------------------------------------------------------------
// weekDates
// ---------------------------------------------------------------------------

export function weekDates(anchorDateStr: string): string[] {
  // Parse the anchor string to a local Date so startOfWeek can find the Sunday.
  const parts = anchorDateStr.split('-')
  const anchor = new Date(
    parseInt(parts[0]!, 10),
    parseInt(parts[1]!, 10) - 1,
    parseInt(parts[2]!, 10)
  )
  const sun = startOfWeek(anchor)
  const sunStr = localDateStr(sun)
  return Array.from({ length: 7 }, (_, i) => addDaysStr(sunStr, i))
}

// ---------------------------------------------------------------------------
// buildGridDays
// ---------------------------------------------------------------------------

export function buildGridDays(params: {
  dates: string[]
  timed: GridTimedInput[]
  allDay: GridAllDayInput[]
  timeZone: string
}): GridDay[] {
  const { dates, timed, allDay, timeZone } = params

  return dates.map(dateStr => {
    const dayStart = wallTimeToInstant(dateStr, 0, timeZone)
    const dayEnd = wallTimeToInstant(dateStr, 1440, timeZone)
    const dayStartMs = dayStart.getTime()
    const dayEndMs = dayEnd.getTime()

    // Build segment list for this date. Errors (naive string, bad zone) propagate.
    const segments: Array<{ id: string; startMin: number; endMin: number }> = []
    const inputByDay: Map<string, GridTimedInput> = new Map()

    for (const item of timed) {
      const seg = daySegment(item.startAt, item.endAt, dateStr, timeZone)
      if (seg === null) continue
      segments.push({ id: item.id, startMin: seg.startMin, endMin: seg.endMin })
      inputByDay.set(item.id, item)
    }

    // layoutDay throws on duplicate ids within this date.
    const laid = layoutDay(segments)

    const blocks: GridBlock[] = laid.map(item => {
      const orig = inputByDay.get(item.id)!
      const startMs =
        orig.startAt instanceof Date
          ? orig.startAt.getTime()
          : new Date(orig.startAt).getTime()
      const endMs =
        orig.endAt instanceof Date
          ? orig.endAt.getTime()
          : new Date(orig.endAt as string).getTime()

      return {
        id: item.id,
        startMin: item.startMin,
        endMin: item.endMin,
        displayEndMin: item.displayEndMin,
        lane: item.lane,
        laneCount: item.laneCount,
        continuesBefore: startMs < dayStartMs,
        continuesAfter: endMs > dayEndMs,
      }
    })

    const allDayIds = allDay
      .filter(ad => ad.date === dateStr)
      .map(ad => ad.id)
      .sort()

    return { dateStr, blocks, allDayIds }
  })
}

// ---------------------------------------------------------------------------
// nowPosition
// ---------------------------------------------------------------------------

export function nowPosition(
  now: Date,
  timeZone: string
): { dateStr: string; minutes: number } {
  return {
    dateStr: zonedDateStr(now, timeZone),
    minutes: minutesIntoDay(now, timeZone),
  }
}

// ---------------------------------------------------------------------------
// blockBox
// ---------------------------------------------------------------------------

export function blockBox(
  block: Pick<GridBlock, 'startMin' | 'displayEndMin' | 'lane' | 'laneCount'>,
  pxPerMinute: number
): { top: number; height: number; leftPct: number; widthPct: number } {
  return {
    top: block.startMin * pxPerMinute,
    height: (block.displayEndMin - block.startMin) * pxPerMinute,
    leftPct: (block.lane / block.laneCount) * 100,
    widthPct: 100 / block.laneCount,
  }
}
