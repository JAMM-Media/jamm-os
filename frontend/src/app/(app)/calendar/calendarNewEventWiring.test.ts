// path: frontend/src/app/(app)/calendar/calendarNewEventWiring.test.ts
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

describe('calendarNewEvent wiring: source guards', () => {
  it('page imports NewEventModal', () => {
    const src = readSrc(PAGE)
    expect(src).toContain("import { NewEventModal } from '@/components/calendar/NewEventModal'")
  })

  it('New event button is gated on staff role', () => {
    const src = readSrc(PAGE)
    expect(src).toContain("user?.role === 'staff'")
  })

  it('New event button is gated on manager role', () => {
    const src = readSrc(PAGE)
    const staffIdx = src.indexOf("user?.role === 'staff'")
    expect(staffIdx).toBeGreaterThan(-1)
    // manager gate should appear near the staff gate (within 300 chars)
    const nearby = src.slice(staffIdx - 50, staffIdx + 300)
    expect(nearby).toContain("user?.role === 'manager'")
  })

  it('New event button is gated on firm_owner role', () => {
    const src = readSrc(PAGE)
    const staffIdx = src.indexOf("user?.role === 'staff'")
    expect(staffIdx).toBeGreaterThan(-1)
    const nearby = src.slice(staffIdx - 50, staffIdx + 300)
    expect(nearby).toContain("user?.role === 'firm_owner'")
  })

  it('New event button is gated on firmTzValid', () => {
    const src = readSrc(PAGE)
    const staffIdx = src.indexOf("user?.role === 'staff'")
    expect(staffIdx).toBeGreaterThan(-1)
    const nearby = src.slice(staffIdx - 50, staffIdx + 300)
    expect(nearby).toContain('firmTzValid')
  })

  it("modal onCreated invalidates ['native-calendar-events']", () => {
    const src = readSrc(PAGE)
    expect(src).toContain("queryKey: ['native-calendar-events']")
    const onCreatedIdx = src.indexOf('onCreated')
    expect(onCreatedIdx).toBeGreaterThan(-1)
    // invalidateQueries should appear within 200 chars of onCreated
    const block = src.slice(onCreatedIdx, onCreatedIdx + 300)
    expect(block).toContain("queryKey: ['native-calendar-events']")
  })

  it('page contains no new useMutation calls beyond the original two', () => {
    const src = readSrc(PAGE)
    const count = (src.match(/useMutation\(/g) ?? []).length
    expect(count).toBe(2)
  })
})
