// frontend/src/components/ui/TimeTextInput.tsx
'use client'

import { useState, useEffect, KeyboardEvent } from 'react'
import { cn } from '@/lib/utils'

// Parse a freely-typed time string into "HH:mm" (24-hour). Returns null if
// the input is not recognizable as a real time.
function parseTimeText(raw: string): string | null {
  const s = raw.trim()
  if (!s) return null

  const lower = s.toLowerCase()

  const hasAm = lower.endsWith('am') || / am$/.test(lower)
  const hasPm = lower.endsWith('pm') || / pm$/.test(lower)

  // Strip AM/PM suffix and surrounding whitespace
  const timePart = lower.replace(/\s*(am|pm)$/, '').trim()

  let h: number
  let m: number

  if (timePart.includes(':')) {
    const parts = timePart.split(':')
    if (parts.length !== 2) return null
    h = parseInt(parts[0], 10)
    m = parseInt(parts[1], 10)
  } else if (/^\d{4}$/.test(timePart)) {
    // "1500" -> h=15, m=0
    h = parseInt(timePart.slice(0, 2), 10)
    m = parseInt(timePart.slice(2), 10)
  } else if (/^\d{3}$/.test(timePart)) {
    // "900" -> h=9, m=0
    h = parseInt(timePart.slice(0, 1), 10)
    m = parseInt(timePart.slice(1), 10)
  } else if (/^\d{1,2}$/.test(timePart)) {
    // Bare hour: "9", "10"
    h = parseInt(timePart, 10)
    m = 0
  } else {
    return null
  }

  if (isNaN(h) || isNaN(m) || m < 0 || m > 59 || h < 0) return null

  if (hasAm) {
    if (h === 12) h = 0
    if (h > 12) return null
  } else if (hasPm) {
    if (h !== 12) h += 12
    if (h > 23) return null
  } else {
    // No AM/PM: accept 0-23 as-is (24-hour or unambiguous single digit)
    if (h > 23) return null
  }

  if (h > 23) return null

  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
}

// Format "HH:mm" as a human-readable display string like "3:00 PM".
function formatDisplayTime(hhmm: string): string {
  const [h, m] = hhmm.split(':').map(Number)
  const ampm = h < 12 ? 'AM' : 'PM'
  const displayH = h % 12 === 0 ? 12 : h % 12
  return `${displayH}:${String(m).padStart(2, '0')} ${ampm}`
}

interface TimeTextInputProps {
  value: string
  onChange: (hhmm: string) => void
  className?: string
  placeholder?: string
}

export function TimeTextInput({ value, onChange, className, placeholder = 'e.g. 3pm' }: TimeTextInputProps) {
  const [displayText, setDisplayText] = useState(() =>
    value ? formatDisplayTime(value) : ''
  )
  const [error, setError] = useState('')

  // Sync display when value is cleared externally (e.g. form reset)
  useEffect(() => {
    if (!value) {
      setDisplayText('')
      setError('')
    }
  }, [value])

  function commit(raw: string) {
    const parsed = parseTimeText(raw)
    if (!raw.trim()) {
      setError('')
      return
    }
    if (parsed === null) {
      setError('Enter a valid time like "3pm" or "15:30"')
    } else {
      setError('')
      setDisplayText(formatDisplayTime(parsed))
      onChange(parsed)
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') {
      e.preventDefault()
      commit(displayText)
    }
  }

  return (
    <div className="flex flex-col gap-0.5">
      <input
        type="text"
        value={displayText}
        onChange={(e) => { setDisplayText(e.target.value); setError('') }}
        onBlur={() => commit(displayText)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        className={cn(
          className,
          error && 'ring-1 ring-red-500 border-red-400'
        )}
      />
      {error && (
        <span className="text-[11px] text-red-500">{error}</span>
      )}
    </div>
  )
}
