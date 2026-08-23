// frontend/src/lib/portal-api.ts

const BASE = '/api/backend'

function portalHeaders(): HeadersInit {
  const token =
    typeof window !== 'undefined' ? localStorage.getItem('portal_access_token') : null
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`
  return headers
}

export interface PortalInvoiceLineItem {
  id: string
  description: string
  quantity: number
  unit_price: number
  total: number
}

export interface PortalInvoice {
  id: string
  invoice_number: string
  total_amount: number
  status: 'draft' | 'sent' | 'paid' | 'overdue' | 'void'
  due_date: string | null
  sent_at: string | null
  created_at: string
  line_items?: PortalInvoiceLineItem[]
}

export interface PortalInvoicesResponse {
  items: PortalInvoice[]
  total: number
  limit: number
  offset: number
}

export interface PortalDocument {
  id: string
  name: string
  uploaded_at: string
  file_type: string
  file_size_kb: number
  uploaded_by: 'client' | 'firm'
  is_superseded: boolean
}

export interface PortalFolder {
  id: string
  name: string
  parent_folder_id: string | null
  firm_id: string
  client_id: string
  created_at: string
  updated_at: string
}

export interface PortalMessage {
  id: string
  body: string
  sender_role: 'staff' | 'client'
  sender_name: string | null
  created_at: string
}

export interface PortalDashboard {
  active_engagements: Array<{ id: string; name: string; status: string }>
  pending_signatures: Array<{
    id: string
    engagement_id: string | null
    status: string
    sent_at: string | null
  }>
  pending_document_requests: Array<{
    id: string
    title?: string
    due_date?: string | null
    status?: string
  }>
  unread_notification_count: number
}

export async function getPortalInvoices(): Promise<PortalInvoicesResponse> {
  const res = await fetch(`${BASE}/portal/invoices?limit=100`, { headers: portalHeaders() })
  if (!res.ok) throw new Error('fetch failed')
  return res.json()
}

export async function getPortalDocuments(folderId?: string): Promise<PortalDocument[]> {
  const url = folderId
    ? `${BASE}/portal/documents?folder_id=${folderId}`
    : `${BASE}/portal/documents`
  const res = await fetch(url, { headers: portalHeaders() })
  if (!res.ok) throw new Error('fetch failed')
  const data = await res.json()
  return Array.isArray(data) ? data : []
}

export async function getPortalFolders(): Promise<PortalFolder[]> {
  const res = await fetch(`${BASE}/portal/folders`, { headers: portalHeaders() })
  if (!res.ok) throw new Error('fetch failed')
  const data = await res.json()
  return Array.isArray(data) ? data : []
}

export async function getPortalMessages(clientId: string): Promise<PortalMessage[]> {
  const res = await fetch(`${BASE}/portal/clients/${clientId}/messages`, {
    headers: portalHeaders(),
  })
  if (!res.ok) throw new Error('fetch failed')
  const data = await res.json()
  return Array.isArray(data) ? data : []
}

export async function sendPortalMessage(clientId: string, body: string): Promise<PortalMessage> {
  const res = await fetch(`${BASE}/portal/clients/${clientId}/messages`, {
    method: 'POST',
    headers: portalHeaders(),
    body: JSON.stringify({ body }),
  })
  if (!res.ok) throw new Error('fetch failed')
  return res.json()
}

export async function getPortalDashboard(): Promise<PortalDashboard> {
  const res = await fetch(`${BASE}/portal/dashboard`, { headers: portalHeaders() })
  if (!res.ok) throw new Error('fetch failed')
  return res.json()
}

export async function getPortalUnreadCount(clientId: string): Promise<number> {
  const res = await fetch(`${BASE}/portal/clients/${clientId}/messages/unread-count`, {
    headers: portalHeaders(),
  })
  if (!res.ok) return 0
  const data = await res.json()
  return data.unread_count ?? 0
}

export interface BillingDetailEntry {
  date: string
  staff_name: string
  engagement_name: string
  activity_type: string | null
  description: string
  hours: number
  hourly_rate: number
  amount: number
  is_billable: boolean
}

export interface BillingDetailReport {
  id: string
  date_from: string | null
  date_to: string | null
  engagement_id: string | null
  total_hours: number
  total_amount: number
  created_at: string
  entries: BillingDetailEntry[]
}

export async function getPortalBillingDetail(): Promise<BillingDetailReport[]> {
  const res = await fetch(`${BASE}/portal/billing-detail`, { headers: portalHeaders() })
  if (!res.ok) throw new Error('fetch failed')
  const data = await res.json()
  return Array.isArray(data) ? data : []
}

export interface PortalNotification {
  id: string
  title: string
  body: string | null
  notification_type: string
  is_read: boolean
  is_pinned: boolean
  read_at: string | null
  related_entity_type: string | null
  related_entity_id: string | null
  created_at: string
}

export async function getPortalNotifications(limit = 20, skip = 0): Promise<PortalNotification[]> {
  const res = await fetch(`${BASE}/portal/notifications?limit=${limit}&skip=${skip}`, {
    headers: portalHeaders(),
  })
  if (!res.ok) throw new Error('fetch failed')
  const data = await res.json()
  return Array.isArray(data) ? data : []
}

export async function markAllPortalNotificationsRead(): Promise<{ marked_read: number }> {
  const res = await fetch(`${BASE}/portal/notifications/read-all`, {
    method: 'POST',
    headers: portalHeaders(),
  })
  if (!res.ok) throw new Error('fetch failed')
  return res.json()
}

export interface SurveyOption {
  value: string
  label: string
}

export interface AttributionSurveyData {
  question: string
  options: SurveyOption[]
}

export async function getAttributionSurvey(): Promise<AttributionSurveyData> {
  const res = await fetch(`${BASE}/portal/attribution-survey`, {
    headers: portalHeaders(),
  })
  if (!res.ok) throw new Error('fetch failed')
  return res.json()
}

export async function submitAttributionSurvey(answer: string): Promise<{ written: boolean }> {
  const res = await fetch(`${BASE}/portal/attribution-survey`, {
    method: 'POST',
    headers: portalHeaders(),
    body: JSON.stringify({ answer }),
  })
  if (!res.ok) throw new Error('submit failed')
  return res.json()
}
