// path: frontend/src/lib/calendarTextColor.test.ts
import { describe, it, expect } from 'vitest'
import { contrastRatio, readableTextColor, MIN_WHITE_CONTRAST } from './calendarTextColor'

describe('contrastRatio', () => {
  it('white on black is 21:1', () => {
    expect(contrastRatio('#000000', '#FFFFFF')).toBeCloseTo(21, 0)
  })

  it('#FFFFFF on #FFFFFF is 1:1', () => {
    expect(contrastRatio('#FFFFFF', '#FFFFFF')).toBeCloseTo(1, 5)
  })
})

describe('readableTextColor', () => {
  it('returns #FFFFFF for dark blue #1F3148', () => {
    expect(readableTextColor('#1F3148')).toBe('#FFFFFF')
  })

  it('returns #FFFFFF for medium blue #3F6E9A', () => {
    expect(readableTextColor('#3F6E9A')).toBe('#FFFFFF')
  })

  it('returns #FFFFFF for meeting green #4E8A6B', () => {
    expect(readableTextColor('#4E8A6B')).toBe('#FFFFFF')
  })

  it('amber #B07D3A returns #FFFFFF under white-first rule', () => {
    expect(readableTextColor('#B07D3A')).toBe('#FFFFFF')
  })

  it('returns #111827 for beige #F5F5DC', () => {
    expect(readableTextColor('#F5F5DC')).toBe('#111827')
  })

  it('returns #111827 for yellow #FFE066', () => {
    expect(readableTextColor('#FFE066')).toBe('#111827')
  })

  it('#FFFFFF fill returns #111827', () => {
    expect(readableTextColor('#FFFFFF')).toBe('#111827')
  })

  it('#949494 white ratio 3.03 returns #FFFFFF (just above threshold)', () => {
    expect(readableTextColor('#949494')).toBe('#FFFFFF')
  })

  it('#969696 white ratio 2.96 returns #111827 (just below threshold)', () => {
    expect(readableTextColor('#969696')).toBe('#111827')
  })

  it('invalid string returns #111827', () => {
    expect(readableTextColor('not-a-color')).toBe('#111827')
  })

  it('empty string returns #111827', () => {
    expect(readableTextColor('')).toBe('#111827')
  })

  it('5-digit hex returns #111827 (invalid)', () => {
    expect(readableTextColor('#FFFFF')).toBe('#111827')
  })

  it('lowercase hex works: #ffffff gives #111827 (white on white is 1:1)', () => {
    expect(readableTextColor('#ffffff')).toBe('#111827')
  })

  it('lowercase hex works: #1f3148 gives #FFFFFF', () => {
    expect(readableTextColor('#1f3148')).toBe('#FFFFFF')
  })
})

describe('MIN_WHITE_CONTRAST', () => {
  it('equals 3', () => {
    expect(MIN_WHITE_CONTRAST).toBe(3)
  })
})
