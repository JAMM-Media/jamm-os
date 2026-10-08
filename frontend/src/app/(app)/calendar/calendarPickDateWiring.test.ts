// frontend/src/app/(app)/calendar/calendarPickDateWiring.test.ts
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

describe('calendarPickDate wiring: source guards', () => {
  it('page imports parsePickedDate', () => {
    const src = readSrc(PAGE)
    expect(src).toContain("import { parsePickedDate } from '@/lib/calendarPickDate'")
  })

  it('page imports DatePickerPopover from the component path', () => {
    const src = readSrc(PAGE)
    expect(src).toContain("import { DatePickerPopover } from '@/components/calendar/DatePickerPopover'")
  })

  it('page does NOT contain a native type="date" input any more', () => {
    const src = readSrc(PAGE)
    expect(src).not.toContain('type="date"')
  })

  it('page contains aria-label "Pick a date"', () => {
    const src = readSrc(PAGE)
    expect(src).toContain('aria-label="Pick a date"')
  })
})
