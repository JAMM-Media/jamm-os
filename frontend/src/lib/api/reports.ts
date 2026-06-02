// path: frontend/src/lib/api/reports.ts
import api from '@/lib/api'

export interface WIPEngagement {
  engagementId: string
  engagementName: string
  clientName: string
  totalHours: number
  wipValue: number
}

export interface WIPSummary {
  totalWipValue: number
  totalHours: number
  topEngagements: WIPEngagement[]
}

function mapWIPSummary(raw: Record<string, unknown>): WIPSummary {
  const engagements = Array.isArray(raw.top_engagements) ? raw.top_engagements : []
  return {
    totalWipValue: Number(raw.total_wip_value ?? 0),
    totalHours: Number(raw.total_hours ?? 0),
    topEngagements: engagements.map((e: Record<string, unknown>) => ({
      engagementId: String(e.engagement_id),
      engagementName: String(e.engagement_name ?? ''),
      clientName: String(e.client_name ?? ''),
      totalHours: Number(e.total_hours ?? 0),
      wipValue: Number(e.wip_value ?? 0),
    })),
  }
}

export const reportsApi = {
  getWip: async (): Promise<WIPSummary> => {
    const { data } = await api.get('/reports/wip')
    return mapWIPSummary(data)
  },
}
