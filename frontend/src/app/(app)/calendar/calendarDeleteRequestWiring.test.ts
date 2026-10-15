// path: frontend/src/app/(app)/calendar/calendarDeleteRequestWiring.test.ts
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
const POPOVER = 'components/calendar/EventDetailsPopover.tsx'

describe('calendarDeleteRequest wiring: source guards', () => {
  it('EventDetailsPopover imports getDeleteRequestActions', () => {
    const src = readSrc(POPOVER)
    expect(src).toContain('getDeleteRequestActions')
  })

  it('EventDetailsPopover calls calendarEventsApi.requestDelete', () => {
    const src = readSrc(POPOVER)
    expect(src).toContain('calendarEventsApi.requestDelete')
  })

  it('EventDetailsPopover calls calendarEventsApi.approveDeleteRequest', () => {
    const src = readSrc(POPOVER)
    expect(src).toContain('calendarEventsApi.approveDeleteRequest')
  })

  it('EventDetailsPopover calls calendarEventsApi.denyDeleteRequest', () => {
    const src = readSrc(POPOVER)
    expect(src).toContain('calendarEventsApi.denyDeleteRequest')
  })

  it('page EventDetailsPopover render passes no extra props beyond the original six', () => {
    const src = readSrc(PAGE)
    const blockStart = src.indexOf('<EventDetailsPopover')
    const blockEnd = src.indexOf('/>', blockStart)
    const block = src.slice(blockStart, blockEnd + 2)
    expect(block).toContain('event={clickedNativeEvent}')
    expect(block).toContain('pos={popoverPos}')
    expect(block).toContain('onClose=')
    expect(block).toContain('onMutated=')
    expect(block).toContain('timeZone=')
    expect(block).toContain('user=')
  })

  it('page contains no new useMutation calls beyond the original two', () => {
    const src = readSrc(PAGE)
    const count = (src.match(/useMutation\(/g) ?? []).length
    // original two: patchSettings and patchStaffColor
    expect(count).toBe(2)
  })
})
