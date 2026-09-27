// path: frontend/src/lib/api/dashboard.ts
import api from '@/lib/api'

export interface StaffUtilizationItem {
  user_id: string
  full_name: string
  hours_this_week: number
  utilization_pct: number
}

export interface UpcomingDeadlineItem {
  engagement_id: string
  client_name: string
  engagement_type: string
  deadline: string
  days_until: number
  status: string
}

export interface OverdueEngagementItem {
  engagement_id: string
  client_name: string
  engagement_type: string
  deadline: string
  days_overdue: number
  status: string
  assigned_staff_name: string | null
}

export interface UnsignedDocumentItem {
  envelope_id: string
  client_name: string
  document_title: string
  sent_at: string
  days_waiting: number
  reminder_count: number
  auto_reminder_sent_at: string | null
  last_reminder_sent_at: string | null
  escalated_at: string | null
  followup_task_id: string | null
  reminder_state: 'ready_first' | 'ready_second' | 'escalated'
}

export interface DashboardMetrics {
  mrr: number
  mrr_invoice_count: number
  mrr_trend_pct: number | null
  mrr_trend_direction: 'up' | 'down' | null
  outstanding_ar: number
  outstanding_ar_count: number
  oldest_overdue_days: number | null
  ar_trend_pct: number | null
  ar_trend_direction: 'up' | 'down' | null
  wip_value: number
  wip_hours: number
  wip_trend_pct: number | null
  wip_trend_direction: 'up' | 'down' | null
  overdue_engagement_count: number
  overdue_engagements: OverdueEngagementItem[]
  upcoming_deadlines: UpcomingDeadlineItem[]
  staff_utilization: StaffUtilizationItem[]
  unsigned_document_count: number
  unsigned_documents: UnsignedDocumentItem[]
  top_engagements: WIPEngagement[]
}

export interface DashboardSectionItem {
  key: string
  visible: boolean
  order: number
}

export interface WIPEngagement {
  engagement_id: string
  engagement_name: string
  client_name: string
  total_hours: number
  wip_value: number
}

export const dashboardApi = {
  getMetrics: async (): Promise<DashboardMetrics> => {
    const { data } = await api.get('/dashboard/metrics')
    return data as DashboardMetrics
  },

  getSections: async (): Promise<DashboardSectionItem[]> => {
    const { data } = await api.get('/dashboard/sections')
    return (data as { sections: DashboardSectionItem[] }).sections
  },

  updateSections: async (sections: DashboardSectionItem[]): Promise<void> => {
    await api.put('/dashboard/sections', { sections })
  },
}

