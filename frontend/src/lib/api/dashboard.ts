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
  outstanding_ar: number
  outstanding_ar_count: number
  oldest_overdue_days: number | null
  wip_value: number
  wip_hours: number
  overdue_engagement_count: number
  overdue_engagements: OverdueEngagementItem[]
  upcoming_deadlines: UpcomingDeadlineItem[]
  staff_utilization: StaffUtilizationItem[]
  unsigned_document_count: number
  unsigned_documents: UnsignedDocumentItem[]
}

export interface DashboardItem {
  id: string
  type: 'task' | 'engagement'
  title: string
  clientName: string
  clientId: string
  status: string
  dueDate: string
  assignedTo: string
  href: string
}

export interface DashboardStats {
  totalClients: number
  activeEngagements: number
  overdue: number
  awaitingDocs: number
}

function mapTaskItem(raw: Record<string, unknown>): DashboardItem {
  return {
    id: String(raw.id),
    type: 'task',
    title: String(raw.title ?? ''),
    clientName: String(raw.client_name ?? raw.clientName ?? ''),
    clientId: String(raw.client_id ?? raw.clientId ?? ''),
    status: String(raw.status ?? ''),
    dueDate: String(raw.due_date ?? raw.dueDate ?? ''),
    assignedTo: String(raw.assigned_to ?? raw.assignedTo ?? ''),
    href: `/tasks/${raw.id}`,
  }
}

function mapEngagementItem(raw: Record<string, unknown>): DashboardItem {
  return {
    id: String(raw.id),
    type: 'engagement',
    title: String(raw.name ?? raw.title ?? ''),
    clientName: String(raw.client_name ?? raw.clientName ?? ''),
    clientId: String(raw.client_id ?? raw.clientId ?? ''),
    status: String(raw.status ?? ''),
    dueDate: String(raw.end_date ?? raw.due_date ?? raw.dueDate ?? ''),
    assignedTo: String(raw.assigned_to ?? raw.assignedTo ?? ''),
    href: `/engagements/${raw.id}`,
  }
}

export const dashboardApi = {
  getMetrics: async (): Promise<DashboardMetrics> => {
    const { data } = await api.get('/dashboard/metrics')
    return data as DashboardMetrics
  },

  getOverdue: async (): Promise<DashboardItem[]> => {
    const [tasks, engagements] = await Promise.all([
      api.get('/tasks', { params: { status_filter: 'overdue', limit: 20 } }),
      api.get('/engagements/', { params: { status_filter: 'overdue', limit: 20 } }),
    ])
    const taskItems = (tasks.data.items ?? tasks.data).map(mapTaskItem)
    const engItems = (engagements.data.items ?? engagements.data).map(mapEngagementItem)
    return [...taskItems, ...engItems].sort(
      (a, b) => new Date(a.dueDate).getTime() - new Date(b.dueDate).getTime()
    )
  },

  getAwaitingDocs: async (): Promise<DashboardItem[]> => {
    const { data } = await api.get('/engagements/', {
      params: { status_filter: 'awaiting_docs', limit: 20 },
    })
    return (data.items ?? data).map(mapEngagementItem)
  },

  getStats: async (): Promise<DashboardStats> => {
    const [clients, engagements, tasks, invoices] = await Promise.all([
      api.get('/clients/', { params: { limit: 1, offset: 0 } }),
      api.get('/engagements/', { params: { limit: 1, offset: 0, status_filter: 'in_progress' } }),
      api.get('/tasks/', { params: { limit: 1, offset: 0 } }),
      api.get('/invoices/', { params: { limit: 1, offset: 0, status: 'unpaid' } }).catch(() =>
        api.get('/invoices/', { params: { limit: 1, offset: 0, status: 'pending' } }).catch(() => ({ data: {} }))
      ),
    ])
    return {
      totalClients: Number(clients.data.total_count ?? clients.data.total ?? 0),
      activeEngagements: Number(engagements.data.total_count ?? engagements.data.total ?? 0),
      overdue: Number(tasks.data.total_count ?? tasks.data.total ?? 0),
      awaitingDocs: Number(invoices.data.total_count ?? invoices.data.total ?? 0),
    }
  },
}
