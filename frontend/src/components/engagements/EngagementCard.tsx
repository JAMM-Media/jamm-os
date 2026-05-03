// frontend/src/components/engagements/EngagementCard.tsx
'use client'

import { useRouter } from 'next/navigation'
import { type Engagement } from '@/lib/api'
import { StatusBadge } from '@/components/ui/StatusBadge'

interface EngagementCardProps {
  engagement: Engagement
  clientMap?: Record<string, string>
  lookupsLoading?: boolean
}

export function EngagementCard({ engagement, clientMap = {}, lookupsLoading = false }: EngagementCardProps) {
  const router = useRouter()

  return (
    <div
      onClick={() => router.push(`/engagements/${engagement.id}`)}
      className="bg-surface-card dark:bg-dark-card rounded-card p-[13px] cursor-pointer hover:brightness-95 dark:hover:brightness-110 transition-all"
    >
      <div className="flex items-start justify-between mb-1">
        <span className="text-[12px] font-medium text-brand dark:text-[#EDEEF0] leading-tight pr-2">
          {engagement.name}
        </span>
        <StatusBadge variant={engagement.status as Parameters<typeof StatusBadge>[0]['variant']} />
      </div>
      <div className="text-[11px] text-[#6B7280] mb-1 truncate">
        {lookupsLoading ? (
          <div className="h-2 w-[60px] bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded inline-block" />
        ) : (
          clientMap[engagement.clientId] ?? (engagement.clientId ? <span className="text-[#6B7280]">Unknown</span> : '')
        )}
      </div>
      <div className="flex items-center justify-between mt-1">
        <span className="text-[11px] text-[#6B7280]">
          {engagement.engagementType ?? ''}
        </span>
        {engagement.endDate && (
          <span className="text-[11px] text-[#6B7280]">
            Due {engagement.endDate}
          </span>
        )}
      </div>
    </div>
  )
}
