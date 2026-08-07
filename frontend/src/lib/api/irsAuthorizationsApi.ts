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

/**
 * The resolved state of one form type, computed by
 * crud_auth.resolve_authorization_state on the backend.
 *
 * Not the same vocabulary as IrsAuthorizationRecord['status']: 'lapsed' is
 * the reported form of a record whose status is 'expired', and 'superseded'
 * has no resolved state at all because resolution reads the replacement
 * instead of the retired row.
 */
export type IrsAuthResolvedState =
  | 'active'
  | 'pending'
  | 'lapsed'
  | 'revoked'
  | 'none'

export interface IrsAuthStatusResponse {
  client_id: string
  /**
   * The resolved record for this form type, whatever its status. This used
   * to carry an active record or nothing, which is why the badge could not
   * tell a lapsed authorization apart from one that never existed.
   */
  '8821': IrsAuthorizationRecord | null
  '2848': IrsAuthorizationRecord | null
  has_active_8821: boolean
  has_active_2848: boolean
  state_8821: IrsAuthResolvedState
  state_2848: IrsAuthResolvedState
  /** ISO date, or null. Null is normal: an 8821 often has no end date. */
  expires_on_8821: string | null
  expires_on_2848: string | null
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
