// path: frontend/src/lib/api/documents.ts
import api from '@/lib/api'

export interface Document {
  id: string
  name: string
  clientId: string
  clientName: string
  engagementId: string
  engagementTitle: string
  status: 'uploaded' | 'pending' | 'pending_signature' | 'signed' | 'rejected'
  uploadedBy: string
  uploadedAt: string
  fileType: string
  fileSizeKb: number
}

function mapDocument(raw: Record<string, unknown>): Document {
  return {
    id: String(raw.id),
    name: String(raw.filename ?? raw.file_name ?? raw.name ?? ''),
    clientId: String(raw.client_id ?? raw.clientId ?? ''),
    clientName: String(raw.client_name ?? raw.clientName ?? ''),
    engagementId: String(raw.engagement_id ?? raw.engagementId ?? ''),
    engagementTitle: String(raw.engagement_title ?? raw.engagementTitle ?? ''),
    status: ((raw.envelope_status ?? raw.status) as Document['status']) ?? 'uploaded',
    uploadedBy: String(raw.uploaded_by ?? raw.uploadedBy ?? ''),
    uploadedAt: String(raw.uploaded_at ?? raw.uploadedAt ?? ''),
    fileType: String(raw.file_type ?? raw.fileType ?? 'PDF'),
    fileSizeKb: raw.size_bytes
      ? Number(raw.size_bytes) / 1024
      : Number(raw.file_size_kb ?? raw.fileSizeKb ?? 0),
  }
}

export const documentsApi = {
  list: async (offset = 0, limit = 50, clientId?: string, engagementId?: string): Promise<{ items: Document[]; total: number }> => {
    const params: Record<string, unknown> = { offset, limit }
    if (clientId) params.client_id = clientId
    if (engagementId) params.engagement_id = engagementId
    const { data } = await api.get('/documents', { params })
    return {
      items: (data.items ?? data).map(mapDocument) as Document[],
      total: Number(data.total_count ?? data.total ?? (data.items ?? data).length),
    }
  },

  get: async (id: string): Promise<Document> => {
    const { data } = await api.get(`/documents/${id}`)
    return mapDocument(data)
  },

  getSignedUrl: async (id: string): Promise<string> => {
    const { data } = await api.get(`/documents/${id}/download`)
    return String(data.url ?? data.signed_url ?? '')
  },

  upload: async (file: File, clientId?: string, engagementId?: string): Promise<Document> => {
    const formData = new FormData()
    formData.append('file', file)
    if (clientId) formData.append('client_id', clientId)
    if (engagementId) formData.append('engagement_id', engagementId)
    const { data } = await api.post('/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return mapDocument(data)
  },
}
