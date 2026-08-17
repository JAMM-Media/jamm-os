// frontend/src/lib/api/staffApi.ts
import api from '@/lib/api'

export interface StaffMember {
  id: string
  email: string
  full_name: string | null
  role: string
  is_active: boolean
  totp_enabled: boolean
  created_at: string
}

export interface StaffCredential {
  id: string
  firm_id: string
  user_id: string
  credential_type: string
  credential_number: string | null
  state: string | null
  issued_at: string | null
  expires_at: string | null
  notes: string | null
  is_expiring_soon: boolean
  created_at: string
  updated_at: string
}

export interface CPERecord {
  id: string
  firm_id: string
  user_id: string
  reporting_period_start: string
  reporting_period_end: string
  hours_required: number
  hours_completed: number
  hours_remaining: number
  status: string
  deadline: string | null
  notes: string | null
  created_at: string
  updated_at: string
}

export interface PaginatedStaffCredentials {
  items: StaffCredential[]
  total: number
  limit: number
  offset: number
}

export interface PaginatedCPERecords {
  items: CPERecord[]
  total: number
  limit: number
  offset: number
}

export const staffApi = {
  listStaff: async (): Promise<StaffMember[]> => {
    const { data } = await api.get('/users', { params: { limit: 100, offset: 0 } })
    return Array.isArray(data) ? data : (data.items ?? [])
  },

  listCredentials: async (params?: { skip?: number; limit?: number }): Promise<PaginatedStaffCredentials> => {
    const { data } = await api.get('/api/v1/staff-credentials', {
      params: { skip: params?.skip ?? 0, limit: params?.limit ?? 50 },
    })
    return data
  },

  listCredentialsByUser: async (userId: string): Promise<StaffCredential[]> => {
    const { data } = await api.get(`/api/v1/staff-credentials/user/${userId}`)
    return Array.isArray(data) ? data : (data.items ?? [])
  },

  createCredential: async (data: object): Promise<StaffCredential> => {
    const { data: result } = await api.post('/api/v1/staff-credentials', data)
    return result
  },

  updateCredential: async (id: string, data: object): Promise<StaffCredential> => {
    const { data: result } = await api.patch(`/api/v1/staff-credentials/${id}`, data)
    return result
  },

  deleteCredential: async (id: string): Promise<void> => {
    await api.delete(`/api/v1/staff-credentials/${id}`)
  },

  listCPERecords: async (params?: { skip?: number; limit?: number }): Promise<PaginatedCPERecords> => {
    const { data } = await api.get('/api/v1/cpe-records', {
      params: { skip: params?.skip ?? 0, limit: params?.limit ?? 50 },
    })
    return data
  },

  listCPERecordsByUser: async (userId: string): Promise<CPERecord[]> => {
    const { data } = await api.get(`/api/v1/cpe-records/user/${userId}`)
    return Array.isArray(data) ? data : (data.items ?? [])
  },

  createCPERecord: async (data: object): Promise<CPERecord> => {
    const { data: result } = await api.post('/api/v1/cpe-records', data)
    return result
  },

  updateCPERecord: async (id: string, data: object): Promise<CPERecord> => {
    const { data: result } = await api.patch(`/api/v1/cpe-records/${id}`, data)
    return result
  },

  deleteCPERecord: async (id: string): Promise<void> => {
    await api.delete(`/api/v1/cpe-records/${id}`)
  },

  updateUser: async (
    userId: string,
    data: { role?: string; is_active?: boolean; full_name?: string }
  ): Promise<StaffMember> => {
    const { data: result } = await api.patch(`/users/${userId}`, data)
    return result
  },

  deleteUser: async (userId: string): Promise<void> => {
    await api.delete(`/users/${userId}`)
  },

  inviteStaff: async (data: {
    email: string
    full_name?: string
    role: string
    password: string
  }): Promise<StaffMember> => {
    const { data: result } = await api.post('/users/', data)
    return result
  },

  listBookableStaff: async (): Promise<{ id: string; full_name: string | null }[]> => {
    const { data } = await api.get('/users/bookable-staff')
    return data
  },
}
