// path: frontend/src/lib/api/leads.ts
import api from '@/lib/api'

export interface LeadActivityItem {
  id: string
  type: 'message' | 'event'
  occurredAt: string
  description: string
  sourceType: string
}

function mapActivity(raw: Record<string, unknown>): LeadActivityItem {
  return {
    id: String(raw.id),
    type: (raw.type as 'message' | 'event') ?? 'event',
    occurredAt: String(raw.occurred_at ?? ''),
    description: String(raw.description ?? ''),
    sourceType: String(raw.source_type ?? ''),
  }
}

export interface Lead {
  id: string
  firmId: string
  name: string
  email: string | null
  phone: string | null
  stage: string
  lostReason: string | null
  referralSource: string | null
  sourcePlatform: string | null
  hot: boolean
  provenance: string
  serviceInterest: string | null
  entityType: string | null
  urgency: string | null
  convertedClientId: string | null
  createdAt: string
  updatedAt: string
}

function mapLead(raw: Record<string, unknown>): Lead {
  return {
    id: String(raw.id),
    firmId: String(raw.firm_id ?? ''),
    name: String(raw.name ?? ''),
    email: raw.email ? String(raw.email) : null,
    phone: raw.phone ? String(raw.phone) : null,
    stage: String(raw.stage ?? 'identified'),
    lostReason: raw.lost_reason ? String(raw.lost_reason) : null,
    referralSource: raw.referral_source ? String(raw.referral_source) : null,
    sourcePlatform: raw.source_platform ? String(raw.source_platform) : null,
    hot: Boolean(raw.hot ?? false),
    provenance: String(raw.provenance ?? ''),
    serviceInterest: raw.service_interest ? String(raw.service_interest) : null,
    entityType: raw.entity_type ? String(raw.entity_type) : null,
    urgency: raw.urgency ? String(raw.urgency) : null,
    convertedClientId: raw.converted_client_id ? String(raw.converted_client_id) : null,
    createdAt: String(raw.created_at ?? ''),
    updatedAt: String(raw.updated_at ?? ''),
  }
}

export const leadsApi = {
  create: async (payload: {
    name: string
    email?: string
    phone?: string
    referral_source?: string
    hot?: boolean
  }): Promise<Lead> => {
    const { data } = await api.post('/api/v1/leads/', {
      ...payload,
      provenance: 'firm_entered',
    })
    return mapLead(data)
  },

  list: async (opts?: {
    stage?: string
    hot?: boolean
    limit?: number
    offset?: number
  }): Promise<{ items: Lead[]; total: number }> => {
    const params: Record<string, unknown> = {
      limit: opts?.limit ?? 100,
      offset: opts?.offset ?? 0,
    }
    if (opts?.stage) params.stage = opts.stage
    if (opts?.hot !== undefined) params.hot = opts.hot
    const { data } = await api.get('/api/v1/leads/', { params })
    const items = Array.isArray(data) ? data : (data.items ?? [])
    return { items: items.map(mapLead), total: Number(data.total ?? items.length) }
  },

  get: async (id: string): Promise<Lead> => {
    const { data } = await api.get(`/api/v1/leads/${id}`)
    return mapLead(data)
  },

  update: async (id: string, payload: Record<string, unknown>): Promise<Lead> => {
    const { data } = await api.patch(`/api/v1/leads/${id}`, payload)
    return mapLead(data)
  },

  transition: async (
    id: string,
    newStage: string,
    lostReason?: string
  ): Promise<Lead> => {
    const body: Record<string, unknown> = { new_stage: newStage }
    if (lostReason) body.lost_reason = lostReason
    const { data } = await api.post(`/api/v1/leads/${id}/transition`, body)
    return mapLead(data)
  },

  getActivity: async (id: string, limit = 50): Promise<LeadActivityItem[]> => {
    const { data } = await api.get(`/api/v1/leads/${id}/activity`, { params: { limit } })
    return Array.isArray(data) ? data.map(mapActivity) : []
  },
}
