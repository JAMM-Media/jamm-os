// path: frontend/src/app/(app)/calendar/calendarMonthCellClick.test.ts
import { describe, it, expect } from 'vitest'
import { readFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'

const cwd = process.cwd()
if (!existsSync(join(cwd, 'package.json'))) {
  throw new Error(`vitest must run from the frontend folder; cwd is ${cwd}`)
}

function readSrc(relPath: string): string {
  return readFileSync(join(cwd, 'src', relPath), 'utf8').replace(/\r\n/g, '\n')
}

const PAGE = 'app/(app)/calendar/page.tsx'

describe('calendarMonthCellClick wiring: source guards', () => {
  it('Month cell onClick calls setView with day', () => {
    const src = readSrc(PAGE)
    expect(src).toContain("setView('day')")
    // The call must appear in the cell's onClick handler, not only elsewhere
    const cellHandler = src.match(/onClick=\{.*parsePickedDate\(ds\).*setView\('day'\).*\}/)
    expect(cellHandler).not.toBeNull()
  })

  it('Month cell onClick uses parsePickedDate to build the cursor date', () => {
    const src = readSrc(PAGE)
    expect(src).toContain('parsePickedDate(ds)')
    // Confirm it appears inside the cell onClick (alongside setView)
    expect(src).toContain("const d = parsePickedDate(ds); if (!d) return")
  })

  it('chip click path calls stopPropagation via handleEventClick', () => {
    // handleEventClick is the shared handler used by EventPill onClick in renderPills.
    // It must call e.stopPropagation() so chip clicks do not reach the cell handler.
    const src = readSrc(PAGE)
    // The function definition must contain stopPropagation on its first statement
    const fnIdx = src.indexOf('function handleEventClick(')
    expect(fnIdx).toBeGreaterThan(-1)
    const fnSlice = src.slice(fnIdx, fnIdx + 200)
    expect(fnSlice).toContain('e.stopPropagation()')
  })

  it('+1 more button onClick calls stopPropagation before toggling expandedDay', () => {
    const src = readSrc(PAGE)
    // The "+1 more" button must stop propagation so the click does not
    // bubble to the cell and navigate to Day view.
    expect(src).toContain('e.stopPropagation(); setExpandedDay(isExpanded ? null : ds)')
  })

  it('expanded day popover div has stopPropagation to block cell navigation', () => {
    const src = readSrc(PAGE)
    // line before the popover div
    expect(src).toContain('{isExpanded && dayEvents.length > 3 && (')
    expect(src).toContain('<div className="absolute top-0 left-0 z-40 bg-surface-card border border-surface-border rounded shadow-lg p-2 w-56" onClick={(e) => e.stopPropagation()}>')
    // line after the popover div
    expect(src).toContain('<div className="flex justify-between items-center mb-1">')
  })
})
