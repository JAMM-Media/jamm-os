// path: frontend/src/app/(app)/calendar/calendarEventDetailsWiring.test.ts
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

describe('calendarEventDetails wiring: source guards', () => {
  it('page imports EventDetailsPopover', () => {
    const src = readSrc(PAGE)
    expect(src).toContain("import { EventDetailsPopover } from '@/components/calendar/EventDetailsPopover'")
  })

  it('native event click (id starts with NATIVE_ID_PREFIX) sets clickedNativeEvent and returns before setClickedEvent', () => {
    const src = readSrc(PAGE)
    // The routing block must call setClickedNativeEvent before returning
    expect(src).toContain('ev.id.startsWith(NATIVE_ID_PREFIX)')
    expect(src).toContain('setClickedNativeEvent(raw)')
    // return must come before setClickedEvent in the native branch
    const nativeBranchStart = src.indexOf('ev.id.startsWith(NATIVE_ID_PREFIX)')
    const nativeBranchReturn = src.indexOf('return', nativeBranchStart)
    const setClickedEventCall = src.indexOf('setClickedEvent(clickedEvent?.id', nativeBranchStart)
    expect(nativeBranchReturn).toBeGreaterThan(nativeBranchStart)
    expect(nativeBranchReturn).toBeLessThan(setClickedEventCall)
  })

  it('MeetingPopover is still rendered for non-native meetings (clickedEvent type meeting)', () => {
    const src = readSrc(PAGE)
    expect(src).toContain("clickedEvent && clickedEvent.type === 'meeting'")
    expect(src).toContain('<MeetingPopover')
  })

  it('EventDetailsPopover is rendered for native events (clickedNativeEvent)', () => {
    const src = readSrc(PAGE)
    expect(src).toContain('clickedNativeEvent && (')
    expect(src).toContain('<EventDetailsPopover')
  })

  it('page contains no new useMutation calls beyond the original two', () => {
    const src = readSrc(PAGE)
    const count = (src.match(/useMutation\(/g) ?? []).length
    // original two: patchSettings and patchStaffColor
    expect(count).toBe(2)
  })
})
