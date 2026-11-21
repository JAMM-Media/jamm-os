// path: frontend/src/lib/irsAuthorizationDestination.ts
import { irsAuthorizationsApi } from '@/lib/api/irsAuthorizationsApi'

// Where an IRS authorization notification opens: the owning client, on the
// IRS Authorizations tab.
export function irsClientPath(clientId: string): string {
  return `/clients/${clientId}?tab=irs-auth`
}

// Resolves that path from an authorization id. Rejects when the lookup fails or
// the record carries no client id. The caller decides what the user sees.
export async function resolveIrsAuthorizationPath(authorizationId: string): Promise<string> {
  const authorization = await irsAuthorizationsApi.getById(authorizationId)
  if (!authorization || !authorization.client_id) {
    throw new Error('IRS authorization has no client id')
  }
  return irsClientPath(authorization.client_id)
}
