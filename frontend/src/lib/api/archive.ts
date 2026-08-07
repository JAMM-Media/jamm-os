// frontend/src/lib/api/archive.ts
import api from '@/lib/api'

export interface ArchiveEntryClient {
  id: string
  name: string
}

export interface ArchiveEntryEngagement {
  id: string
  name: string
}

export interface ArchiveEntry {
  task_id: string
  task_title: string
  client: ArchiveEntryClient
  engagement: ArchiveEntryEngagement
  role: string
  completed_at: string | null
  completed_at_is_approximate: boolean
  revision_count: number | null
  reviewer: string | null
  hours: number
  starred: boolean
}

export interface ArchiveAggregates {
  tasks_completed: number
  hours_logged: number
  engagements_touched: number
}

export interface ArchiveResponse {
  items: ArchiveEntry[]
  total: number
  aggregates: ArchiveAggregates
}

export interface ArchiveParams {
  from?: string
  to?: string
  client_id?: string
  engagement_id?: string
  role?: string
  starred?: boolean
  search?: string
  page?: number
  page_size?: number
}

export const archiveApi = {
  getArchive: async (userId: string, params: ArchiveParams = {}): Promise<ArchiveResponse> => {
    const { data } = await api.get(`/archive/${userId}`, { params })
    return data as ArchiveResponse
  },

  starTask: async (taskId: string): Promise<void> => {
    await api.post(`/archive/entries/${taskId}/star`)
  },

  unstarTask: async (taskId: string): Promise<void> => {
    await api.delete(`/archive/entries/${taskId}/star`)
  },
}
