// path: frontend/src/lib/irsAuthorizationDestination.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/lib/api/irsAuthorizationsApi', () => ({
  irsAuthorizationsApi: { getById: vi.fn() },
}))

import { irsAuthorizationsApi } from '@/lib/api/irsAuthorizationsApi'
import { irsClientPath, resolveIrsAuthorizationPath } from './irsAuthorizationDestination'

const getById = irsAuthorizationsApi.getById as unknown as ReturnType<typeof vi.fn>

beforeEach(() => {
  getById.mockReset()
})

describe('irsClientPath', () => {
  it('opens the client page on the IRS Authorizations tab', () => {
    expect(irsClientPath('c-9')).toBe('/clients/c-9?tab=irs-auth')
  })
})

describe('resolveIrsAuthorizationPath', () => {
  it('looks the authorization up by id once and returns the exact client URL', async () => {
    getById.mockResolvedValue({ id: 'a-1', client_id: 'c-9' })
    await expect(resolveIrsAuthorizationPath('a-1')).resolves.toBe('/clients/c-9?tab=irs-auth')
    expect(getById).toHaveBeenCalledTimes(1)
    expect(getById).toHaveBeenCalledWith('a-1')
  })

  it('rejects when the lookup fails', async () => {
    getById.mockRejectedValue({ response: { status: 404 } })
    await expect(resolveIrsAuthorizationPath('a-1')).rejects.toEqual({ response: { status: 404 } })
  })

  it('rejects when the record has no client id', async () => {
    getById.mockResolvedValue({ id: 'a-1', client_id: '' })
    await expect(resolveIrsAuthorizationPath('a-1')).rejects.toThrow('no client id')
    getById.mockResolvedValue(undefined)
    await expect(resolveIrsAuthorizationPath('a-1')).rejects.toThrow('no client id')
  })
})
