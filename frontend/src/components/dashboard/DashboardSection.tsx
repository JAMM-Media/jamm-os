// frontend/src/components/dashboard/DashboardSection.tsx

import { DashboardItem } from '@/lib/mock/dashboard'
import { PriorityItem } from './PriorityItem'

interface DashboardSectionProps {
  title: string
  items: DashboardItem[]
  emptyMessage: string
}

export function DashboardSection({
  title,
  items,
  emptyMessage,
}: DashboardSectionProps) {
  return (
    <div>
      <h2 className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] mb-2">
        {title}
      </h2>
      <div className="rounded-modal border border-[0.5px] border-surface-border dark:border-dark-border overflow-hidden">
        {items.length === 0 ? (
          <div className="px-4 py-6 text-center">
            <p className="text-[12px] text-[#6B7280]">{emptyMessage}</p>
          </div>
        ) : (
          items.map((item, i) => (
            <PriorityItem
              key={item.id}
              item={item}
              index={i}
              total={items.length}
            />
          ))
        )}
      </div>
    </div>
  )
}
