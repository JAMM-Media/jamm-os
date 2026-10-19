// path: frontend/src/lib/notificationDisplay.ts
// Pure display helpers for the notifications page. No React or browser imports.

// Friendly names for every value of the backend NotificationType enum
// (app/core/enums.py). Keep in step with that enum.
export const NOTIFICATION_TYPE_LABELS: Record<string, string> = {
  task_assigned: 'Task assigned',
  doc_request_ready: 'Document request',
  esign_needed: 'Signature needed',
  payment_due: 'Payment due',
  system: 'General',
  deadline_alert: 'Deadline alert',
  irs_auth_expiry: 'IRS authorization expiring',
  irs_auth_missing: 'IRS authorization missing',
  extension_deadline: 'Extension deadline',
  client_anniversary: 'Client anniversary',
  document_expiry_alert: 'Document expiring',
  peer_network_mention: 'Peer Network',
  lead_replied: 'Lead replied',
  nurture_hold_for_approval: 'Approval needed',
  lead_hot_alert: 'Hot lead',
  nurture_dead_end_reached: 'Lead needs attention',
}

// Underscores and dots become spaces, first letter capitalized.
export function humanizeNotificationType(raw: string): string {
  const spaced = raw.replace(/[_.]+/g, ' ').trim()
  if (!spaced) return ''
  return spaced.charAt(0).toUpperCase() + spaced.slice(1)
}

export function getNotificationTypeLabel(type: string): string {
  if (Object.prototype.hasOwnProperty.call(NOTIFICATION_TYPE_LABELS, type)) {
    return NOTIFICATION_TYPE_LABELS[type]
  }
  return humanizeNotificationType(type)
}

export type DayGroup = 'today' | 'yesterday' | 'last7' | 'older'

export const DAY_GROUP_LABELS: Record<DayGroup, string> = {
  today: 'Today',
  yesterday: 'Yesterday',
  last7: 'Last 7 days',
  older: 'Older',
}

// Whole calendar days between two local dates, by year, month and day only.
// Date.UTC over the local components ignores the hour of day and any DST
// shift, so a 23 or 25 hour day still counts as exactly one day.
function localDayNumber(d: Date): number {
  return Math.round(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()) / 86400000)
}

// Groups by local calendar date. "Last 7 days" covers 2 to 7 calendar days
// ago; yesterday has its own group. A timestamp later than today (clock skew)
// counts as today. An unparseable timestamp counts as older.
export function getDayGroup(createdAtIso: string, now: Date): DayGroup {
  const created = new Date(createdAtIso)
  if (Number.isNaN(created.getTime())) return 'older'
  const diff = localDayNumber(now) - localDayNumber(created)
  if (diff <= 0) return 'today'
  if (diff === 1) return 'yesterday'
  if (diff <= 7) return 'last7'
  return 'older'
}

export interface DeleteRequestSplit {
  main: string
  reason: string | null
}

const DELETE_REQUEST_MARKER = ' has requested to delete "'

// KNOWN COUPLING: this parses the body text written by the backend in
// calendar_event_service._notify_delete_request:
//   '{name} has requested to delete "{event title}".' + optional ' {reason}'
// The proper fix is a separate reason field on the notification. Until then
// the split only happens when exactly one place in the body can end the
// sentence (a quote and period followed by a space or the end). Anything
// else is returned unchanged.
export function splitDeleteRequestBody(
  title: string,
  body: string,
  entityType?: string,
): DeleteRequestSplit {
  const unchanged: DeleteRequestSplit = { main: body, reason: null }
  if (title !== 'Delete request' || entityType !== 'calendar_event') return unchanged

  const markerAt = body.indexOf(DELETE_REQUEST_MARKER)
  if (markerAt <= 0) return unchanged

  const searchFrom = markerAt + DELETE_REQUEST_MARKER.length
  const ends: number[] = []
  for (let i = body.indexOf('".', searchFrom); i !== -1; i = body.indexOf('".', i + 1)) {
    const after = i + 2
    if (after === body.length || body[after] === ' ') ends.push(after)
  }
  if (ends.length !== 1) return unchanged

  const end = ends[0]
  if (end === body.length) return unchanged
  const reason = body.slice(end).trim()
  if (!reason) return unchanged
  return { main: body.slice(0, end), reason }
}

// Concatenated pages can overlap when new rows arrive mid-session and shift
// the offsets. Keeps the first occurrence of each id, preserving order.
export function dedupeById<T extends { id: string }>(rows: T[]): T[] {
  const seen = new Set<string>()
  const out: T[] = []
  for (const row of rows) {
    if (seen.has(row.id)) continue
    seen.add(row.id)
    out.push(row)
  }
  return out
}
