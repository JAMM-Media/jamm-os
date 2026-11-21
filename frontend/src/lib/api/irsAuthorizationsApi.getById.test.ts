// path: frontend/src/lib/api/irsAuthorizationsApi.getById.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/lib/api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))

import api from '@/lib/api'
import { irsAuthorizationsApi } from './irsAuthorizationsApi'

const getMock = api.get as unknown as ReturnType<typeof vi.fn>

beforeEach(() => {
  getMock.mockReset()
})

describe('irsAuthorizationsApi.getById', () => {
  it('uses the same /irs-authorizations prefix as the other calls, with no /api/v1, and returns the data', async () => {
    getMock.mockResolvedValue({ data: { id: 'a-1', client_id: 'c-9' } })
    const record = await irsAuthorizationsApi.getById('a-1')
    expect(getMock).toHaveBeenCalledWith('/irs-authorizations/a-1')
    expect(record.client_id).toBe('c-9')
  })
})
