// frontend/src/components/tasks/TaskCard.tsx
'use client'

import { useRouter } from 'next/navigation'
import { type Task } from '@/lib/api'
import { StatusBadge } from '@/components/ui/StatusBadge'

type BadgeVariant = Parameters<typeof StatusBadge>[0]['variant']

interface TaskCardProps {
  task: Task
  clientMap?: Record<string, string>
  engagementMap?: Record<string, string>
  lookupsLoading?: boolean
}

export function TaskCard({ task, clientMap = {}, engagementMap = {}, lookupsLoading = false }: TaskCardProps) {
  const router = useRouter()

  const clientName = clientMap[task.clientId]
  const engagementName = engagementMap[task.engagementId]

  return (
    <div
      onClick={() => router.push(`/tasks/${task.id}`)}
      className="bg-surface-card dark:bg-dark-card rounded-card p-[13px] cursor-pointer hover:brightness-95 dark:hover:brightness-110 transition-all"
    >
      <div className="flex items-start justify-between mb-1">
        <span className="text-[12px] font-medium text-brand dark:text-[#EDEEF0] leading-tight pr-2">
          {task.title}
        </span>
        <StatusBadge variant={task.status as BadgeVariant} />
      </div>
      <div className="text-[11px] text-[#6B7280] mb-2 truncate">
        {lookupsLoading ? (
          <div className="h-2 w-[60px] bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded inline-block" />
        ) : (
          <>{clientName ?? (task.clientId ? <span className="text-[#6B7280]">Unknown</span> : '—')}{engagementName ? ` · ${engagementName}` : ''}</>
        )}
      </div>
      <div className="flex items-center justify-between">
        <span className="text-[11px] text-[#6B7280]">
          {task.assignedTo ?? '—'}
        </span>
        <span className="text-[11px] text-[#6B7280]">
          Due {task.dueDate ?? '—'}
        </span>
      </div>
    </div>
  )
}
