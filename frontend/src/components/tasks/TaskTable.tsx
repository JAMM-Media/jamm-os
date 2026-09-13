// frontend/src/components/tasks/TaskTable.tsx
'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { toast } from 'sonner'
import { type Task, tasksApi } from '@/lib/api'
import { StatusBadge } from '@/components/ui/StatusBadge'

type BadgeVariant = Parameters<typeof StatusBadge>[0]['variant']

interface TaskTableProps {
  tasks: Task[]
  clientMap?: Record<string, string>
  engagementMap?: Record<string, string>
  userMap?: Record<string, string>
  lookupsLoading?: boolean
  selectedIds?: Set<string>
  onSelect?: (id: string, checked: boolean) => void
  onSelectAll?: (checked: boolean) => void
  onStatusChange?: (id: string, status: string) => void
}

export function TaskTable({
  tasks,
  clientMap = {},
  engagementMap = {},
  userMap = {},
  lookupsLoading = false,
  selectedIds,
  onSelect,
  onSelectAll,
  onStatusChange,
}: TaskTableProps) {
  const router = useRouter()
  const hasSelection = selectedIds !== undefined
  const [loadingId, setLoadingId] = useState<string | null>(null)

  async function handleComplete(e: React.MouseEvent, taskId: string) {
    e.stopPropagation()
    setLoadingId(taskId)
    try {
      await tasksApi.update(taskId, { status: 'done' })
      onStatusChange?.(taskId, 'done')
    } catch {
      toast.error('Could not update task -- please try again')
    } finally {
      setLoadingId(null)
    }
  }

  const allSelected = hasSelection && tasks.length > 0 && tasks.every((t) => selectedIds.has(t.id))
  const someSelected = hasSelection && tasks.some((t) => selectedIds.has(t.id))

  return (
    <div className="rounded-modal border border-[0.5px] border-surface-border dark:border-dark-border overflow-auto">
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
            {['Task', 'Client', 'Engagement', 'Assigned To', 'Due Date', 'Status', ''].map((col) => (
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
          {tasks.map((task, i) => {
            const isSelected = hasSelection && selectedIds.has(task.id)
            return (
              <tr
                key={task.id}
                onClick={() => router.push(`/tasks/${task.id}`)}
                className={[
                  'group cursor-pointer transition-colors',
                  isSelected ? 'bg-[#EEF2FF] dark:bg-[#1e2a40]' : 'bg-surface-page dark:bg-dark-page',
                  'hover:bg-[#DDDFE3] dark:hover:bg-[#323232]',
                  i !== tasks.length - 1
                    ? 'border-b border-[0.5px] border-[#D5D8DE] dark:border-dark-card'
                    : '',
                ].join(' ')}
              >
                {hasSelection && (
                  <td className="px-3 py-3" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={(e) => onSelect?.(task.id, e.target.checked)}
                      className="rounded border-[#D5D8DE] accent-brand"
                    />
                  </td>
                )}
                <td className="px-4 py-3">
                  <span className="text-[12px] font-medium text-brand dark:text-[#EDEEF0]">
                    {task.title}
                  </span>
                </td>
                <td className="px-4 py-3">
                  {lookupsLoading ? (
                    <div className="h-2 w-[60px] bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                  ) : (
                    <span
                      onClick={(e) => { e.stopPropagation(); router.push(`/clients/${task.clientId}`) }}
                      className="text-[12px] text-brand-light hover:underline cursor-pointer"
                    >
                      {clientMap[task.clientId] ?? (task.clientId ? <span className="text-[#6B7280]">Unknown</span> : '—')}
                    </span>
                  )}
                </td>
                <td className="px-4 py-3">
                  {lookupsLoading ? (
                    <div className="h-2 w-[60px] bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                  ) : (
                    <span
                      onClick={(e) => { e.stopPropagation(); router.push(`/engagements/${task.engagementId}`) }}
                      className="text-[12px] text-brand-light hover:underline cursor-pointer"
                    >
                      {engagementMap[task.engagementId] ?? (task.engagementId ? <span className="text-[#6B7280]">Unknown</span> : '—')}
                    </span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <span className="text-[12px] text-[#374151] dark:text-[#9CA3AF]">
                    {task.assignedToName ?? (task.assignedTo ? (userMap[task.assignedTo] ?? task.assignedTo) : '—')}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className="text-[12px] text-[#374151] dark:text-[#9CA3AF]">
                    {task.dueDate ?? '—'}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <StatusBadge variant={task.status as BadgeVariant} />
                </td>
                <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                  {task.status !== 'done' && (
                    <button
                      disabled={loadingId === task.id}
                      onClick={(e) => handleComplete(e, task.id)}
                      className="opacity-0 group-hover:opacity-100 transition-opacity h-7 px-2.5 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border text-[11px] text-[#374151] dark:text-[#9CA3AF] hover:border-brand hover:text-brand whitespace-nowrap disabled:opacity-50"
                    >
                      {loadingId === task.id ? 'Saving...' : 'Mark Complete'}
                    </button>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
