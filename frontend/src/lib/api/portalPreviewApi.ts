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

export interface PortalPreviewData {
  client_id: string
  client_name: string
  document_requests: PortalPreviewDocumentRequest[]
  documents: PortalPreviewDocument[]
  invoices: PortalPreviewInvoice[]
  messages: PortalPreviewMessages
  generated_at: string
}

export const portalPreviewApi = {
  get: (clientId: string) =>
    api.get<PortalPreviewData>(`/portal/preview/${clientId}`),
}
