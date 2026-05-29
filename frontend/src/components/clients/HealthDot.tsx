// frontend/src/components/clients/HealthDot.tsx
'use client'

import { useQuery } from '@tanstack/react-query'
import { clientsApi } from '@/lib/api/clients'
import type { ClientHealth } from '@/lib/api/clients'
import {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
  TooltipProvider,
} from '@/components/ui/tooltip'

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

  const config = data
    ? STATUS_CONFIG[data.status as keyof typeof STATUS_CONFIG] ?? null
    : null
  const color = isLoading || !config ? '#C8CDD6' : config.color

  const hasReasons = data && data.reasons.length > 0

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

  // No reasons — healthy or still loading — just render the dot/label with no tooltip
  if (!hasReasons) {
    if (showLabel) {
      return <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, color: isLoading || !config ? '#C8CDD6' : config.color }}>{dot}{!isLoading && config && config.label}</span>
    }
    return <span style={{ display: 'inline-flex', alignItems: 'center' }}>{dot}</span>
  }

  // Has reasons — wrap in tooltip showing each reason on its own line
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger>{showLabel ? (<span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, color: isLoading || !config ? '#C8CDD6' : config.color, cursor: 'default' }}>{dot}{!isLoading && config && config.label}</span>) : (<span style={{ display: 'inline-flex', alignItems: 'center' }}>{dot}</span>)}</TooltipTrigger>
        <TooltipContent
          side="right"
          className="max-w-[240px]"
        >
          <div className="flex flex-col gap-1">
            {data.reasons.map((reason, i) => (
              <div key={i} className="flex items-start gap-1.5">
                <span
                  style={{
                    width: 5,
                    height: 5,
                    borderRadius: '50%',
                    backgroundColor: color,
                    flexShrink: 0,
                    marginTop: 5,
                  }}
                />
                <span className="text-[11px] leading-tight">{reason}</span>
              </div>
            ))}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
