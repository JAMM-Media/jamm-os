// path: frontend/src/components/calendar/TimeGrid.tsx
'use client'

import { useMemo, useRef, useEffect } from 'react'
import {
  buildGridDays,
  blockBox,
  nowPosition,
  DEFAULT_FIRST_VISIBLE_MINUTES,
} from '@/lib/calendarGrid'
import {
  formatHourLabel,
  formatTimeLabel,
  zonedDateStr,
} from '@/lib/calendarTime'
import { readableTextColor } from '@/lib/calendarTextColor'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

export const HOUR_HEIGHT_PX = 48
export const GUTTER_WIDTH_PX = 56

const PX_PER_MINUTE = HOUR_HEIGHT_PX / 60
const GRID_HEIGHT_PX = HOUR_HEIGHT_PX * 24

const DAY_NAMES = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface TimeGridTimedEvent {
  id: string
  title: string
  startAt: string | Date
  endAt: string | Date
  color: string
}

export interface TimeGridAllDayItem {
  id: string
  date: string
  title: string
  color: string
}

export interface TimeGridProps {
  days: string[]
  timeZone: string
  timed: TimeGridTimedEvent[]
  allDay: TimeGridAllDayItem[]
  now: Date | null
  onItemClick?: (id: string, e: React.MouseEvent<HTMLElement>) => void
  initialScrollMinutes?: number
  className?: string
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function TimeGrid({
  days,
  timeZone,
  timed,
  allDay,
  now,
  onItemClick,
  initialScrollMinutes,
  className,
}: TimeGridProps) {
  const scrollRef = useRef<HTMLDivElement>(null)

  // Scroll once on mount to the initial position.
  // The page is responsible for passing stable arrays to avoid re-computation.
  useEffect(() => {
    if (scrollRef.current) {
      const scrollMin = initialScrollMinutes ?? DEFAULT_FIRST_VISIBLE_MINUTES
      scrollRef.current.scrollTop = scrollMin * PX_PER_MINUTE
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Compute the grid days from the given dates, timed events, and all day items.
  const gridDays = useMemo(
    () =>
      buildGridDays({
        dates: days,
        timed: timed.map(e => ({ id: e.id, startAt: e.startAt, endAt: e.endAt })),
        allDay: allDay.map(a => ({ id: a.id, date: a.date })),
        timeZone,
      }),
    [days, timed, allDay, timeZone]
  )

  // Lookup maps for rendering item details by id.
  const timedById = useMemo(() => {
    const m = new Map<string, TimeGridTimedEvent>()
    for (const e of timed) m.set(e.id, e)
    return m
  }, [timed])

  const allDayById = useMemo(() => {
    const m = new Map<string, TimeGridAllDayItem>()
    for (const a of allDay) m.set(a.id, a)
    return m
  }, [allDay])

  // Today's date string in the firm zone (null when now is not provided).
  const todayStr = now !== null ? zonedDateStr(now, timeZone) : null

  // Current time position: only when now falls on one of the displayed dates.
  const nowPos = now !== null ? nowPosition(now, timeZone) : null
  const nowDay =
    nowPos !== null && days.includes(nowPos.dateStr) ? nowPos.dateStr : null

  // Whether any visible day has all day items (controls strip visibility).
  const hasAllDay = gridDays.some(gd => gd.allDayIds.length > 0)

  return (
    <div
      className={`flex flex-col min-h-0 overflow-hidden${className ? ` ${className}` : ''}`}
    >
      {/* Header row */}
      <div className="flex flex-shrink-0 overflow-y-hidden border-b border-cal-border dark:border-dark-cal-border" data-grid-header="true" style={{ scrollbarGutter: 'stable' }}>
        <div style={{ width: GUTTER_WIDTH_PX, flexShrink: 0 }} />
        {days.map(dateStr => {
          const parts = dateStr.split('-')
          const y = parseInt(parts[0]!, 10)
          const mo = parseInt(parts[1]!, 10)
          const d = parseInt(parts[2]!, 10)
          // Derive weekday from UTC to avoid local timezone interference.
          const weekday = new Date(Date.UTC(y, mo - 1, d)).getUTCDay()
          const isToday = todayStr === dateStr
          return (
            <div
              key={dateStr}
              className="flex-1 flex flex-col items-center justify-center py-1"
              {...(isToday ? { 'data-today': 'true' } : {})}
            >
              <span className="text-[11px] text-muted-foreground uppercase tracking-wide">
                {DAY_NAMES[weekday]}
              </span>
              <span
                className={
                  isToday
                    ? 'mt-0.5 w-7 h-7 flex items-center justify-center rounded-full bg-primary text-primary-foreground text-base font-medium'
                    : 'mt-0.5 text-base font-medium text-brand dark:text-[#EDEEF0]'
                }
              >
                {d}
              </span>
            </div>
          )
        })}
      </div>

      {/* All day strip (only when at least one day in view has items) */}
      {hasAllDay && (
        <div className="flex flex-shrink-0 overflow-y-hidden border-b border-cal-border dark:border-dark-cal-border" data-grid-allday="true" style={{ scrollbarGutter: 'stable' }}>
          <div style={{ width: GUTTER_WIDTH_PX, flexShrink: 0 }} />
          {gridDays.map(gd => (
            <div
              key={gd.dateStr}
              className="flex-1 flex flex-col gap-0.5 p-0.5 max-h-24 overflow-y-auto"
            >
              {gd.allDayIds.map(aid => {
                const item = allDayById.get(aid)
                if (!item) return null
                return (
                  <button
                    key={`a-${aid}`}
                    type="button"
                    data-allday-id={aid}
                    className="truncate rounded-[3px] px-1 text-[11px] text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
                    style={{
                      backgroundColor: item.color,
                      color: readableTextColor(item.color),
                    }}
                    onClick={e => onItemClick?.(aid, e)}
                  >
                    {item.title}
                  </button>
                )
              })}
            </div>
          ))}
        </div>
      )}

      {/* Scrolling grid */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto min-h-0 bg-white" data-grid-scroll="true" style={{ scrollbarGutter: 'stable' }}>
        <div className="relative flex" style={{ height: GRID_HEIGHT_PX }}>
          {/* Gutter: hour labels at hours 1-23 */}
          <div
            className="relative flex-shrink-0"
            style={{ width: GUTTER_WIDTH_PX }}
          >
            {Array.from({ length: 23 }, (_, i) => {
              const hour = i + 1
              return (
                <div
                  key={`lbl-${hour}`}
                  className="absolute text-muted-foreground select-none pointer-events-none"
                  style={{
                    top: hour * HOUR_HEIGHT_PX - 8,
                    right: 4,
                    left: 0,
                    fontSize: 11,
                    textAlign: 'right',
                  }}
                >
                  {formatHourLabel(hour)}
                </div>
              )
            })}
          </div>

          {/* Day columns */}
          <div
            className="relative flex-1"
            style={{
              display: 'grid',
              gridTemplateColumns: `repeat(${days.length}, minmax(0, 1fr))`,
            }}
          >
            {gridDays.map(gd => (
              <div
                key={gd.dateStr}
                className="relative border-l border-gray-100 dark:border-dark-cal-border"
              >
                {/* Hour lines */}
                {Array.from({ length: 24 }, (_, hour) => (
                  <div
                    key={`hl-${hour}`}
                    className="absolute left-0 right-0 border-t border-gray-200 dark:border-dark-cal-border pointer-events-none"
                    style={{ top: hour * HOUR_HEIGHT_PX }}
                  />
                ))}

                {/* Current time line (today column only) */}
                {nowDay === gd.dateStr && nowPos !== null && (
                  <div
                    data-now-line="true"
                    className="absolute left-0 right-0 pointer-events-none"
                    style={{ top: nowPos.minutes * PX_PER_MINUTE }}
                  >
                    <div
                      className="absolute"
                      style={{
                        left: 0,
                        top: -3,
                        width: 8,
                        height: 8,
                        borderRadius: '50%',
                        backgroundColor: '#E24B4A',
                      }}
                    />
                    <div style={{ height: 2, backgroundColor: '#E24B4A' }} />
                  </div>
                )}

                {/* Timed blocks */}
                {gd.blocks.map(block => {
                  const item = timedById.get(block.id)
                  if (!item) return null
                  const box = blockBox(block, PX_PER_MINUTE)
                  const displayMin = block.displayEndMin - block.startMin
                  const showTimeLabel = displayMin >= 45

                  // Square corners when the block continues past the day boundary.
                  const trTopLeft = block.continuesBefore ? '0' : '4px'
                  const trTopRight = block.continuesBefore ? '0' : '4px'
                  const trBotRight = block.continuesAfter ? '0' : '4px'
                  const trBotLeft = block.continuesAfter ? '0' : '4px'
                  const borderRadius = `${trTopLeft} ${trTopRight} ${trBotRight} ${trBotLeft}`

                  const ariaLabel = `${item.title}, ${formatTimeLabel(item.startAt, timeZone)} to ${formatTimeLabel(item.endAt, timeZone)}`

                  return (
                    <button
                      key={`t-${block.id}`}
                      type="button"
                      aria-label={ariaLabel}
                      data-block-id={block.id}
                      data-lane={block.lane}
                      data-lane-count={block.laneCount}
                      data-start-min={block.startMin}
                      data-end-min={block.endMin}
                      data-continues-before={block.continuesBefore ? 'true' : 'false'}
                      data-continues-after={block.continuesAfter ? 'true' : 'false'}
                      className="absolute overflow-hidden focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand border border-white dark:border-[#1c1c1c]"
                      style={{
                        top: box.top,
                        height: box.height,
                        left: `calc(${box.leftPct}% + 1px)`,
                        width: `calc(${box.widthPct}% - 2px)`,
                        backgroundColor: item.color,
                        borderRadius,
                        color: readableTextColor(item.color),
                      }}
                      onClick={e => onItemClick?.(block.id, e)}
                    >
                      <div className="text-[12px] font-bold truncate px-1 pt-0.5 leading-tight">
                        {item.title}
                      </div>
                      {showTimeLabel && (
                        <div className="text-[11px] opacity-80 truncate px-1 leading-tight">
                          {formatTimeLabel(item.startAt, timeZone)}
                        </div>
                      )}
                    </button>
                  )
                })}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
