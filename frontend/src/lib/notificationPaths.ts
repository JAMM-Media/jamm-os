// path: frontend/src/lib/notificationPaths.ts
export function getEntityPath(type?: string, id?: string): string | null {
  if (!type) return null
  if (type === 'time_entry') return '/timesheets'
  if (type === 'staff_credential') return '/staff'
  if (!id) return null
  const map: Record<string, string> = {
    engagement: `/engagements/${id}`,
    task: `/tasks/${id}`,
    client: `/clients/${id}`,
    lead: `/leads/${id}`,
    document: `/documents/${id}`,
    message: '/firm-chat',
  }
  return map[type] ?? null
}
