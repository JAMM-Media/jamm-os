// frontend/src/components/engagements/EngagementTable.tsx
'use client'

import { useRouter } from 'next/navigation'
import { type Engagement } from '@/lib/api'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { formatEngagementType } from '@/lib/utils'

interface EngagementTableProps {
  engagements: Engagement[]
  clientMap?: Record<string, string>
  lookupsLoading?: boolean
  selectedIds?: Set<string>
  onSelect?: (id: string, checked: boolean) => void
  onSelectAll?: (checked: boolean) => void
}

export function EngagementTable({
  engagements,
  clientMap = {},
  lookupsLoading = false,
  selectedIds,
  onSelect,
  onSelectAll,
}: EngagementTableProps) {
  const router = useRouter()
  const hasSelection = selectedIds !== undefined

  const allSelected = hasSelection && engagements.length > 0 && engagements.every((e) => selectedIds.has(e.id))
  const someSelected = hasSelection && engagements.some((e) => selectedIds.has(e.id))

  return (
    <div className="rounded-modal border border-[0.5px] border-surface-border dark:border-dark-border overflow-hidden">
      <table className="w-full border-collapse">
        <thead>
          <tr className="bg-surface-card dark:bg-[#252525]">
            {hasSelection && (
              <th className="px-3 py-2.5 w-8">
                <input
                  type="checkbox"
                  checked={allSelected}
                  ref={(el) => { if (el) el.indeterminate = someSelected && !allSelected }}
                  onChange={(e) => onSelectAll?.(e.target.checked)}
                  className="rounded border-[#D5D8DE] accent-brand"
                />
              </th>
            )}
            {['Engagement', 'Client', 'Type', 'Due Date', 'Status'].map((col) => (
              <th
                key={col}
                className="px-4 py-2.5 text-left text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] whitespace-nowrap"
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {engagements.map((eng, i) => {
            const isSelected = hasSelection && selectedIds.has(eng.id)
            return (
              <tr
                key={eng.id}
                onClick={() => router.push(`/engagements/${eng.id}`)}
                className={[
                  'group cursor-pointer transition-colors',
                  isSelected ? 'bg-[#EEF2FF] dark:bg-[#1e2a40]' : 'bg-surface-page dark:bg-dark-page',
                  'hover:bg-[#DDDFE3] dark:hover:bg-[#323232]',
                  i !== engagements.length - 1
                    ? 'border-b border-[0.5px] border-[#D5D8DE] dark:border-dark-card'
                    : '',
                ].join(' ')}
              >
                {hasSelection && (
                  <td className="px-3 py-3" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={(e) => onSelect?.(eng.id, e.target.checked)}
                      className="rounded border-[#D5D8DE] accent-brand"
                    />
                  </td>
                )}
                <td className="px-4 py-3">
                  <span className="text-[12px] font-medium text-brand dark:text-[#EDEEF0]">
                    {eng.name}
                  </span>
                </td>
                <td className="px-4 py-3">
                  {lookupsLoading ? (
                    <div className="h-2 w-[60px] bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                  ) : (
                    <span
                      onClick={(e) => { e.stopPropagation(); router.push(`/clients/${eng.clientId}`) }}
                      className="text-[12px] text-brand-light hover:underline cursor-pointer"
                    >
                      {clientMap[eng.clientId] ?? (eng.clientId ? <span className="text-[#6B7280]">Unknown</span> : '—')}
                    </span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <span className="text-[12px] text-[#374151] dark:text-[#9CA3AF]">
                    {formatEngagementType(eng.engagementType ?? '')}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className="text-[12px] text-[#374151] dark:text-[#9CA3AF]">
                    {eng.endDate ?? '—'}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <StatusBadge variant={eng.status as Parameters<typeof StatusBadge>[0]['variant']} />
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
