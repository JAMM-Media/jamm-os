// path: frontend/src/app/(app)/calendar/calendarCleanupWiring.test.ts
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

describe('calendar cleanup wiring: source guards', () => {
  it('native events query key contains the current user id', () => {
    const src = readSrc(PAGE)
    const keyIdx = src.indexOf("queryKey: ['native-calendar-events',")
    expect(keyIdx).toBeGreaterThan(-1)
    const keyLine = src.slice(keyIdx, src.indexOf('\n', keyIdx))
    expect(keyLine).toContain("user?.id ?? ''")
  })

  it('EventDetailsPopover is not rendered when firmTzValid is false', () => {
    const src = readSrc(PAGE)
    const gateIdx = src.indexOf('{clickedNativeEvent && (firmTzValid && firmTz) && (')
    expect(gateIdx).toBeGreaterThan(-1)
    const popIdx = src.indexOf('<EventDetailsPopover')
    expect(popIdx).toBeGreaterThan(gateIdx)
    const block = src.slice(gateIdx, src.indexOf('/>', popIdx) + 2)
    expect(block).toContain('timeZone={firmTz}')
    expect(block).not.toContain("firmTz ?? ''")
  })

  it("invalidateQueries still uses ['native-calendar-events'] in the page", () => {
    const src = readSrc(PAGE)
    const count = (src.match(/invalidateQueries\(\{ queryKey: \['native-calendar-events'\] \}\)/g) ?? []).length
    expect(count).toBe(2)
  })

  it('useMutation count in page.tsx is unchanged at 2', () => {
    const src = readSrc(PAGE)
    const count = (src.match(/useMutation\(/g) ?? []).length
    expect(count).toBe(2)
  })
})
