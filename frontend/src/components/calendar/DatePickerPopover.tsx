// path: frontend/src/components/calendar/DatePickerPopover.tsx
'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import {
  buildMonthGrid,
  shiftMonth,
  monthTitle,
  addDaysUTC,
  WEEKDAY_LABELS,
} from '@/lib/calendarMonthGrid'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const WEEKDAY_FULL = [
  'Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday',
]

const MONTH_NAMES_FULL = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
]

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function parseUTCParts(dateStr: string): { year: number; month: number; day: number } {
  const parts = dateStr.split('-')
  return {
    year: parseInt(parts[0]!, 10),
    month: parseInt(parts[1]!, 10),
    day: parseInt(parts[2]!, 10),
  }
}

function dayAriaLabel(dateStr: string): string {
  const { year, month, day } = parseUTCParts(dateStr)
  const dow = new Date(Date.UTC(year, month - 1, day)).getUTCDay()
  return `${WEEKDAY_FULL[dow]}, ${MONTH_NAMES_FULL[month - 1]} ${day}, ${year}`
}

function clampDayToMonth(year: number, month: number, day: number): number {
  const lastDay = new Date(Date.UTC(year, month, 0)).getUTCDate()
  return Math.min(day, lastDay)
}

function toDateStr(year: number, month: number, day: number): string {
  return (
    `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
  )
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface DatePickerPopoverProps {
  valueDateStr: string
  todayDateStr: string
  onPick: (dateStr: string) => void
  onClose: () => void
  className?: string
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DatePickerPopover({
  valueDateStr,
  todayDateStr,
  onPick,
  onClose,
  className = '',
}: DatePickerPopoverProps) {
  const { year: initYear, month: initMonth } = parseUTCParts(valueDateStr)
  const [viewYear, setViewYear] = useState(initYear)
  const [viewMonth, setViewMonth] = useState(initMonth)
  const [focusedStr, setFocusedStr] = useState(valueDateStr)
  const containerRef = useRef<HTMLDivElement>(null)
  const shouldFocusRef = useRef(true)

  // keyboard navigation requests focus; month-button clicks do not.
  const navigate = useCallback((newFocused: string) => {
    shouldFocusRef.current = true
    const { year, month } = parseUTCParts(newFocused)
    setFocusedStr(newFocused)
    setViewYear(year)
    setViewMonth(month)
  }, [])

  // Move DOM focus to the focused day only when navigation requests it.
  useEffect(() => {
    if (!shouldFocusRef.current) return
    shouldFocusRef.current = false
    const el = containerRef.current?.querySelector<HTMLButtonElement>(
      `[data-date="${focusedStr}"]`,
    )
    el?.focus()
  }, [focusedStr, viewYear, viewMonth])

  function handleKeyDown(e: React.KeyboardEvent) {
    // Day-navigation keys only act when focus is on a day button.
    // Escape works from anywhere inside the popover.
    const dayButton = (e.target as HTMLElement).closest<HTMLElement>('[data-date]')
    if (e.key !== 'Escape' && !dayButton) return

    const base = dayButton?.getAttribute('data-date') ?? focusedStr
    const { year, month, day } = parseUTCParts(base)
    let next = base

    switch (e.key) {
      case 'ArrowLeft':
        e.preventDefault()
        next = addDaysUTC(base, -1)
        break
      case 'ArrowRight':
        e.preventDefault()
        next = addDaysUTC(base, 1)
        break
      case 'ArrowUp':
        e.preventDefault()
        next = addDaysUTC(base, -7)
        break
      case 'ArrowDown':
        e.preventDefault()
        next = addDaysUTC(base, 7)
        break
      case 'PageUp': {
        e.preventDefault()
        const { year: ny, month: nm } = shiftMonth(year, month, -1)
        next = toDateStr(ny, nm, clampDayToMonth(ny, nm, day))
        break
      }
      case 'PageDown': {
        e.preventDefault()
        const { year: ny, month: nm } = shiftMonth(year, month, 1)
        next = toDateStr(ny, nm, clampDayToMonth(ny, nm, day))
        break
      }
      case 'Home': {
        e.preventDefault()
        const dow = new Date(Date.UTC(year, month - 1, day)).getUTCDay()
        next = addDaysUTC(base, -dow)
        break
      }
      case 'End': {
        e.preventDefault()
        const dow = new Date(Date.UTC(year, month - 1, day)).getUTCDay()
        next = addDaysUTC(base, 6 - dow)
        break
      }
      case 'Enter':
      case ' ':
        e.preventDefault()
        onPick(base)
        return
      case 'Escape':
        e.preventDefault()
        onClose()
        return
      default:
        return
    }

    if (next !== base) navigate(next)
  }

  function handlePrevMonth(e: React.MouseEvent<HTMLButtonElement>) {
    const { year, month } = shiftMonth(viewYear, viewMonth, -1)
    setViewYear(year)
    setViewMonth(month)
    e.currentTarget.focus()
  }

  function handleNextMonth(e: React.MouseEvent<HTMLButtonElement>) {
    const { year, month } = shiftMonth(viewYear, viewMonth, 1)
    setViewYear(year)
    setViewMonth(month)
    e.currentTarget.focus()
  }

  const grid = buildMonthGrid(viewYear, viewMonth)
  const _gridCells = grid.flat()
  const _focusedInGrid = _gridCells.some((c) => c.dateStr === focusedStr)
  const tabFocusStr = _focusedInGrid
    ? focusedStr
    : (_gridCells.find((c) => c.inMonth)?.dateStr ?? focusedStr)

  return (
    <div
      ref={containerRef}
      role="dialog"
      aria-label="Choose a date"
      className={`bg-surface-card dark:bg-dark-card border border-cal-border dark:border-dark-cal-border rounded-[10px] shadow-lg p-3 w-[264px] ${className}`}
      onKeyDown={handleKeyDown}
    >
      {/* Month navigation header */}
      <div className="flex items-center justify-between mb-2">
        <button
          aria-label="Previous month"
          onClick={handlePrevMonth}
          className="flex items-center justify-center w-7 h-7 rounded text-[#6B7280] dark:text-[#9CA3AF] hover:bg-surface-border/20 dark:hover:bg-dark-border/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
        >
          <ChevronLeft size={14} />
        </button>
        <span className="text-[13px] font-semibold text-brand dark:text-[#EDEEF0]">
          {monthTitle(viewYear, viewMonth)}
        </span>
        <button
          aria-label="Next month"
          onClick={handleNextMonth}
          className="flex items-center justify-center w-7 h-7 rounded text-[#6B7280] dark:text-[#9CA3AF] hover:bg-surface-border/20 dark:hover:bg-dark-border/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
        >
          <ChevronRight size={14} />
        </button>
      </div>

      {/* Weekday labels */}
      <div className="grid grid-cols-7 mb-1">
        {WEEKDAY_LABELS.map((lbl) => (
          <div
            key={lbl}
            className="text-center text-[10px] font-medium text-[#9CA3AF] py-0.5"
          >
            {lbl}
          </div>
        ))}
      </div>

      {/* Day grid */}
      <div className="grid grid-cols-7">
        {grid.flat().map((cell) => {
          const isSelected = cell.dateStr === valueDateStr
          const isToday = cell.dateStr === todayDateStr
          const isFocused = cell.dateStr === focusedStr

          let dayClass =
            'flex items-center justify-center w-8 h-8 text-[12px] rounded transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand '

          if (isSelected) {
            dayClass += 'bg-brand text-white font-semibold'
          } else if (isToday) {
            dayClass += 'ring-1 ring-brand font-medium text-brand dark:text-[#EDEEF0]'
          } else if (cell.inMonth) {
            dayClass +=
              'text-brand dark:text-[#EDEEF0] hover:bg-surface-border/20 dark:hover:bg-dark-border/20'
          } else {
            dayClass +=
              'text-[#9CA3AF] hover:bg-surface-border/20 dark:hover:bg-dark-border/20'
          }

          return (
            <button
              key={cell.dateStr}
              data-date={cell.dateStr}
              aria-label={dayAriaLabel(cell.dateStr)}
              tabIndex={cell.dateStr === tabFocusStr ? 0 : -1}
              onClick={() => onPick(cell.dateStr)}
              className={dayClass}
            >
              {cell.day}
            </button>
          )
        })}
      </div>
    </div>
  )
}
