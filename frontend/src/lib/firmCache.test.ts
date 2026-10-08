// frontend/src/lib/firmCache.test.ts
import { describe, it, expect, vi } from 'vitest'
import { readFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'
import { FIRM_QUERY_KEY, refreshFirmCache } from './firmCache'

const cwd = process.cwd()
if (!existsSync(join(cwd, 'package.json'))) {
  throw new Error(`vitest must run from the frontend folder; cwd is ${cwd}`)
}

function readSrc(relPath: string): string {
  return readFileSync(join(cwd, 'src', relPath), 'utf8').replace(/\r\n/g, '\n')
}

const KEY_STRING = FIRM_QUERY_KEY.join('')

describe('FIRM_QUERY_KEY', () => {
  it('equals [\'firm-settings-sidebar\']', () => {
    expect(FIRM_QUERY_KEY).toEqual(['firm-settings-sidebar'])
  })
})

describe('refreshFirmCache', () => {
  it('calls invalidateQueries once with { queryKey: [\'firm-settings-sidebar\'] } and returns its promise', async () => {
    const marker = Symbol('marker')
    const mockQc = { invalidateQueries: vi.fn().mockResolvedValue(marker) }
    const result = await refreshFirmCache(mockQc)
    expect(mockQc.invalidateQueries).toHaveBeenCalledTimes(1)
    expect(mockQc.invalidateQueries).toHaveBeenCalledWith({ queryKey: ['firm-settings-sidebar'] })
    expect(result).toBe(marker)
  })

  it('passes through a rejection from invalidateQueries', async () => {
    const err = new Error('cache bust failed')
    const mockQc = { invalidateQueries: vi.fn().mockRejectedValue(err) }
    await expect(refreshFirmCache(mockQc)).rejects.toThrow('cache bust failed')
  })
})

describe('source guards', () => {
  it('Sidebar.tsx contains queryKey: [\'firm-settings-sidebar\']', () => {
    const src = readSrc('components/layout/Sidebar.tsx')
    const expected = `queryKey: ['${KEY_STRING}']`
    expect(src).toContain(expected)
  })

  it('calendar/page.tsx contains queryKey: [\'firm-settings-sidebar\']', () => {
    const src = readSrc('app/(app)/calendar/page.tsx')
    const expected = `queryKey: ['${KEY_STRING}']`
    expect(src).toContain(expected)
  })

  it('settings/page.tsx imports refreshFirmCache, calls useQueryClient, and handleSaveTimezone contains refreshFirmCache(qc)', () => {
    const src = readSrc('app/(app)/settings/page.tsx')
    expect(src).toContain("import { refreshFirmCache } from '@/lib/firmCache'")
    expect(src).toContain('useQueryClient()')
    const fnStart = src.indexOf('async function handleSaveTimezone()')
    const fnEnd = src.indexOf('\n  }', fnStart)
    expect(fnStart).toBeGreaterThan(-1)
    expect(fnEnd).toBeGreaterThan(fnStart)
    const fnBody = src.slice(fnStart, fnEnd + 4)
    const toastIdx = fnBody.indexOf("toast.success('Timezone saved')")
    const refreshIdx = fnBody.indexOf('refreshFirmCache(qc)')
    expect(toastIdx).toBeGreaterThan(-1)
    expect(refreshIdx).toBeGreaterThan(toastIdx)
  })

  it('key string used in tests 4 and 5 is derived from FIRM_QUERY_KEY (changing the constant breaks those tests)', () => {
    expect(KEY_STRING).toBe('firm-settings-sidebar')
  })
})
