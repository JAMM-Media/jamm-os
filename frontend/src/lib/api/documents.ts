// path: frontend/src/lib/api/documents.ts
import api from '@/lib/api'

export interface PendingDocument {
  id: string
  filename: string
  contentType: string
  clientNote: string | null
  createdAt: string
  clientName: string | null
  clientId: string
  engagementId: string
}

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
  is_superseded: boolean
  scope: string
  visibility: string
}

function mapDocument(raw: Record<string, unknown>): Document {
  return {
    id: String(raw.id),
    name: String(raw.filename ?? raw.file_name ?? raw.name ?? ''),
    clientId: String(raw.client_id ?? raw.clientId ?? ''),
    clientName: String(raw.client_name ?? raw.clientName ?? ''),
    engagementId: String(raw.engagement_id ?? raw.engagementId ?? ''),
    engagementTitle: String(raw.engagement_title ?? raw.engagementTitle ?? raw.engagement_name ?? ''),
    status: ((raw.envelope_status ?? raw.status) as Document['status']) ?? 'uploaded',
    uploadedBy: raw.uploaded_by_name
      ? String(raw.uploaded_by_name)
      : raw.uploaded_by
      ? 'Staff'
      : 'System',
    uploadedAt: String(raw.uploaded_at ?? raw.uploadedAt ?? ''),
    fileType: String(raw.file_type ?? raw.fileType ?? 'PDF'),
    fileSizeKb: raw.size_bytes
      ? Math.round(Number(raw.size_bytes) / 1024 * 10) / 10
      : Number(raw.file_size_kb ?? raw.fileSizeKb ?? 0),
    is_superseded: Boolean(raw.is_superseded ?? false),
    scope: String(raw.scope ?? 'client'),
    visibility: String(raw.visibility ?? 'internal'),
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

  patchSuperseded: async (id: string, is_superseded: boolean): Promise<void> => {
    await api.patch(`/documents/${id}/superseded`, { is_superseded })
  },

  shareToPortal: async (id: string): Promise<void> => {
    await api.post(`/documents/${id}/share-to-portal`)
  },

  unshareFromPortal: async (id: string): Promise<void> => {
    await api.post(`/documents/${id}/unshare-from-portal`)
  },

  listPending: async (engagementId: string): Promise<{ items: PendingDocument[]; total: number }> => {
    const { data } = await api.get('/documents/pending', { params: { engagement_id: engagementId } })
    const items: PendingDocument[] = (data.items ?? []).map((raw: Record<string, unknown>) => ({
      id: String(raw.id),
      filename: String(raw.filename ?? ''),
      contentType: String(raw.content_type ?? ''),
      clientNote: raw.client_note ? String(raw.client_note) : null,
      createdAt: String(raw.created_at ?? ''),
      clientName: raw.client_name ? String(raw.client_name) : null,
      clientId: String(raw.client_id ?? ''),
      engagementId: String(raw.engagement_id ?? ''),
    }))
    return { items, total: Number(data.total ?? items.length) }
  },

  approvePending: async (documentId: string): Promise<void> => {
    await api.post(`/documents/${documentId}/approve`)
  },

  reassignPending: async (documentId: string, destEngagementId: string): Promise<void> => {
    await api.post(`/documents/${documentId}/reassign`, { dest_engagement_id: destEngagementId })
  },
}
