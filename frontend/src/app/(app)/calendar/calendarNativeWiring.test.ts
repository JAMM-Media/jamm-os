// frontend/src/app/(app)/calendar/calendarNativeWiring.test.ts
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

describe('calendarNative wiring: source guards', () => {
  it("page import line contains mapNativeEvents", () => {
    const src = readSrc(PAGE)
    // Must appear in an import statement, not just a usage
    expect(src).toContain("import { mapNativeEvents")
  })

  it("page import line contains dateRangeForView", () => {
    const src = readSrc(PAGE)
    expect(src).toContain("import { mapNativeEvents, dateRangeForView")
  })

  it("query key contains 'native-calendar-events'", () => {
    const src = readSrc(PAGE)
    expect(src).toContain("'native-calendar-events'")
  })

  it('query key contains the firm time zone variable (firmTz)', () => {
    const src = readSrc(PAGE)
    const queryKeyIdx = src.indexOf("'native-calendar-events'")
    expect(queryKeyIdx).toBeGreaterThan(-1)
    const lineEnd = src.indexOf('\n', queryKeyIdx)
    const keyLine = src.slice(queryKeyIdx, lineEnd)
    expect(keyLine).toContain("firmTz ?? ''")
  })

  it('native query is gated on isValidTimeZone via firmTzValid', () => {
    const src = readSrc(PAGE)
    const queryStart = src.indexOf("'native-calendar-events'")
    expect(queryStart).toBeGreaterThan(-1)
    const queryBlock = src.slice(queryStart, queryStart + 400)
    expect(queryBlock).toContain('firmTzValid')
    expect(queryBlock).toContain('enabled:')
  })
})
