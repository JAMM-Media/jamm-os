// path: frontend/src/lib/calendarEventColor.test.ts
import { describe, it, expect } from 'vitest'
import { readFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'
import { resolveEventColor } from './calendarEventColor'

const cwd = process.cwd()
if (!existsSync(join(cwd, 'package.json'))) {
  throw new Error(`vitest must run from the frontend folder; cwd is ${cwd}`)
}

function readSrc(relPath: string): string {
  return readFileSync(join(cwd, 'src', relPath), 'utf8').replace(/\r\n/g, '\n')
}

const PAGE = 'app/(app)/calendar/page.tsx'

describe('resolveEventColor', () => {
  it('own valid color wins over type color', () => {
    expect(resolveEventColor('#FF0000', '#3F6E9A')).toBe('#FF0000')
    expect(resolveEventColor('#aabbcc', '#B4534B')).toBe('#aabbcc')
  })

  it('lowercase valid own color is accepted', () => {
    expect(resolveEventColor('#ab12ef', '#9CA3AF')).toBe('#ab12ef')
  })

  it('falls back to type color when own color is invalid', () => {
    const type = '#3F6E9A'
    expect(resolveEventColor('red',      type)).toBe(type)
    expect(resolveEventColor('#12',      type)).toBe(type)
    expect(resolveEventColor('#GGGGGG',  type)).toBe(type)
    expect(resolveEventColor('',         type)).toBe(type)
    expect(resolveEventColor(null,       type)).toBe(type)
    expect(resolveEventColor(undefined,  type)).toBe(type)
  })

  it('falls back to gray when both own color and type color are absent', () => {
    expect(resolveEventColor(null, null)).toBe('#9CA3AF')
    expect(resolveEventColor(undefined, undefined)).toBe('#9CA3AF')
  })

  it('falls back to gray when type color is also invalid', () => {
    expect(resolveEventColor('bad', 'alsoBad')).toBe('#9CA3AF')
  })

  it('an event with no color property uses the type color unchanged', () => {
    const type = '#4E8A6B'
    expect(resolveEventColor(undefined, type)).toBe(type)
  })
})

describe('calendarEventColor wiring: source guards', () => {
  it('page imports resolveEventColor from calendarEventColor', () => {
    const src = readSrc(PAGE)
    expect(src).toContain("import { resolveEventColor } from '@/lib/calendarEventColor'")
  })

  it('page uses resolveEventColor in renderPills (Month chip border color)', () => {
    const src = readSrc(PAGE)
    expect(src).toContain('const borderColor = resolveEventColor(ev.color, eventColors[ev.type])')
  })

  it('page uses resolveEventColor in AgendaView (dot color)', () => {
    const src = readSrc(PAGE)
    expect(src).toContain('const color = resolveEventColor(ev.color, eventColors[ev.type])')
  })

  it('page uses resolveEventColor in Upcoming list (dot backgroundColor)', () => {
    const src = readSrc(PAGE)
    expect(src).toContain('backgroundColor: resolveEventColor(ev.color, eventColors[ev.type])')
  })
})
