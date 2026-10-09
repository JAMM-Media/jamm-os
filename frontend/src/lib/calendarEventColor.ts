// path: frontend/src/lib/calendarEventColor.ts

// COLOR_RE is not exported from calendarGridData.ts, so the same pattern is duplicated here.
// FALLBACK_EVENT_COLOR is imported from calendarGridData.ts (it is exported).
import { FALLBACK_EVENT_COLOR } from './calendarGridData'

const COLOR_RE = /^#[0-9A-Fa-f]{6}$/

/**
 * Returns the color to use for an event chip, dot or border.
 * Priority: the event's own color when it is a valid #RRGGBB string,
 * otherwise the type color when it is valid, otherwise the fallback gray.
 */
export function resolveEventColor(
  ownColor: string | null | undefined,
  typeColor: string | null | undefined,
): string {
  if (typeof ownColor === 'string' && COLOR_RE.test(ownColor)) return ownColor
  if (typeof typeColor === 'string' && COLOR_RE.test(typeColor)) return typeColor
  return FALLBACK_EVENT_COLOR
}
