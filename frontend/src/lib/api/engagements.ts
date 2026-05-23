// path: frontend/src/lib/api/engagements.ts
import api from '@/lib/api'

export interface Engagement {
  id: string
  name: string
  description: string | null
  status: string
  startDate: string | null
  endDate: string | null
  filingDeadline: string | null
  extendedDeadline: string | null
  engagementType: string | null
  isActive: boolean
  clientId: string
  notes: string | null
  createdAt: string
  updatedAt: string
}

function mapEngagement(raw: Record<string, unknown>): Engagement {
  return {
    id: String(raw.id),
    name: String(raw.name ?? raw.title ?? ''),
    description: raw.description ? String(raw.description) : null,
    status: String(raw.status ?? 'planning'),
    startDate: raw.start_date ? String(raw.start_date) : null,
    endDate: raw.end_date ? String(raw.end_date) : null,
    filingDeadline: raw.filing_deadline ? String(raw.filing_deadline) : null,
    extendedDeadline: raw.extended_deadline ? String(raw.extended_deadline) : null,
    engagementType: raw.engagement_type ? String(raw.engagement_type) : null,
    isActive: Boolean(raw.is_active ?? true),
    clientId: String(raw.client_id ?? ''),
    notes: raw.notes ? String(raw.notes) : null,
    createdAt: String(raw.created_at ?? ''),
    updatedAt: String(raw.updated_at ?? ''),
  }
}

export const engagementsApi = {
  list: async (
    offset = 0,
    limit = 100,
    clientId?: string,
    statusFilter?: string
  ): Promise<{ items: Engagement[]; total: number }> => {
    const params: Record<string, unknown> = { offset, limit }
    if (clientId) params.client_id = clientId
    if (statusFilter) params.status_filter = statusFilter
    const { data } = await api.get('/engagements/', { params })
    const items = Array.isArray(data) ? data : (data.items ?? data.engagements ?? [])
    return {
      items: items.map(mapEngagement) as Engagement[],
      total: Number(data.total ?? items.length),
    }
  },

  get: async (id: string): Promise<Engagement> => {
    const { data } = await api.get(`/engagements/${id}`)
    return mapEngagement(data)
  },

  create: async (payload: {
    name: string
    client_id: string
    engagement_type?: string
    end_date?: string
  }): Promise<Engagement> => {
    const { data } = await api.post('/engagements/', payload)
    return mapEngagement(data)
  },

  update: async (id: string, payload: Record<string, unknown>): Promise<Engagement> => {
    const { data } = await api.patch(`/engagements/${id}`, payload)
    return mapEngagement(data)
  },

  bulkUpdate: async (ids: string[], update: { status?: string; deadline_push_days?: number }): Promise<{ updated: number }> => {
    const { data } = await api.patch('/engagements/bulk', { ids, update })
    return data
  },

  bulkCreate: async (payload: {
    client_ids: string[]
    name: string
    engagement_type?: string
    status?: string
    start_date?: string
    end_date?: string
    notes?: string
    filing_deadline?: string
  }): Promise<{ created: number; engagement_ids: string[]; skipped: number }> => {
    const { data } = await api.post('/engagements/bulk-create', payload)
    return data
  },

  bulkSendLetter: async (payload: {
    engagement_ids: string[]
    template_id: string
    fee_amount?: string
  }): Promise<{ sent: number; failed: number; errors: string[] }> => {
    const { data } = await api.post('/engagements/bulk-send-letter', payload)
    return data
  },

  getCalendar: async (days = 180): Promise<CalendarItem[]> => {
    const { data } = await api.get('/engagements/calendar', { params: { days } })
    const items = Array.isArray(data) ? data : (data.items ?? [])
    return items.map((item: Record<string, unknown>) => ({
      engagementId: String(item.engagement_id),
      engagementName: String(item.engagement_name ?? ''),
      engagementType: item.engagement_type ? String(item.engagement_type) : null,
      clientId: String(item.client_id),
      clientName: String(item.client_name ?? ''),
      effectiveDeadline: String(item.effective_deadline),
      deadlineType: String(item.deadline_type ?? 'filing') as 'extended' | 'filing',
      status: String(item.status ?? ''),
    }))
  },
}

export interface CalendarItem {
  engagementId: string
  engagementName: string
  engagementType: string | null
  clientId: string
  clientName: string
  effectiveDeadline: string
  deadlineType: 'extended' | 'filing'
  status: string
}
