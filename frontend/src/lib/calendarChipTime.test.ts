// path: frontend/src/lib/calendarChipTime.test.ts
import { describe, it, expect } from 'vitest'
import { formatChipTime, sortDayEvents } from './calendarChipTime'
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

describe('formatChipTime', () => {
  it('2026-10-15T13:00:00Z in America/New_York gives 9:00a', () => {
    expect(formatChipTime('2026-10-15T13:00:00Z', 'America/New_York')).toBe('9:00a')
  })

  it('2026-10-15T17:15:00Z in America/New_York gives 1:15p', () => {
    expect(formatChipTime('2026-10-15T17:15:00Z', 'America/New_York')).toBe('1:15p')
  })

  it('2026-10-15T16:00:00Z in America/New_York gives 12:00p', () => {
    expect(formatChipTime('2026-10-15T16:00:00Z', 'America/New_York')).toBe('12:00p')
  })

  it('2026-10-15T04:00:00Z in America/New_York gives 12:00a', () => {
    expect(formatChipTime('2026-10-15T04:00:00Z', 'America/New_York')).toBe('12:00a')
  })

  it('2026-10-16T02:30:00Z in America/New_York gives 10:30p', () => {
    expect(formatChipTime('2026-10-16T02:30:00Z', 'America/New_York')).toBe('10:30p')
  })

  it('2026-10-15T03:30:00Z in Asia/Kolkata gives 9:00a', () => {
    expect(formatChipTime('2026-10-15T03:30:00Z', 'Asia/Kolkata')).toBe('9:00a')
  })

  it('DST: 2026-11-01T14:00:00Z in America/New_York gives 9:00a', () => {
    expect(formatChipTime('2026-11-01T14:00:00Z', 'America/New_York')).toBe('9:00a')
  })

  it('DST: 2026-03-08T13:00:00Z in America/New_York gives 9:00a', () => {
    expect(formatChipTime('2026-03-08T13:00:00Z', 'America/New_York')).toBe('9:00a')
  })

  it('+05:30 offset string input works', () => {
    expect(formatChipTime('2026-10-15T09:00:00+05:30', 'Asia/Kolkata')).toBe('9:00a')
  })

  it('null returns null', () => {
    expect(formatChipTime(null, 'America/New_York')).toBeNull()
  })

  it('undefined returns null', () => {
    expect(formatChipTime(undefined, 'America/New_York')).toBeNull()
  })

  it('empty string returns null', () => {
    expect(formatChipTime('', 'America/New_York')).toBeNull()
  })

  it('no offset returns null', () => {
    expect(formatChipTime('2026-10-15T09:00:00', 'America/New_York')).toBeNull()
  })

  it('invalid zone returns null', () => {
    expect(formatChipTime('2026-10-15T13:00:00Z', 'Not/AReal')).toBeNull()
  })

  it('null zone returns null', () => {
    expect(formatChipTime('2026-10-15T13:00:00Z', null)).toBeNull()
  })
})

describe('sortDayEvents', () => {
  const NY = 'America/New_York'

  it('untimed items come first, timed items follow ascending by start', () => {
    const a = { id: 'a', startAt: null as string | null, endAt: null as string | null }
    const b = { id: 'b', startAt: '2026-10-15T17:00:00Z', endAt: '2026-10-15T18:00:00Z' }
    const c = { id: 'c', startAt: '2026-10-15T14:00:00Z', endAt: '2026-10-15T15:00:00Z' }
    const result = sortDayEvents([a, b, c], NY)
    expect(result.map(e => e.id)).toEqual(['a', 'c', 'b'])
  })

  it('mixed offsets: Z instant before -04:00 instant sorts correctly', () => {
    // 13:00Z = 9:00am EDT; 09:30-04:00 = 9:30am EDT; so Z event is first
    const first = { id: 'first', startAt: '2026-10-15T13:00:00Z', endAt: '2026-10-15T14:00:00Z' }
    const second = { id: 'second', startAt: '2026-10-15T09:30:00-04:00', endAt: '2026-10-15T10:30:00-04:00' }
    const result = sortDayEvents([second, first], NY)
    expect(result.map(e => e.id)).toEqual(['first', 'second'])
  })

  it('ties keep original order', () => {
    const a = { id: 'a', startAt: '2026-10-15T13:00:00Z', endAt: '2026-10-15T14:00:00Z' }
    const b = { id: 'b', startAt: '2026-10-15T13:00:00Z', endAt: '2026-10-15T14:00:00Z' }
    const result = sortDayEvents([a, b], NY)
    expect(result.map(e => e.id)).toEqual(['a', 'b'])
  })

  it('untimed events keep their original relative order', () => {
    const a = { id: 'a', startAt: null as string | null, endAt: null as string | null }
    const b = { id: 'b', startAt: undefined as string | undefined, endAt: undefined as string | undefined }
    const c = { id: 'c', startAt: null as string | null, endAt: null as string | null }
    const result = sortDayEvents([a, b, c], NY)
    expect(result.map(e => e.id)).toEqual(['a', 'b', 'c'])
  })

  it('does not mutate the input array', () => {
    const a = { id: 'a', startAt: '2026-10-15T17:00:00Z', endAt: '2026-10-15T18:00:00Z' }
    const b = { id: 'b', startAt: '2026-10-15T13:00:00Z', endAt: '2026-10-15T14:00:00Z' }
    const input = [a, b]
    sortDayEvents(input, NY)
    expect(input.map(e => e.id)).toEqual(['a', 'b'])
  })

  it('empty array returns empty array', () => {
    expect(sortDayEvents([], NY)).toEqual([])
  })

  it('null zone treats everything as untimed and returns original order', () => {
    const a = { id: 'a', startAt: '2026-10-15T17:00:00Z', endAt: '2026-10-15T18:00:00Z' }
    const b = { id: 'b', startAt: '2026-10-15T13:00:00Z', endAt: '2026-10-15T14:00:00Z' }
    const result = sortDayEvents([a, b], null)
    expect(result.map(e => e.id)).toEqual(['a', 'b'])
  })
})

describe('calendarChipTime wiring: source guards', () => {
  it('page imports formatChipTime and sortDayEvents from calendarChipTime', () => {
    const src = readSrc(PAGE)
    expect(src).toContain("import { formatChipTime, sortDayEvents } from '@/lib/calendarChipTime'")
  })

  it('page calls sortDayEvents in the Month cell path with firmTz', () => {
    const src = readSrc(PAGE)
    expect(src).toContain("sortDayEvents(byDate[ds] ?? [], firmTzValid ? firmTz : null)")
  })

  it('page calls formatChipTime in renderPills', () => {
    const src = readSrc(PAGE)
    const pillsIdx = src.indexOf('function renderPills(')
    expect(pillsIdx).toBeGreaterThan(-1)
    const pillsSlice = src.slice(pillsIdx, pillsIdx + 800)
    expect(pillsSlice).toContain('formatChipTime(ev.startAt, firmTzValid ? firmTz : null)')
  })
})
