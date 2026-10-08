// frontend/src/lib/firmCache.ts
import type { QueryClient } from '@tanstack/react-query'

export const FIRM_QUERY_KEY = ['firm-settings-sidebar'] as const

export function refreshFirmCache(qc: Pick<QueryClient, 'invalidateQueries'>): Promise<void> { return qc.invalidateQueries({ queryKey: FIRM_QUERY_KEY }) }
