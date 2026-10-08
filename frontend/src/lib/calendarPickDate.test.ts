// path: frontend/src/lib/calendarPickDate.test.ts
import { describe, it, expect } from 'vitest'
import { parsePickedDate } from './calendarPickDate'

describe('parsePickedDate', () => {
  it('accepts a normal date 2026-10-15', () => {
    const d = parsePickedDate('2026-10-15')
    expect(d).not.toBeNull()
    expect(d!.getFullYear()).toBe(2026)
    expect(d!.getMonth()).toBe(9)
    expect(d!.getDate()).toBe(15)
  })

  it('accepts the leap day 2028-02-29', () => {
    const d = parsePickedDate('2028-02-29')
    expect(d).not.toBeNull()
    expect(d!.getFullYear()).toBe(2028)
    expect(d!.getMonth()).toBe(1)
    expect(d!.getDate()).toBe(29)
  })

  it('rejects 2027-02-29 (not a leap year)', () => {
    expect(parsePickedDate('2027-02-29')).toBeNull()
  })

  it('DST spring-forward 2026-03-08 returns a Date with local hour 12', () => {
    const d = parsePickedDate('2026-03-08')
    expect(d).not.toBeNull()
    expect(d!.getFullYear()).toBe(2026)
    expect(d!.getMonth()).toBe(2)
    expect(d!.getDate()).toBe(8)
    expect(d!.getHours()).toBe(12)
  })

  it('DST fall-back 2026-11-01 returns a Date with local hour 12', () => {
    const d = parsePickedDate('2026-11-01')
    expect(d).not.toBeNull()
    expect(d!.getFullYear()).toBe(2026)
    expect(d!.getMonth()).toBe(10)
    expect(d!.getDate()).toBe(1)
    expect(d!.getHours()).toBe(12)
  })

  it.each([
    ['empty string', ''],
    ['partial date', '2026-10'],
    ['invalid month 13', '2026-13-01'],
    ['rolled-over Feb 30', '2026-02-30'],
    ['trailing text', '2026-10-15x'],
    ['leading space', ' 2026-10-15'],
    ['US slash format', '10/15/2026'],
  ])('rejects %s', (_label, value) => {
    expect(parsePickedDate(value)).toBeNull()
  })
})
