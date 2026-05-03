// path: frontend/src/lib/api/documentRequests.ts
import api from '@/lib/api'

export interface ChecklistItem {
  id: string
  label: string
  description: string
  is_required: boolean
  status: 'pending' | 'uploaded' | 'approved' | 'rejected'
}

export interface DocumentRequest {
  id: string
  title: string
  client_id: string
  engagement_id: string
  due_date?: string | null
  created_at: string
  checklist_items: ChecklistItem[]
}

export interface CreateDocumentRequestPayload {
  title: string
  client_id: string
  engagement_id: string
  due_date?: string
  checklist_items: ChecklistItem[]
}

export const documentRequestsApi = {
  list: (engagementId: string): Promise<DocumentRequest[]> =>
    api
      .get('/document-requests/', {
        params: { engagement_id: engagementId },
      })
      .then((r) => r.data?.items ?? r.data),

  get: (id: string): Promise<DocumentRequest> =>
    api.get<DocumentRequest>(`/document-requests/${id}`).then((r) => r.data),

  create: (payload: CreateDocumentRequestPayload): Promise<DocumentRequest> =>
    api.post<DocumentRequest>('/document-requests/', payload).then((r) => r.data),

  updateItem: (
    requestId: string,
    itemId: string,
    status: 'approved' | 'rejected'
  ): Promise<void> =>
    api
      .patch(`/document-requests/${requestId}/items/${itemId}`, { status })
      .then(() => undefined),
}