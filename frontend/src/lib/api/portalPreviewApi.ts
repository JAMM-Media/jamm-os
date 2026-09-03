// frontend/src/lib/api/portalPreviewApi.ts
import api from '@/lib/api'

export interface PortalPreviewDocumentRequest {
  id: string
  title: string
  status: string
  due_date: string | null
  items_total: number
  items_completed: number
}

export interface PortalPreviewDocument {
  id: string
  name: string
  uploaded_at: string
  visibility: string
}

export interface PortalPreviewInvoice {
  id: string
  invoice_number: string
  amount_due: number
  status: string
  due_date: string | null
}

export interface PortalPreviewMessages {
  unread_count: number
  last_message_at: string | null
}

export interface PortalPreviewNotification {
  id: string
  title: string
  body: string | null
  notification_type: string
  is_read: boolean
  created_at: string
}

export interface PortalPreviewNotifications {
  unread_count: number
  recent: PortalPreviewNotification[]
}

export interface PortalPreviewBilling {
  total_invoiced: number
  total_outstanding: number
  invoice_count: number
}

export interface PortalPreviewOrganizer {
  organizer_count: number
  sent_count: number
  in_progress_count: number
  submitted_count: number
}

export interface PortalPreviewData {
  client_id: string
  client_name: string
  document_requests: PortalPreviewDocumentRequest[]
  documents: PortalPreviewDocument[]
  invoices: PortalPreviewInvoice[]
  messages: PortalPreviewMessages
  notifications: PortalPreviewNotifications
  billing: PortalPreviewBilling
  organizer: PortalPreviewOrganizer
  generated_at: string
}

export const portalPreviewApi = {
  get: (clientId: string) =>
    api.get<PortalPreviewData>(`/portal/preview/${clientId}`),
}
