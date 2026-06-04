// frontend/src/components/dashboard/StatCard.tsx

import { cn } from '@/lib/utils'

interface StatCardProps {
  label: string
  value: number
  accent?: 'default' | 'warning' | 'danger'
}

export function StatCard({ label, value, accent = 'default' }: StatCardProps) {
  return (
    <div className="bg-surface-card dark:bg-dark-card rounded-card p-4 flex flex-col gap-1">
      <span className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em]">
        {label}
      </span>
      <span
        className={cn(
          'text-2xl font-medium',
          accent === 'danger' && 'text-status-red-text',
          accent === 'warning' && 'text-status-amber-text',
          accent === 'default' && 'text-brand dark:text-[#EDEEF0]'
        )}
      >
        {value}
      </span>
    </div>
  )
}
