// frontend/src/components/dashboard/PriorityItem.tsx
'use client'

import { useRouter } from 'next/navigation'
import { DashboardItem } from '@/lib/api/dashboard'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { CheckSquare, Briefcase } from 'lucide-react'
import { cn } from '@/lib/utils'

interface PriorityItemProps {
  item: DashboardItem
  index: number
  total: number
}

export function PriorityItem({ item, index, total }: PriorityItemProps) {
  const router = useRouter()

  return (
    <div
      onClick={() => router.push(item.href)}
      className={cn(
        'flex items-center gap-3 px-4 py-3 cursor-pointer transition-colors',
        'bg-surface-page dark:bg-dark-page',
        'hover:bg-[#DDDFE3] dark:hover:bg-[#323232]',
        index !== total - 1
          ? 'border-b border-[0.5px] border-[#D5D8DE] dark:border-dark-card'
          : ''
      )}
    >
      {/* Type icon */}
      <div className="flex-shrink-0 text-[#6B7280]">
        {item.type === 'task' ? (
          <CheckSquare className="h-4 w-4" />
        ) : (
          <Briefcase className="h-4 w-4" />
        )}
      </div>

      {/* Title + client */}
      <div className="flex-1 min-w-0">
        <p className="text-[12px] font-medium text-brand dark:text-[#EDEEF0] truncate">
          {item.title}
        </p>
        <p className="text-[11px] text-[#6B7280]">
          {item.clientName} · {item.assignedTo}
        </p>
      </div>

      {/* Due date */}
      <span className="text-[11px] text-[#6B7280] flex-shrink-0 hidden sm:block">
        Due {item.dueDate}
      </span>

      {/* Status badge */}
      <div className="flex-shrink-0">
        <StatusBadge variant={item.status as any} />
      </div>
    </div>
  )
}
