// path: frontend/src/lib/notificationPaths.ts

// One table drives both the click destination and the "Opens: X" label, so a
// label exists exactly when a path exists, apart from the async destinations
// further down. needsId false means the page opens without an entity id.
interface EntityDestination {
  label: string
  needsId: boolean
  path: (id?: string) => string
}

const ENTITY_DESTINATIONS: Record<string, EntityDestination> = {
  time_entry: { label: 'Timesheets', needsId: false, path: () => '/timesheets' },
  staff_credential: { label: 'Staff', needsId: false, path: () => '/staff' },
  calendar_event: { label: 'Calendar', needsId: false, path: () => '/calendar' },
  engagement: { label: 'Engagement', needsId: true, path: (id) => `/engagements/${id}` },
  task: { label: 'Task', needsId: true, path: (id) => `/tasks/${id}` },
  client: { label: 'Client', needsId: true, path: (id) => `/clients/${id}` },
  lead: { label: 'Lead', needsId: true, path: (id) => `/leads/${id}` },
  document: { label: 'Document', needsId: true, path: (id) => `/documents/${id}` },
  message: { label: 'Firm chat', needsId: true, path: () => '/firm-chat' },
}

export const NOTIFICATION_ENTITY_TYPES: string[] = Object.keys(ENTITY_DESTINATIONS)

// Destinations that need a lookup before they can open. getEntityPath stays
// synchronous and returns null for these. The notifications page resolves the
// path on click, and the label below is static so the row can say where it goes.
const ASYNC_DESTINATION_LABELS: Record<string, string> = {
  irs_authorization: 'Client IRS authorizations',
}

export function isAsyncDestination(type?: string): boolean {
  return !!type && Object.prototype.hasOwnProperty.call(ASYNC_DESTINATION_LABELS, type)
}

function lookupDestination(type: string): EntityDestination | null {
  return Object.prototype.hasOwnProperty.call(ENTITY_DESTINATIONS, type)
    ? ENTITY_DESTINATIONS[type]
    : null
}

export function getEntityPath(type?: string, id?: string): string | null {
  if (!type) return null
  const dest = lookupDestination(type)
  if (!dest) return null
  if (dest.needsId && !id) return null
  return dest.path(id)
}

export function getEntityDestinationLabel(type?: string, id?: string): string | null {
  // An async destination cannot open without an id to look up.
  if (isAsyncDestination(type)) return id ? ASYNC_DESTINATION_LABELS[type as string] : null
  if (getEntityPath(type, id) === null) return null
  return lookupDestination(type as string)?.label ?? null
}
