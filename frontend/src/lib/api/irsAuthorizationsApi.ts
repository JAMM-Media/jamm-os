// frontend/src/lib/api/irsAuthorizationsApi.ts
import api from '@/lib/api'

export interface IrsAuthorizationRecord {
  id: string
  firm_id: string
  client_id: string
  form_type: '8821' | '2848'
  status: 'pending_signature' | 'active' | 'expired' | 'revoked' | 'superseded'
  tax_years: number[]
  valid_from: string | null
  valid_until: string | null
  created_at: string
  updated_at: string
}

export interface IrsAuthStatusResponse {
  client_id: string
  '8821': IrsAuthorizationRecord | null
  '2848': IrsAuthorizationRecord | null
  has_active_8821: boolean
  has_active_2848: boolean
}

export interface IrsAuthSendRequest {
  client_id: string
  form_type: '8821' | '2848'
  tax_years: number[]
  valid_from?: string
  valid_until?: string
}

export const irsAuthorizationsApi = {
  checkClientStatus: (clientId: string) =>
    api.get(`/irs-authorizations/check/${clientId}`),

  listForClient: (clientId: string) =>
    api.get(`/irs-authorizations/`, {
      params: { client_id: clientId },
    }),

  send: (payload: IrsAuthSendRequest) =>
    api.post(`/irs-authorizations/send`, payload),
}
