// path: frontend/src/lib/notificationPaths.ts

// One table drives both the click destination and the "Opens: X" label, so a
// label exists exactly when a path exists. needsId false means the page opens
// without an entity id.
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
  if (getEntityPath(type, id) === null) return null
  return lookupDestination(type as string)?.label ?? null
}
