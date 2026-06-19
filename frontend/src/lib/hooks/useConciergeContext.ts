// path: frontend/src/lib/hooks/useConciergeContext.ts
'use client'

import { useState, useEffect, useRef } from 'react'
import { usePathname } from 'next/navigation'
import api from '@/lib/api'

export interface ConciergeEntitySummary {
  entity_type: string
  entity_id: string
  entity_name: string
  summary: Record<string, unknown>
}

export interface ConciergeUIContext {
  page: string
  entity_type: string | null
  entity_id: string | null
  entity_name: string | null
  summary: Record<string, unknown> | null
  ready: boolean
}

const PAGE_LABELS: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/clients': 'Clients',
  '/engagements': 'Engagements',
  '/tasks': 'Tasks',
  '/documents': 'Documents',
  '/billing': 'Billing',
  '/settings': 'Settings',
  '/firm-chat': 'Firm Chat',
}

// UUID pattern for detecting entity IDs in routes
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

const _cache: Map<string, { data: ConciergeEntitySummary; ts: number }> = new Map()
const CACHE_TTL = 60_000 // 60 seconds

function parseEntityFromPath(pathname: string): { entity_type: string; entity_id: string } | null {
  // /clients/:id  or  /clients/:id/...
  const clientMatch = pathname.match(/^\/clients\/([^/]+)/)
  if (clientMatch && UUID_RE.test(clientMatch[1])) {
    return { entity_type: 'client', entity_id: clientMatch[1] }
  }
  // /engagements/:id  or  /engagements/:id/...
  const engMatch = pathname.match(/^\/engagements\/([^/]+)/)
  if (engMatch && UUID_RE.test(engMatch[1])) {
    return { entity_type: 'engagement', entity_id: engMatch[1] }
  }
  return null
}

export function useConciergeContext(): ConciergeUIContext {
  const pathname = usePathname()
  const [entityData, setEntityData] = useState<ConciergeEntitySummary | null>(null)
  const [ready, setReady] = useState(true)
  const fetchingRef = useRef<string | null>(null)

  const page =
    Object.entries(PAGE_LABELS).find(([k]) => pathname.startsWith(k))?.[1] ?? 'JAMM PX'

  const parsed = parseEntityFromPath(pathname)
  const cacheKey = parsed ? `${parsed.entity_type}:${parsed.entity_id}` : null

  useEffect(() => {
    if (!cacheKey || !parsed) {
      setEntityData(null)
      setReady(true)
      return
    }

    // Check cache first
    const cached = _cache.get(cacheKey)
    if (cached && Date.now() - cached.ts < CACHE_TTL) {
      setEntityData(cached.data)
      setReady(true)
      return
    }

    // Avoid duplicate in-flight requests
    if (fetchingRef.current === cacheKey) return
    fetchingRef.current = cacheKey
    setReady(false)

    api
      .get<ConciergeEntitySummary>(
        `/concierge/entity-preview/${parsed.entity_type}/${parsed.entity_id}`
      )
      .then((res) => {
        _cache.set(cacheKey, { data: res.data, ts: Date.now() })
        setEntityData(res.data)
      })
      .catch(() => {
        setEntityData(null)
      })
      .finally(() => {
        if (fetchingRef.current === cacheKey) fetchingRef.current = null
        setReady(true)
      })
  }, [cacheKey])

  return {
    page,
    entity_type: entityData?.entity_type ?? null,
    entity_id: entityData?.entity_id ?? null,
    entity_name: entityData?.entity_name ?? null,
    summary: entityData?.summary ?? null,
    ready,
  }
}
