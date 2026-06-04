// frontend/src/components/engagements/EngagementTable.tsx
'use client'

import { useRouter } from 'next/navigation'
import { type Engagement } from '@/lib/api'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { BookmarkPlus } from 'lucide-react'

function formatTypeDisplay(engagementType: string | null | undefined): string {
  if (!engagementType) return '—'
  const map: Record<string, string> = {
    tax_return_1040: 'Tax Return — 1040',
    tax_return_1120: 'Tax Return — 1120',
    tax_return_1120s: 'Tax Return — 1120-S',
    tax_return_1065: 'Tax Return — 1065',
    tax_return_1041: 'Tax Return — 1041',
    tax_return_706: 'Tax Return — 706',
    amended_return_1040x: 'Amended — 1040-X',
    extension_4868: 'Extension — 4868',
    extension_7004: 'Extension — 7004',
    extension_8868: 'Extension — 8868',
    payroll_tax_941: 'Payroll — 941',
    tax_planning_advisory: 'Advisory',
    bookkeeping_monthly: 'Bookkeeping — Monthly',
    bookkeeping_quarterly: 'Bookkeeping — Quarterly',
    audit_representation: 'Audit',
    other_advisory: 'Advisory',
    custom: 'Other',
  }
  return map[engagementType] ?? engagementType.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

function formatDeadline(eng: Engagement): string {
  const raw = eng.extendedDeadline ?? eng.filingDeadline ?? eng.endDate
  if (!raw) return '—'
  try {
    return new Date(raw).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    })
  } catch {
    return raw
  }
}

interface EngagementTableProps {
  engagements: Engagement[]
  clientMap?: Record<string, string>
  lookupsLoading?: boolean
  selectedIds?: Set<string>
  onSelect?: (id: string, checked: boolean) => void
  onSelectAll?: (checked: boolean) => void
  onSaveAsTemplate?: (engagement: Engagement) => void
}

export function EngagementTable({
  engagements,
  clientMap = {},
  lookupsLoading = false,
  selectedIds,
  onSelect,
  onSelectAll,
  onSaveAsTemplate,
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
            {['Engagement', 'Client', 'Type', 'Due Date', 'Status', ''].map((col) => (
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
                    {formatTypeDisplay(eng.engagementType)}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className="text-[12px] text-[#374151] dark:text-[#9CA3AF]">
                    {formatDeadline(eng)}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <StatusBadge variant={eng.status as Parameters<typeof StatusBadge>[0]['variant']} />
                </td>
                {onSaveAsTemplate && (
                  <td className="px-3 py-3" onClick={(e) => e.stopPropagation()}>
                    <button
                      onClick={() => onSaveAsTemplate(eng)}
                      title="Save as template"
                      className="p-1.5 rounded text-[#9CA3AF] hover:text-brand-light hover:bg-[#F3F4F6] dark:hover:bg-[#333] transition-colors opacity-0 group-hover:opacity-100"
                    >
                      <BookmarkPlus className="h-3.5 w-3.5" />
                    </button>
                  </td>
                )}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
