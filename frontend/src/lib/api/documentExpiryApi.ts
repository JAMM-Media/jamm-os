// frontend/src/lib/api/documentExpiryApi.ts
import api from '@/lib/api'

export interface DocumentExpiryRecord {
  id: string
  firm_id: string
  client_id: string
  document_id: string | null
  document_type: string
  description: string | null
  expires_on: string
  status: string
  expiry_notification_sent: boolean
  created_at: string
  updated_at: string
}

export interface DocumentExpiryCreatePayload {
  client_id: string
  document_type: string
  description?: string
  expires_on: string
  status?: string
  document_id?: string
}

export interface DocumentExpiryUpdatePayload {
  document_type?: string
  description?: string
  expires_on?: string
  status?: string
}

export const documentExpiryApi = {
  list: (clientId: string) =>
    api.get<DocumentExpiryRecord[]>('/document-expiries/', {
      params: { client_id: clientId },
    }),

  create: (payload: DocumentExpiryCreatePayload) =>
    api.post<DocumentExpiryRecord>('/document-expiries/', payload),

  update: (expiryId: string, payload: DocumentExpiryUpdatePayload) =>
    api.patch<DocumentExpiryRecord>(`/document-expiries/${expiryId}`, payload),

  delete: (expiryId: string) =>
    api.delete(`/document-expiries/${expiryId}`),
}
