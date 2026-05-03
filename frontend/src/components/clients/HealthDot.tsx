// frontend/src/components/clients/HealthDot.tsx
'use client'

import { useQuery } from '@tanstack/react-query'
import { clientsApi } from '@/lib/api/clients'
import type { ClientHealth } from '@/lib/api/clients'

const STATUS_CONFIG = {
  healthy: { color: '#10B981', label: 'Healthy' },
  needs_attention: { color: '#F59E0B', label: 'Needs Attention' },
  at_risk: { color: '#E24B4A', label: 'At Risk' },
} as const

interface HealthDotProps {
  clientId: string
  showLabel?: boolean
}

export function HealthDot({ clientId, showLabel = false }: HealthDotProps) {
  const { data, isLoading, isError } = useQuery<ClientHealth>({
    queryKey: ['client-health', clientId],
    queryFn: () => clientsApi.getHealth(clientId),
    staleTime: 10 * 60 * 1000,
    refetchOnWindowFocus: false,
  })

  if (isError) return null

  const config = data ? STATUS_CONFIG[data.status as keyof typeof STATUS_CONFIG] ?? null : null
  const color = isLoading || !config ? '#C8CDD6' : config.color
  const tooltip =
    isLoading || !data
      ? undefined
      : data.reasons.length === 0
      ? 'All good'
      : data.reasons.join('\n')

  const dot = (
    <span
      style={{
        display: 'inline-block',
        width: 8,
        height: 8,
        borderRadius: '50%',
        backgroundColor: color,
        flexShrink: 0,
      }}
    />
  )

  if (!showLabel) {
    return (
      <span title={tooltip} style={{ display: 'inline-flex', alignItems: 'center' }}>
        {dot}
      </span>
    )
  }

  return (
    <span
      title={tooltip}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        fontSize: 12,
        color: isLoading || !config ? '#C8CDD6' : config.color,
      }}
    >
      {dot}
      {!isLoading && config && config.label}
    </span>
  )
}
