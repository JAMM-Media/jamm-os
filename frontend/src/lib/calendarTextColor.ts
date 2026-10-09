// path: frontend/src/lib/calendarTextColor.ts

function parseHex(hex: string): [number, number, number] | null {
  const m = /^#([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})$/.exec(hex)
  if (!m) return null
  return [parseInt(m[1]!, 16), parseInt(m[2]!, 16), parseInt(m[3]!, 16)]
}

function linearize(c8: number): number {
  const c = c8 / 255
  return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4)
}

function relativeLuminance(r: number, g: number, b: number): number {
  return 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b)
}

export function contrastRatio(hexA: string, hexB: string): number {
  const a = parseHex(hexA)
  const b = parseHex(hexB)
  if (!a || !b) return 1
  const la = relativeLuminance(...a)
  const lb = relativeLuminance(...b)
  const lighter = Math.max(la, lb)
  const darker = Math.min(la, lb)
  return (lighter + 0.05) / (darker + 0.05)
}

// Prefer white text unless the fill's contrast against white falls below this threshold.
export const MIN_WHITE_CONTRAST = 3

export function readableTextColor(fillHex: string): '#FFFFFF' | '#111827' {
  const rgb = parseHex(fillHex)
  if (!rgb) return '#111827'
  return contrastRatio(fillHex, '#FFFFFF') >= MIN_WHITE_CONTRAST ? '#FFFFFF' : '#111827'
}
