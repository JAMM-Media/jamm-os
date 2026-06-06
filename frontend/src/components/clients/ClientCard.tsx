// frontend/src/components/clients/ClientCard.tsx
'use client'

import { useRouter } from 'next/navigation'
import { type Client } from '@/lib/api'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { IrsAuthBadge } from '@/components/clients/IrsAuthBadge'
import { HealthDot } from '@/components/clients/HealthDot'
import { formatEntityType, formatEntitySubtype } from '@/lib/utils'

interface ClientCardProps {
  client: Client
}

export function ClientCard({ client }: ClientCardProps) {
  const router = useRouter()

  return (
    <div
      onClick={() => router.push(`/clients/${client.id}`)}
      className="bg-surface-card dark:bg-dark-card rounded-card p-[13px_13px_12px] cursor-pointer hover:brightness-95 dark:hover:brightness-110 transition-all"
    >
      <div className="flex items-start justify-between mb-1">
        <div className="flex items-center gap-2">
          <HealthDot clientId={client.id} />
          <span className="text-[12px] font-medium text-brand dark:text-[#EDEEF0] leading-tight">
            {client.name}
          </span>
        </div>
        <span className="text-[10px] text-[#6B7280] ml-2 flex-shrink-0">
          {formatEntityType(client.entityType)}{client.entitySubtype ? ` -- ${formatEntitySubtype(client.entitySubtype)}` : ''}
        </span>
      </div>
      <div className="text-[11px] text-[#6B7280] mb-2">
        {client.email ?? ''}
      </div>
      <div className="flex flex-wrap items-center gap-1">
        <StatusBadge variant={client.isActive ? 'active' : 'inactive'} />
        <IrsAuthBadge
          clientId={client.id}
          onClick={() => router.push(`/clients/${client.id}?tab=irs-auth`)}
        />
      </div>
    </div>
  )
}
