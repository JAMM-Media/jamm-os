// frontend/src/lib/api/extensionsApi.ts
import api from '@/lib/api'

export interface ExtensionRecord {
  id: string
  firm_id: string
  client_id: string
  engagement_id: string
  form_type: '4868' | '7004' | '8868'
  status: 'not_filed' | 'filed' | 'confirmed'
  filed_at: string
  extended_deadline: string
  notes: string | null
  created_at: string
  updated_at: string
}

export interface ExtensionFileRequest {
  engagement_id: string
  client_id: string
  form_type: '4868' | '7004' | '8868'
  filed_at?: string
  extended_deadline?: string
  notes?: string
}

export interface ExtensionUpdateRequest {
  status?: 'not_filed' | 'filed' | 'confirmed'
  notes?: string
  extended_deadline?: string
}

export const extensionsApi = {
  listForEngagement: (engagementId: string) =>
    api.get('/extensions/', {
      params: { engagement_id: engagementId },
    }),

  file: (payload: ExtensionFileRequest) =>
    api.post('/extensions/file', payload),

  update: (extId: string, payload: ExtensionUpdateRequest) =>
    api.patch(`/extensions/${extId}`, payload),
}
