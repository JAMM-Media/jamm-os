// frontend/src/lib/api/settingsApi.ts
import api from '@/lib/api'

export interface FirmDetails {
  id: string
  name: string
  slug: string
  subscription_tier: string
  is_active: boolean
  staff_auth_policy: string
  settings: Record<string, unknown> | null
  feature_flags: Record<string, boolean> | null
  created_at: string
  updated_at: string
}

export type StaffAuthPolicy = 'either' | 'password_only' | 'magic_link_only'

export interface StaffMember {
  id: string
  full_name: string | null
  email: string
  role: string
  is_active: boolean
  firm_id: string
  totp_enabled: boolean
  created_at: string
}

export const settingsApi = {
  getMyFirm: () =>
    api.get('/users/firm'),

  listTeam: () =>
    api.get('/users', { params: { limit: 100, offset: 0 } }),

  updateStaffAuthPolicy: (policy: StaffAuthPolicy) =>
    api.patch('/settings/security/staff-auth-policy', { staff_auth_policy: policy }),

  updateFirmSettings: (settings: Record<string, unknown>) =>
    api.patch('/users/firm/settings', settings),
}
