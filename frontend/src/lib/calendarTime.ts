// path: frontend/src/lib/calendarTime.ts

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

export const MINUTES_PER_DAY = 1440
export const SNAP_MINUTES = 15
export const MIN_DISPLAY_MINUTES = 30

// ---------------------------------------------------------------------------
// InstantInput
// ---------------------------------------------------------------------------

export type InstantInput = Date | string

function toDate(input: InstantInput): Date {
  if (input instanceof Date) return input
  if (!/Z$/.test(input) && !/[+-]\d{2}:\d{2}$/.test(input)) {
    throw new Error(`Instant must include a timezone offset. Got: ${input}`)
  }
  return new Date(input)
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function getParts(epochMs: number, timeZone: string) {
  const fmt = new Intl.DateTimeFormat('en-US', {
    hourCycle: 'h23',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    timeZone,
  })
  const parts = fmt.formatToParts(new Date(epochMs))
  const get = (t: string) => parts.find(p => p.type === t)!.value
  return {
    year: parseInt(get('year'), 10),
    month: parseInt(get('month'), 10),
    day: parseInt(get('day'), 10),
    hour: parseInt(get('hour'), 10),
    minute: parseInt(get('minute'), 10),
    second: parseInt(get('second'), 10),
  }
}

// Returns zone offset in ms: positive means the zone is ahead of UTC.
function getZoneOffsetMs(epochMs: number, timeZone: string): number {
  const p = getParts(epochMs, timeZone)
  return Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute, p.second) - epochMs
}

function parseYMD(dateStr: string): [number, number, number] {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(dateStr)
  if (!m) throw new RangeError(`malformed dateStr: ${dateStr}`)
  const year = parseInt(m[1], 10)
  const month = parseInt(m[2], 10)
  const day = parseInt(m[3], 10)
  if (month < 1 || month > 12 || day < 1 || day > 31) {
    throw new RangeError(`invalid date values in dateStr: ${dateStr}`)
  }
  return [year, month, day]
}

// ---------------------------------------------------------------------------
// zonedDateStr
// ---------------------------------------------------------------------------

export function zonedDateStr(instant: InstantInput, timeZone: string): string {
  const d = toDate(instant)
  const p = getParts(d.getTime(), timeZone)
  return `${p.year}-${String(p.month).padStart(2, '0')}-${String(p.day).padStart(2, '0')}`
}

// ---------------------------------------------------------------------------
// minutesIntoDay
// ---------------------------------------------------------------------------

export function minutesIntoDay(instant: InstantInput, timeZone: string): number {
  const d = toDate(instant)
  const fmt = new Intl.DateTimeFormat('en-US', {
    hourCycle: 'h23',
    hour: 'numeric',
    minute: 'numeric',
    timeZone,
  })
  const parts = fmt.formatToParts(d)
  // h23: midnight returns hour=0 (not 24)
  const hour = parseInt(parts.find(p => p.type === 'hour')!.value, 10)
  const minute = parseInt(parts.find(p => p.type === 'minute')!.value, 10)
  return hour * 60 + minute
}

// ---------------------------------------------------------------------------
// wallTimeToInstant
// ---------------------------------------------------------------------------

export function wallTimeToInstant(dateStr: string, minutes: number, timeZone: string): Date {
  if (!Number.isInteger(minutes) || minutes < 0 || minutes > 1440) {
    throw new RangeError(`minutes must be 0 to 1440, got: ${minutes}`)
  }

  const [year, month, day] = parseYMD(dateStr)
  const utcBase = Date.UTC(year, month - 1, day)

  if (minutes === 1440) {
    const next = new Date(utcBase + 86400000)
    const ny = next.getUTCFullYear()
    const nm = next.getUTCMonth() + 1
    const nd = next.getUTCDate()
    const nextStr = `${ny}-${String(nm).padStart(2, '0')}-${String(nd).padStart(2, '0')}`
    return wallTimeToInstant(nextStr, 0, timeZone)
  }

  // Iterative convergence: start with noon offset, then refine.
  // If the offset oscillates the time is in a DST gap; return the later candidate
  // (compatible forward resolution).
  const noonOffset = getZoneOffsetMs(Date.UTC(year, month - 1, day, 12), timeZone)
  let offsetMs = noonOffset
  const seen = new Set<number>()
  let candidateMs = 0

  for (let i = 0; i < 5; i++) {
    candidateMs = utcBase - offsetMs + minutes * 60000
    if (seen.has(candidateMs)) {
      // Oscillation: gap time. Return the later candidate (forward resolution).
      let max = candidateMs
      seen.forEach(v => { if (v > max) max = v })
      return new Date(max)
    }
    seen.add(candidateMs)
    const next = getZoneOffsetMs(candidateMs, timeZone)
    if (next === offsetMs) break
    offsetMs = next
  }

  // Verify result
  const gotDate = zonedDateStr(new Date(candidateMs), timeZone)
  const gotMin = minutesIntoDay(new Date(candidateMs), timeZone)

  if (gotDate === dateStr && gotMin === minutes) {
    // Check for DST fall-back ambiguity: is there a 1h-earlier instant with the same wall time?
    const earlier = new Date(candidateMs - 3600000)
    if (
      zonedDateStr(earlier, timeZone) === dateStr &&
      minutesIntoDay(earlier, timeZone) === minutes
    ) {
      return earlier
    }
    return new Date(candidateMs)
  }

  throw new RangeError(
    `wallTimeToInstant: could not resolve "${dateStr}" minute ${minutes} in ${timeZone}`
  )
}

// ---------------------------------------------------------------------------
// snapMinutes
// ---------------------------------------------------------------------------

export function snapMinutes(
  minutes: number,
  mode: 'round' | 'floor' | 'ceil' = 'round',
  step: number = SNAP_MINUTES
): number {
  if (mode === 'floor') return Math.floor(minutes / step) * step
  if (mode === 'ceil') return Math.ceil(minutes / step) * step
  return Math.round(minutes / step) * step
}

// ---------------------------------------------------------------------------
// daySegment
// ---------------------------------------------------------------------------

export function daySegment(
  start: InstantInput,
  end: InstantInput,
  dateStr: string,
  timeZone: string
): { startMin: number; endMin: number } | null {
  const startD = toDate(start)
  const endD = toDate(end)

  if (endD.getTime() <= startD.getTime()) return null

  const dayStartMs = wallTimeToInstant(dateStr, 0, timeZone).getTime()
  const dayEndMs = wallTimeToInstant(dateStr, 1440, timeZone).getTime()

  // No overlap: event ends at or before day start, or starts at or after day end
  if (endD.getTime() <= dayStartMs || startD.getTime() >= dayEndMs) return null

  const startMin = startD.getTime() <= dayStartMs
    ? 0
    : minutesIntoDay(startD, timeZone)

  const endMin = endD.getTime() >= dayEndMs
    ? 1440
    : minutesIntoDay(endD, timeZone)

  return { startMin, endMin }
}

// ---------------------------------------------------------------------------
// layoutDay
// ---------------------------------------------------------------------------

export type LayoutInput = { id: string; startMin: number; endMin: number }
export type LayoutItem = {
  id: string
  startMin: number
  endMin: number
  displayEndMin: number
  lane: number
  laneCount: number
}

export function layoutDay(items: LayoutInput[]): LayoutItem[] {
  if (items.length === 0) return []

  // Reject duplicate ids: union-find merges by id and would silently give wrong results
  const seenIds = new Set<string>()
  for (const item of items) {
    if (seenIds.has(item.id)) throw new Error(`layoutDay: duplicate item id "${item.id}"`)
    seenIds.add(item.id)
  }

  // Compute displayEndMin without mutating input
  const processed = items.map(item => ({
    id: item.id,
    startMin: item.startMin,
    endMin: item.endMin,
    displayEndMin: Math.min(MINUTES_PER_DAY, Math.max(item.endMin, item.startMin + MIN_DISPLAY_MINUTES)),
  }))

  // Sort: startMin ASC, displayEndMin DESC (longer first), id ASC
  processed.sort((a, b) => {
    if (a.startMin !== b.startMin) return a.startMin - b.startMin
    if (b.displayEndMin !== a.displayEndMin) return b.displayEndMin - a.displayEndMin
    return a.id < b.id ? -1 : 1
  })

  // Assign lanes: lowest lane not used by any earlier item that still overlaps
  // Two items overlap when a.startMin < b.displayEndMin AND b.startMin < a.displayEndMin
  const laneAssigned: Array<{ id: string; startMin: number; displayEndMin: number; lane: number }> = []

  for (const item of processed) {
    const overlapping = laneAssigned.filter(
      a => a.startMin < item.displayEndMin && item.startMin < a.displayEndMin
    )
    const usedLanes = new Set(overlapping.map(a => a.lane))
    let lane = 0
    while (usedLanes.has(lane)) lane++
    laneAssigned.push({ id: item.id, startMin: item.startMin, displayEndMin: item.displayEndMin, lane })
  }

  // Compute clusters using union-find for laneCount
  const parent: Record<string, string> = {}
  function find(x: string): string {
    if (parent[x] !== x) parent[x] = find(parent[x]!)
    return parent[x]!
  }
  function union(x: string, y: string) { parent[find(x)] = find(y) }

  for (const item of processed) parent[item.id] = item.id
  for (let i = 0; i < processed.length; i++) {
    for (let j = i + 1; j < processed.length; j++) {
      const a = processed[i]!
      const b = processed[j]!
      if (a.startMin < b.displayEndMin && b.startMin < a.displayEndMin) {
        union(a.id, b.id)
      }
    }
  }

  // Max lane per cluster root
  const clusterMaxLane: Record<string, number> = {}
  for (const item of laneAssigned) {
    const root = find(item.id)
    if (clusterMaxLane[root] === undefined || item.lane > clusterMaxLane[root]) {
      clusterMaxLane[root] = item.lane
    }
  }

  // Build result in sorted order
  return processed.map(item => {
    const la = laneAssigned.find(a => a.id === item.id)!
    return {
      id: item.id,
      startMin: item.startMin,
      endMin: item.endMin,
      displayEndMin: item.displayEndMin,
      lane: la.lane,
      laneCount: clusterMaxLane[find(item.id)]! + 1,
    }
  })
}

// ---------------------------------------------------------------------------
// normalizeSpaces
// ---------------------------------------------------------------------------

export function normalizeSpaces(s: string): string {
  return s.replace(/[\u202f\u00a0]/g, ' ')
}

// ---------------------------------------------------------------------------
// formatTimeLabel
// ---------------------------------------------------------------------------

export function formatTimeLabel(instant: InstantInput, timeZone: string): string {
  const d = toDate(instant)
  const raw = new Intl.DateTimeFormat('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
    timeZone,
  }).format(d)
  return normalizeSpaces(raw)
}

// ---------------------------------------------------------------------------
// formatHourLabel
// ---------------------------------------------------------------------------

export function formatHourLabel(hour: number): string {
  if (hour === 0) return '12 AM'
  if (hour === 12) return '12 PM'
  if (hour < 12) return `${hour} AM`
  return `${hour - 12} PM`
}