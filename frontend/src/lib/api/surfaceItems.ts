// frontend/src/lib/api/surfaceItems.ts
import api from '@/lib/api'

export type DismissalReason = 'not_relevant' | 'already_handling' | 'was_wrong'

export interface SurfaceItemOut {
  id: string
  firm_id: string
  kind: string
  item_type: string
  dedup_key: string
  headline: string
  payload: Record<string, unknown>
  rank: number
  slotted_at: string | null
  appearance_count: number
  last_served_on: string | null
  dismissed_at: string | null
  dismissal_reason: DismissalReason | null
  implemented_at: string | null
  suppressed_until: string | null
  resolved_at: string | null
  value_at_action: Record<string, unknown> | null
  flagged_for_review: boolean
  // Computed server-side from payload.client_id; may be null.
  client_name: string | null
  created_at: string
  updated_at: string
}

export interface TierOneFact {
  category: string
  text: string
  count: number
  amount: number | null
}

export interface BriefingResponse {
  items: SurfaceItemOut[]
  count: number
  resolved_in_place: number
  summary: string
  facts: TierOneFact[]
  intelligence_pending: boolean
}

export interface PromoteNextResponse {
  promoted: boolean
  detail: string
  item: SurfaceItemOut | null
}

export interface SurfaceItemDetailOut {
  client: string
  engagement: string
  assigned_staff: string
  invoice_balance: string
  days_overdue: string
  current_workflow_status: string
  issued_date: string
  last_client_communication: string
  related_documents_count: number
  open_items: string
}

export const surfaceItemsApi = {
  getBriefing: async (): Promise<BriefingResponse> => {
    const { data } = await api.get('/api/v1/briefing')
    return data
  },

  dismissItem: async (id: string, reason: DismissalReason): Promise<SurfaceItemOut> => {
    const { data } = await api.post(`/api/v1/surface-items/${id}/dismiss`, { reason })
    return data
  },

  implementItem: async (id: string): Promise<SurfaceItemOut> => {
    const { data } = await api.post(`/api/v1/surface-items/${id}/implement`)
    return data
  },

  promoteNext: async (): Promise<PromoteNextResponse> => {
    const { data } = await api.post('/api/v1/briefing/promote-next')
    return data
  },

  getItemDetail: async (id: string): Promise<SurfaceItemDetailOut> => {
    const { data } = await api.get(`/api/v1/surface-items/${id}/detail`)
    return data
  },
}
