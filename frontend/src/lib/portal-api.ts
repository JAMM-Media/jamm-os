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

export async function getPortalDocuments(): Promise<PortalDocument[]> {
  const res = await fetch(`${BASE}/portal/documents`, { headers: portalHeaders() })
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
