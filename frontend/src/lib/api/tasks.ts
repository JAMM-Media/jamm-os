// path: frontend/src/lib/api/tasks.ts
import api from '@/lib/api'

export interface Task {
  id: string
  title: string
  status: string
  dueDate: string | null
  assignedTo: string | null
  notes: string | null
  isCompleted: boolean
  clientId: string
  engagementId: string
  createdAt: string
  updatedAt: string
}

function mapTask(raw: Record<string, unknown>): Task {
  return {
    id: String(raw.id),
    title: String(raw.title ?? ''),
    status: String(raw.status ?? 'todo'),
    dueDate: raw.due_date ? String(raw.due_date) : null,
    assignedTo: raw.assigned_to ? String(raw.assigned_to) : null,
    notes: raw.notes ? String(raw.notes) : null,
    isCompleted: Boolean(raw.is_completed ?? false),
    clientId: String(raw.client_id ?? ''),
    engagementId: String(raw.engagement_id ?? ''),
    createdAt: String(raw.created_at ?? ''),
    updatedAt: String(raw.updated_at ?? ''),
  }
}

export const tasksApi = {
  list: async (
    offset = 0,
    limit = 100,
    engagementId?: string,
    clientId?: string,
    status?: string
  ): Promise<{ items: Task[]; total: number }> => {
    const params: Record<string, unknown> = { offset, limit }
    if (engagementId) params.engagement_id = engagementId
    if (clientId) params.client_id = clientId
    if (status) params.status = status
    const { data } = await api.get('/tasks/', { params })
    const items = Array.isArray(data) ? data : (data.items ?? data.tasks ?? [])
    return {
      items: items.map(mapTask) as Task[],
      total: Number(data.total ?? items.length),
    }
  },

  get: async (id: string): Promise<Task> => {
    const { data } = await api.get(`/tasks/${id}`)
    return mapTask(data)
  },

  create: async (payload: {
    title: string
    client_id: string
    engagement_id: string
    due_date?: string
    assigned_to?: string
  }): Promise<Task> => {
    const { data } = await api.post('/tasks/', payload)
    return mapTask(data)
  },

  update: async (id: string, payload: Record<string, unknown>): Promise<Task> => {
    const { data } = await api.patch(`/tasks/${id}`, payload)
    return mapTask(data)
  },

  bulkUpdate: async (ids: string[], update: { status?: string; assigned_to?: string; due_date?: string }): Promise<{ updated: number }> => {
    const { data } = await api.patch('/tasks/bulk', { ids, update })
    return data
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`/tasks/${id}`)
  },
}
