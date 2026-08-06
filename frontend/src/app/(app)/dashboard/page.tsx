// path: frontend/src/app/(app)/dashboard/page.tsx
'use client'

import { useState, useMemo, useCallback, useEffect } from 'react'
import Link from 'next/link'
import { useQuery } from '@tanstack/react-query'
import { toast } from 'sonner'
import { CheckCircle, X, Minus, ChevronDown, Plus } from 'lucide-react'
import { Modal } from '@/components/ui/Modal'
import { GridLayout, useContainerWidth } from 'react-grid-layout'
import type { Layout, LayoutItem, EventCallback } from 'react-grid-layout'
import { dashboardApi } from '@/lib/api/dashboard'
import { reportsApi } from '@/lib/api/reports'
import type { DashboardWidgetInstance, DashboardTemplateItem, OverdueEngagementItem, UpcomingDeadlineItem, StaffUtilizationItem, UnsignedDocumentItem, WidgetCatalogItem } from '@/lib/api/dashboard'
import type { WIPSummary } from '@/lib/api/reports'
import api, { clientsApi } from '@/lib/api'
import { SelectInput } from '@/components/ui/SelectInput'
import { formatEngagementType } from '@/lib/utils'
import { ConciergeSpotlight } from '@/components/dashboard/ConciergeSpotlight'
import { useConfirm } from '@/lib/hooks/useConfirm'
import { useAuth } from '@/lib/hooks/useAuth'

// Size -> grid span mapping (4-column grid, rowHeight 80px).
const SIZE_TO_SPAN: Record<string, { w: number; h: number }> = {
  small:  { w: 1, h: 2 },
  medium: { w: 2, h: 5 },
  large:  { w: 4, h: 7 },
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value)
}

// ---------------------------------------------------------------------------
// Stat Card
// ---------------------------------------------------------------------------

interface MetricCardProps {
  label: string
  value: string
  subtext?: string
  valueClassName?: string
  variant?: 'alert'
}

function MetricCard({ label, value, subtext, valueClassName, variant }: MetricCardProps) {
  const cardClass = variant === 'alert'
    ? 'bg-status-red dark:bg-status-red-text/20 rounded-[8px] p-5 border border-status-red-text/30 dark:border-status-red-text/40 shadow-sm flex flex-col gap-1 h-full'
    : 'bg-surface-card dark:bg-dark-card rounded-[8px] p-5 border border-surface-border dark:border-dark-border shadow-md flex flex-col gap-1 h-full'
  return (
    <div className={cardClass}>
      <span className="text-[12px] text-muted-foreground">{label}</span>
      <span className={`text-[28px] font-display font-medium leading-none ${valueClassName ?? 'text-brand dark:text-foreground'}`}>
        {value}
      </span>
      {subtext && <span className="text-[11px] text-muted-foreground mt-0.5">{subtext}</span>}
    </div>
  )
}

function MetricCardSkeleton() {
  return (
    <div className="bg-surface-card dark:bg-dark-card rounded-[8px] p-5 border border-surface-border dark:border-dark-border shadow-sm flex flex-col gap-2 h-full">
      <div className="h-3 w-24 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
      <div className="h-8 w-32 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
      <div className="h-3 w-20 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Upcoming Deadlines
// ---------------------------------------------------------------------------

function daysBadge(days: number) {
  let cls = 'text-[11px] font-medium px-1.5 py-0.5 rounded'
  if (days <= 2) cls += ' bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
  else if (days <= 6) cls += ' bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400'
  else cls += ' bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
  return <span className={cls}>{days}d</span>
}

function UpcomingDeadlinesList({ items }: { items: UpcomingDeadlineItem[] }) {
  return (
    <div className="bg-surface-card dark:bg-dark-card rounded-[8px] border border-surface-border dark:border-dark-border shadow-sm overflow-hidden h-full flex flex-col">
      <div className="px-4 py-3 border-b border-surface-border dark:border-dark-border flex-shrink-0">
        <span className="text-[13px] font-medium text-foreground">Upcoming Deadlines</span>
      </div>
      {items.length === 0 ? (
        <div className="px-4 py-8 text-center flex-1">
          <p className="text-[13px] text-green-600 dark:text-green-400 font-medium">No deadlines in the next 14 days.</p>
          <p className="text-[12px] text-muted-foreground mt-1">Your runway is clear — keep it that way.</p>
        </div>
      ) : (
        <div className="divide-y divide-surface-border dark:divide-dark-border overflow-y-auto flex-1">
          {items.map((item) => (
            <div key={item.engagement_id} className="flex items-center px-4 py-2.5 gap-3">
              <div className="flex-1 min-w-0">
                <p className="text-[13px] font-medium text-foreground truncate">{item.client_name}</p>
              </div>
              <p className="text-[12px] text-muted-foreground truncate flex-shrink-0">{formatEngagementType(item.engagement_type)}</p>
              <p className="text-[12px] text-muted-foreground flex-shrink-0 w-24 text-right">{item.deadline}</p>
              <div className="flex-shrink-0">{daysBadge(item.days_until)}</div>
            </div>
          ))}
          <div className="px-4 py-2.5 flex justify-end">
            <Link href="/calendar" className="text-[12px] text-brand-light hover:underline">
              View full calendar &rarr;
            </Link>
          </div>
        </div>
      )}
    </div>
  )
}

function UpcomingDeadlinesSkeleton() {
  return (
    <div className="bg-surface-card dark:bg-dark-card rounded-[8px] border border-surface-border dark:border-dark-border shadow-sm overflow-hidden h-full">
      <div className="px-4 py-3 border-b border-surface-border dark:border-dark-border">
        <div className="h-4 w-36 bg-surface-border dark:bg-dark-border animate-pulse rounded" />
      </div>
      <div className="divide-y divide-surface-border dark:divide-dark-border">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="flex items-center px-4 py-3 gap-3">
            <div className="flex-1 h-4 bg-surface-border dark:bg-dark-border animate-pulse rounded" />
            <div className="h-4 w-20 bg-surface-border dark:bg-dark-border animate-pulse rounded" />
          </div>
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Staff Utilization
// ---------------------------------------------------------------------------

function utilizationBarColor(pct: number) {
  if (pct >= 100) return 'bg-red-500'
  if (pct >= 80) return 'bg-amber-400'
  return 'bg-green-500'
}

function StaffUtilizationPanel({ items }: { items: StaffUtilizationItem[] }) {
  return (
    <div className="bg-surface-card dark:bg-dark-card rounded-[8px] border border-surface-border dark:border-dark-border shadow-sm overflow-hidden h-full flex flex-col">
      <div className="px-4 py-3 border-b border-surface-border dark:border-dark-border flex-shrink-0">
        <span className="text-[13px] font-medium text-foreground">Staff Utilization</span>
      </div>
      {items.length === 0 ? (
        <div className="px-4 py-8 text-center flex-1">
          <p className="text-[12px] text-muted-foreground">No time logged this week.</p>
        </div>
      ) : (
        <div className="px-4 py-3 flex flex-col gap-3 overflow-y-auto flex-1">
          {items.map((item) => (
            <div key={item.user_id}>
              <div className="flex justify-between mb-1">
                <span className="text-[12px] text-foreground">{item.full_name}</span>
                <span className="text-[12px] text-muted-foreground">{Math.round(item.utilization_pct)}%</span>
              </div>
              <div className="h-2 w-full bg-surface-border dark:bg-dark-border rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${utilizationBarColor(item.utilization_pct)}`}
                  style={{ width: `${Math.min(item.utilization_pct, 100)}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function StaffUtilizationSkeleton() {
  return (
    <div className="bg-surface-card dark:bg-dark-card rounded-[8px] border border-surface-border dark:border-dark-border shadow-sm overflow-hidden h-full">
      <div className="px-4 py-3 border-b border-surface-border dark:border-dark-border">
        <div className="h-4 w-32 bg-surface-border dark:bg-dark-border animate-pulse rounded" />
      </div>
      <div className="px-4 py-3 flex flex-col gap-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i}>
            <div className="h-3 w-28 bg-surface-border dark:bg-dark-border animate-pulse rounded mb-2" />
            <div className="h-2 w-full bg-surface-border dark:bg-dark-border animate-pulse rounded-full" />
          </div>
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Overdue Engagements
// ---------------------------------------------------------------------------

function OverdueEngagementsTable({
  items,
  onComplete,
}: {
  items: OverdueEngagementItem[]
  onComplete: (id: string) => void
}) {
  const [completing, setCompleting] = useState<string | null>(null)

  async function handleComplete(id: string) {
    setCompleting(id)
    try {
      await api.patch(`/engagements/${id}`, { status: 'completed' })
      onComplete(id)
      toast.success('Engagement marked as complete')
    } catch {
      toast.error('Failed to update engagement')
    } finally {
      setCompleting(null)
    }
  }

  return (
    <div className="bg-surface-card dark:bg-dark-card rounded-[8px] border border-surface-border dark:border-dark-border shadow-sm overflow-hidden h-full flex flex-col">
      <div className="px-4 py-3 border-b border-surface-border dark:border-dark-border flex items-center gap-2 flex-shrink-0">
        <span className="text-[13px] font-medium text-foreground">Overdue Engagements</span>
        {items.length > 0 && (
          <span className="text-[11px] font-medium px-1.5 py-0.5 rounded bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">
            {items.length}
          </span>
        )}
      </div>
      {items.length === 0 ? (
        <div className="px-4 py-8 text-center flex flex-col items-center gap-2 flex-1">
          <CheckCircle className="w-5 h-5 text-green-500" />
          <p className="text-[13px] text-green-600 dark:text-green-400 font-medium">Nothing overdue. Good work.</p>
        </div>
      ) : (
        <div className="overflow-auto flex-1">
          <table className="w-full text-[12px]">
            <thead>
              <tr className="border-b border-surface-border dark:border-dark-border text-muted-foreground">
                <th className="px-4 py-2 text-left font-medium">Client</th>
                <th className="px-4 py-2 text-left font-medium">Engagement Type</th>
                <th className="px-4 py-2 text-left font-medium">Deadline</th>
                <th className="px-4 py-2 text-left font-medium">Days Overdue</th>
                <th className="px-4 py-2 text-left font-medium">Staff</th>
                <th className="px-4 py-2 text-left font-medium">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border dark:divide-dark-border">
              {items.map((item) => (
                <tr key={item.engagement_id}>
                  <td className="px-4 py-2.5 font-medium text-foreground">{item.client_name}</td>
                  <td className="px-4 py-2.5 text-muted-foreground">{formatEngagementType(item.engagement_type)}</td>
                  <td className="px-4 py-2.5 text-muted-foreground">{item.deadline}</td>
                  <td className="px-4 py-2.5">
                    <span className="font-medium text-[#DC2626]">{item.days_overdue}d</span>
                  </td>
                  <td className="px-4 py-2.5 text-muted-foreground">{item.assigned_staff_name ?? '—'}</td>
                  <td className="px-4 py-2.5">
                    <button
                      onClick={() => handleComplete(item.engagement_id)}
                      disabled={completing === item.engagement_id}
                      className="text-[11px] font-medium px-2.5 py-1 rounded border border-surface-border dark:border-dark-border text-foreground hover:bg-surface-input dark:hover:bg-dark-page disabled:opacity-50 transition-colors"
                    >
                      {completing === item.engagement_id ? 'Saving…' : 'Mark Complete'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Unsigned Documents
// ---------------------------------------------------------------------------

function UnsignedDocumentsTable({
  items,
  onActionComplete,
}: {
  items: UnsignedDocumentItem[]
  onActionComplete: () => void
}) {
  const [pending, setPending] = useState<string | null>(null)

  async function handleRemind(envelopeId: string) {
    setPending(envelopeId)
    try {
      await api.post(`/esign/envelopes/${envelopeId}/remind`)
      toast.success('Reminder sent')
      onActionComplete()
    } catch {
      toast.error('Failed to send reminder')
    } finally {
      setPending(null)
    }
  }

  async function handleCreateFollowup(envelopeId: string) {
    setPending(envelopeId)
    try {
      await api.post(`/esign/envelopes/${envelopeId}/create-followup-task`)
      toast.success('Follow-up task created')
      onActionComplete()
    } catch {
      toast.error('Failed to create task')
    } finally {
      setPending(null)
    }
  }

  function renderStatusCell(item: UnsignedDocumentItem) {
    if (item.reminder_state === 'ready_first') {
      return <span className="text-[11px] text-muted-foreground">Awaiting first follow-up</span>
    }
    if (item.reminder_state === 'ready_second') {
      return <span className="text-[11px] text-status-amber-text">Needs second reminder</span>
    }
    return <span className="text-[11px] text-status-red-text">No response</span>
  }

  function renderActionCell(item: UnsignedDocumentItem) {
    const isPending = pending === item.envelope_id
    if (item.reminder_state === 'ready_first') {
      return (
        <button
          onClick={() => handleRemind(item.envelope_id)}
          disabled={isPending}
          className="text-[11px] font-medium px-2.5 py-1 rounded border border-brand text-brand disabled:opacity-50 disabled:cursor-not-allowed transition-colors hover:bg-surface-card"
        >
          {isPending ? '...' : 'Send Reminder'}
        </button>
      )
    }
    if (item.reminder_state === 'ready_second') {
      return (
        <button
          onClick={() => handleRemind(item.envelope_id)}
          disabled={isPending}
          style={{ borderColor: '#F59E0B', color: '#92400E' }}
          className="text-[11px] font-medium px-2.5 py-1 rounded border disabled:opacity-50 disabled:cursor-not-allowed transition-colors hover:opacity-80"
        >
          {isPending ? '...' : 'Send Second Reminder'}
        </button>
      )
    }
    return (
      <button
        onClick={() => handleCreateFollowup(item.envelope_id)}
        disabled={isPending}
        style={{ borderColor: '#991B1B', color: '#991B1B' }}
        className="text-[11px] font-medium px-2.5 py-1 rounded border disabled:opacity-50 disabled:cursor-not-allowed transition-colors hover:opacity-80"
      >
        {isPending ? '...' : 'Create Follow-Up Task'}
      </button>
    )
  }

  return (
    <div className="bg-surface-card dark:bg-dark-card rounded-[8px] border border-surface-border dark:border-dark-border shadow-sm overflow-hidden h-full flex flex-col">
      <div className="px-4 py-3 border-b border-surface-border dark:border-dark-border flex items-center gap-2 flex-shrink-0">
        <span className="text-[13px] font-medium text-foreground">Awaiting Signature</span>
        {items.length > 0 && (
          <span className="text-[11px] font-medium px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
            {items.length}
          </span>
        )}
      </div>
      {items.length === 0 ? (
        <div className="px-4 py-8 text-center flex-1">
          <p className="text-[13px] text-green-600 dark:text-green-400 font-medium">All signatures are in.</p>
          <p className="text-[12px] text-muted-foreground mt-1">No envelopes are sitting unsigned across your clients.</p>
        </div>
      ) : (
        <div className="overflow-auto flex-1">
          <table className="w-full text-[12px]">
            <thead>
              <tr className="border-b border-surface-border dark:border-dark-border text-muted-foreground">
                <th className="px-4 py-2 text-left font-medium">Client</th>
                <th className="px-4 py-2 text-left font-medium">Document</th>
                <th className="px-4 py-2 text-left font-medium">Sent</th>
                <th className="px-4 py-2 text-left font-medium">Days Waiting</th>
                <th className="px-4 py-2 text-left font-medium">Status</th>
                <th className="px-4 py-2 text-left font-medium">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border dark:divide-dark-border">
              {items.map((item) => (
                <tr key={item.envelope_id}>
                  <td className="px-4 py-2.5 font-medium text-foreground">
                    <span>{item.client_name}</span>
                    {item.reminder_state === 'escalated' && (
                      <span
                        className="ml-2 text-[11px] font-medium px-1.5 py-0.5 rounded-full"
                        style={{ color: '#991B1B', backgroundColor: '#FEE2E2' }}
                      >
                        Unresponsive
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-muted-foreground">{item.document_title || '—'}</td>
                  <td className="px-4 py-2.5 text-muted-foreground">{new Date(item.sent_at).toLocaleDateString()}</td>
                  <td className="px-4 py-2.5 text-muted-foreground">{item.days_waiting}d</td>
                  <td className="px-4 py-2.5">{renderStatusCell(item)}</td>
                  <td className="px-4 py-2.5">{renderActionCell(item)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// WIP Widget (fetches its own data via reportsApi internally, unchanged)
// ---------------------------------------------------------------------------

function WIPWidget() {
  const { data, isLoading, isError } = useQuery<WIPSummary>({
    queryKey: ['wip-summary'],
    queryFn: reportsApi.getWip,
    staleTime: 5 * 60 * 1000,
  })

  return (
    <div className="bg-surface-card dark:bg-dark-card rounded-[8px] border border-surface-border dark:border-dark-border shadow-sm overflow-hidden h-full flex flex-col">
      <div className="px-4 py-3 border-b border-surface-border dark:border-dark-border flex-shrink-0">
        <span className="text-[13px] font-medium text-foreground">Work in Progress</span>
        {isLoading ? (
          <div className="flex flex-col gap-1 mt-1">
            <div className="h-7 w-28 bg-surface-border dark:bg-dark-border animate-pulse rounded" />
            <div className="h-3 w-20 bg-surface-border dark:bg-dark-border animate-pulse rounded" />
          </div>
        ) : !isError && data ? (
          <div className="mt-1">
            <p className="text-[22px] font-display font-medium text-brand dark:text-foreground leading-none">{formatCurrency(data?.totalWipValue ?? 0)}</p>
            <p className="text-[11px] text-muted-foreground mt-0.5">{data?.totalHours ?? 0} hrs unbilled</p>
          </div>
        ) : null}
      </div>
      {isLoading ? (
        <div className="divide-y divide-surface-border dark:divide-dark-border flex-1">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="flex items-center justify-between px-4 py-2.5">
              <div className="flex flex-col gap-1 flex-1">
                <div className="h-3.5 w-40 bg-surface-border dark:bg-dark-border animate-pulse rounded" />
                <div className="h-3 w-24 bg-surface-border dark:bg-dark-border animate-pulse rounded" />
              </div>
              <div className="h-4 w-16 bg-surface-border dark:bg-dark-border animate-pulse rounded" />
            </div>
          ))}
        </div>
      ) : isError ? (
        <div className="px-4 py-8 text-center flex-1">
          <p className="text-[12px] text-muted-foreground">WIP data unavailable.</p>
        </div>
      ) : !data || (data?.topEngagements ?? []).length === 0 ? (
        <div className="px-4 py-8 text-center flex-1">
          <p className="text-[13px] text-green-600 dark:text-green-400 font-medium">All billable work is accounted for.</p>
          <p className="text-[12px] text-muted-foreground mt-1">Nothing sitting uninvoiced right now.</p>
        </div>
      ) : (
        <div className="divide-y divide-surface-border dark:divide-dark-border overflow-y-auto flex-1">
          {(data?.topEngagements ?? []).slice(0, 5).map((eng) => (
            <div key={eng.engagementId} className="flex items-center justify-between px-4 py-2.5">
              <div className="min-w-0 flex-1">
                <p className="text-[13px] font-medium text-foreground truncate">{eng.engagementName}</p>
                <p className="text-[11px] text-muted-foreground truncate">{eng.clientName}</p>
              </div>
              <span className="text-[13px] font-display font-medium text-status-amber-text dark:text-amber-400 ml-4 flex-shrink-0">
                {formatCurrency(eng.wipValue)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Batch 4a widgets
// ---------------------------------------------------------------------------

function MyTasksWidget({ data }: { data: Record<string, unknown> }) {
  const tasks = (data.tasks ?? []) as Array<{ task_id: string; title: string; client_name: string; status: string; due_date: string | null; overdue: boolean }>
  const incompleteCount = Number(data.incomplete_tasks ?? 0)
  return (
    <div className="bg-surface-card dark:bg-dark-card rounded-[8px] border border-surface-border dark:border-dark-border shadow-sm overflow-hidden h-full flex flex-col">
      <div className="px-4 py-3 border-b border-surface-border dark:border-dark-border flex items-center gap-2 flex-shrink-0">
        <span className="text-[13px] font-medium text-foreground">My Tasks</span>
        {incompleteCount > 0 && (
          <span className="text-[11px] font-medium px-1.5 py-0.5 rounded bg-brand/10 text-brand">{incompleteCount}</span>
        )}
      </div>
      {tasks.length === 0 ? (
        <div className="px-4 py-8 text-center flex flex-col items-center gap-2 flex-1">
          <CheckCircle className="w-5 h-5 text-green-500" />
          <p className="text-[13px] text-green-600 dark:text-green-400 font-medium">All caught up. No incomplete tasks.</p>
        </div>
      ) : (
        <div className="divide-y divide-surface-border dark:divide-dark-border overflow-y-auto flex-1">
          {tasks.map((task) => (
            <Link key={task.task_id} href={`/tasks/${task.task_id}`} className="flex items-center px-4 py-2.5 gap-3 hover:bg-surface-input dark:hover:bg-dark-page transition-colors">
              <div className="flex-1 min-w-0">
                <p className="text-[13px] font-medium text-foreground truncate">{task.title}</p>
                <p className="text-[11px] text-muted-foreground truncate">{task.client_name}</p>
              </div>
              {task.overdue && (
                <span className="text-[11px] font-medium px-1.5 py-0.5 rounded bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400 flex-shrink-0">Overdue</span>
              )}
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}

function ClientCommunicationGapWidget({ data }: { data: Record<string, unknown> }) {
  const clients = (data.clients ?? []) as Array<{ client_id: string; client_name: string; last_outbound: string | null; days_since_contact: number | null }>
  const gapCount = Number(data.gap_count ?? 0)
  const threshold = Number(data.threshold_days ?? 21)
  return (
    <div className="bg-surface-card dark:bg-dark-card rounded-[8px] border border-surface-border dark:border-dark-border shadow-sm overflow-hidden h-full flex flex-col">
      <div className="px-4 py-3 border-b border-surface-border dark:border-dark-border flex items-center gap-2 flex-shrink-0">
        <span className="text-[13px] font-medium text-foreground">Communication Gaps</span>
        {gapCount > 0 && (
          <span className="text-[11px] font-medium px-1.5 py-0.5 rounded bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">{gapCount}</span>
        )}
      </div>
      {clients.length === 0 ? (
        <div className="px-4 py-8 text-center flex flex-col items-center gap-2 flex-1">
          <CheckCircle className="w-5 h-5 text-green-500" />
          <p className="text-[13px] text-green-600 dark:text-green-400 font-medium">All clients contacted in the last {threshold} days.</p>
        </div>
      ) : (
        <div className="divide-y divide-surface-border dark:divide-dark-border overflow-y-auto flex-1">
          {clients.map((c) => (
            <Link key={c.client_id} href={`/clients/${c.client_id}`} className="flex items-center px-4 py-2.5 gap-3 hover:bg-surface-input dark:hover:bg-dark-page transition-colors">
              <p className="text-[13px] font-medium text-foreground flex-1 truncate">{c.client_name}</p>
              <p className="text-[11px] text-muted-foreground flex-shrink-0">
                {c.days_since_contact != null ? `${c.days_since_contact}d ago` : 'No contact logged'}
              </p>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}

function OutstandingDocumentRequestsWidget({ data }: { data: Record<string, unknown> }) {
  const requests = (data.requests ?? []) as Array<{ id: string; title: string; status: string; due_date: string | null; client_name: string; engagement_name: string }>
  const count = Number(data.outstanding_count ?? 0)
  return (
    <div className="bg-surface-card dark:bg-dark-card rounded-[8px] border border-surface-border dark:border-dark-border shadow-sm overflow-hidden h-full flex flex-col">
      <div className="px-4 py-3 border-b border-surface-border dark:border-dark-border flex items-center gap-2 flex-shrink-0">
        <span className="text-[13px] font-medium text-foreground">Outstanding Document Requests</span>
        {count > 0 && (
          <span className="text-[11px] font-medium px-1.5 py-0.5 rounded bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">{count}</span>
        )}
      </div>
      {requests.length === 0 ? (
        <div className="px-4 py-8 text-center flex flex-col items-center gap-2 flex-1">
          <CheckCircle className="w-5 h-5 text-green-500" />
          <p className="text-[13px] text-green-600 dark:text-green-400 font-medium">No outstanding document requests.</p>
        </div>
      ) : (
        <div className="divide-y divide-surface-border dark:divide-dark-border overflow-y-auto flex-1">
          {requests.map((req) => (
            <div key={req.id} className="flex items-center px-4 py-2.5 gap-3">
              <div className="flex-1 min-w-0">
                <p className="text-[13px] font-medium text-foreground truncate">{req.title}</p>
                <p className="text-[11px] text-muted-foreground truncate">{req.client_name}</p>
              </div>
              {req.due_date && (
                <p className="text-[11px] text-muted-foreground flex-shrink-0">{req.due_date}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function UnbilledHoursWidget({ data }: { data: Record<string, unknown> }) {
  const billableThisWeek = Number(data.firm_billable_hours_this_week ?? 0)
  const unbilledThisMonth = Number(data.unbilled_billable_hours_this_month_all_engagements ?? 0)
  const staff = (data.staff ?? []) as Array<{ user_id: string; full_name: string; billable: number; non_billable: number }>
  return (
    <div className="bg-surface-card dark:bg-dark-card rounded-[8px] border border-surface-border dark:border-dark-border shadow-sm overflow-hidden h-full flex flex-col">
      <div className="px-4 py-3 border-b border-surface-border dark:border-dark-border flex-shrink-0">
        <span className="text-[13px] font-medium text-foreground">Unbilled Hours</span>
      </div>
      <div className="px-4 py-3 flex gap-6 border-b border-surface-border dark:border-dark-border flex-shrink-0">
        <div>
          <p className="text-[11px] text-muted-foreground">Billable this week</p>
          <p className="text-[20px] font-semibold text-foreground">{billableThisWeek.toFixed(1)}h</p>
        </div>
        <div>
          <p className="text-[11px] text-muted-foreground">Unbilled this month</p>
          <p className="text-[20px] font-semibold text-foreground">{unbilledThisMonth.toFixed(1)}h</p>
        </div>
      </div>
      {staff.length === 0 ? (
        <div className="px-4 py-6 text-center flex-1">
          <p className="text-[12px] text-muted-foreground">No time logged this week.</p>
        </div>
      ) : (
        <div className="divide-y divide-surface-border dark:divide-dark-border overflow-y-auto flex-1">
          {staff.map((s) => (
            <div key={s.user_id} className="flex items-center px-4 py-2.5 gap-3">
              <p className="text-[13px] text-foreground flex-1 truncate">{s.full_name}</p>
              <p className="text-[12px] text-muted-foreground flex-shrink-0">{Number(s.billable ?? 0).toFixed(1)}h billable</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function RecentFirmChatActivityWidget({ data }: { data: Record<string, unknown> }) {
  const messages = (data.messages ?? []) as Array<{ channel_name: string; sender_name: string; body_snippet: string; created_at: string }>
  const days = Number(data.days ?? 7)
  return (
    <div className="bg-surface-card dark:bg-dark-card rounded-[8px] border border-surface-border dark:border-dark-border shadow-sm overflow-hidden h-full flex flex-col">
      <div className="px-4 py-3 border-b border-surface-border dark:border-dark-border flex-shrink-0">
        <span className="text-[13px] font-medium text-foreground">Recent Firm Chat</span>
      </div>
      {messages.length === 0 ? (
        <div className="px-4 py-8 text-center flex-1">
          <p className="text-[13px] text-green-600 dark:text-green-400 font-medium">No firm chat activity in the last {days} days.</p>
        </div>
      ) : (
        <div className="divide-y divide-surface-border dark:divide-dark-border overflow-y-auto flex-1">
          {messages.map((msg, i) => (
            <Link key={i} href="/firm-chat" className="flex flex-col px-4 py-2.5 gap-0.5 hover:bg-surface-input dark:hover:bg-dark-page transition-colors">
              <div className="flex items-center gap-1.5">
                <span className="text-[12px] font-medium text-foreground">{msg.sender_name}</span>
                <span className="text-[11px] text-muted-foreground">#{msg.channel_name}</span>
              </div>
              <p className="text-[12px] text-muted-foreground truncate">{msg.body_snippet}</p>
            </Link>
          ))}
          <div className="px-4 py-2.5 flex justify-end">
            <Link href="/firm-chat" className="text-[12px] text-brand-light hover:underline">Open firm chat &rarr;</Link>
          </div>
        </div>
      )}
    </div>
  )
}

function ClientHealthSnapshotWidget({ data }: { data: Record<string, unknown> }) {
  const clientName = String(data.client_name ?? 'Client Health')
  const status = String(data.status ?? 'unknown')
  const reasons = (data.reasons ?? []) as Array<{ severity: string; text: string }>
  const statusColor = status === 'healthy' ? 'text-green-600 dark:text-green-400' : status === 'at_risk' ? 'text-amber-600 dark:text-amber-400' : 'text-red-600 dark:text-red-400'
  const statusLabel = status === 'healthy' ? 'Healthy' : status === 'at_risk' ? 'At Risk' : status === 'critical' ? 'Critical' : status
  return (
    <div className="bg-surface-card dark:bg-dark-card rounded-[8px] border border-surface-border dark:border-dark-border shadow-sm overflow-hidden h-full flex flex-col">
      <div className="px-4 py-3 border-b border-surface-border dark:border-dark-border flex items-center gap-2 flex-shrink-0">
        <span className="text-[13px] font-medium text-foreground">{clientName}</span>
        <span className={`text-[11px] font-medium ${statusColor}`}>{statusLabel}</span>
      </div>
      <div className="px-4 py-3 flex flex-col gap-2 overflow-y-auto flex-1">
        {reasons.map((r, i) => (
          <p key={i} className="text-[12px] text-muted-foreground">{r.text}</p>
        ))}
      </div>
    </div>
  )
}

function SingleClientQuickViewWidget({ data }: { data: Record<string, unknown> }) {
  const clientName = String(data.client_name ?? '')
  const email = String(data.email ?? '')
  const entityType = String(data.entity_type ?? '')
  const portalAccess = Boolean(data.portal_access)
  const engagements = (data.engagements ?? []) as unknown[]
  const invoices = (data.invoices ?? []) as unknown[]
  const pendingDocRequests = Number(data.pending_document_requests ?? 0)
  return (
    <div className="bg-surface-card dark:bg-dark-card rounded-[8px] border border-surface-border dark:border-dark-border shadow-sm overflow-hidden h-full flex flex-col">
      <div className="px-4 py-3 border-b border-surface-border dark:border-dark-border flex-shrink-0">
        <p className="text-[13px] font-medium text-foreground">{clientName || 'Client'}</p>
        {email && <p className="text-[11px] text-muted-foreground">{email}</p>}
      </div>
      <div className="px-4 py-3 flex flex-col gap-2 overflow-y-auto flex-1">
        {entityType && (
          <div className="flex justify-between">
            <span className="text-[12px] text-muted-foreground">Type</span>
            <span className="text-[12px] text-foreground capitalize">{entityType}</span>
          </div>
        )}
        <div className="flex justify-between">
          <span className="text-[12px] text-muted-foreground">Engagements</span>
          <span className="text-[12px] text-foreground">{engagements.length}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-[12px] text-muted-foreground">Invoices</span>
          <span className="text-[12px] text-foreground">{invoices.length}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-[12px] text-muted-foreground">Pending doc requests</span>
          <span className="text-[12px] text-foreground">{pendingDocRequests}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-[12px] text-muted-foreground">Portal</span>
          <span className={`text-[12px] font-medium ${portalAccess ? 'text-green-600 dark:text-green-400' : 'text-muted-foreground'}`}>
            {portalAccess ? 'Enabled' : 'Not enabled'}
          </span>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Widget Skeleton
// ---------------------------------------------------------------------------

function WidgetSkeleton({ typeKey }: { typeKey: string }) {
  if (['revenue_this_month', 'outstanding_ar', 'unbilled_wip_stat', 'overdue_engagements_count'].includes(typeKey)) {
    return <MetricCardSkeleton />
  }
  if (typeKey === 'upcoming_deadlines') return <UpcomingDeadlinesSkeleton />
  if (typeKey === 'staff_utilization') return <StaffUtilizationSkeleton />
  return <div className="h-full bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded-[8px]" />
}

// ---------------------------------------------------------------------------
// Widget Renderer
// ---------------------------------------------------------------------------

function WidgetRenderer({ widget }: { widget: DashboardWidgetInstance }) {
  const [dismissedIds, setDismissedIds] = useState<Set<string>>(new Set())

  const isWIP = widget.type_key === 'work_in_progress'

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['dashboard-widget-data', widget.type_key, widget.instance_id],
    queryFn: () => dashboardApi.getWidgetData(widget.type_key, widget.config),
    staleTime: 60 * 1000,
    enabled: !isWIP,
  })

  if (isWIP) return <WIPWidget />
  if (isLoading) return <WidgetSkeleton typeKey={widget.type_key} />

  if (isError || !data) {
    return (
      <div className="flex items-center justify-center h-full bg-surface-card dark:bg-dark-card rounded-[8px] border border-surface-border dark:border-dark-border">
        <p className="text-[12px] text-muted-foreground">Data unavailable.</p>
      </div>
    )
  }

  const d = data as Record<string, unknown>

  switch (widget.type_key) {
    case 'revenue_this_month': {
      const mrr = Number(d.mrr ?? 0)
      const count = Number(d.mrr_invoice_count ?? 0)
      return (
        <MetricCard
          label="Revenue This Month"
          value={formatCurrency(mrr)}
          subtext={`${count} invoice${count !== 1 ? 's' : ''} paid`}
        />
      )
    }
    case 'outstanding_ar': {
      const ar = Number(d.outstanding_ar ?? 0)
      const arCount = Number(d.outstanding_ar_count ?? 0)
      const oldestDays = d.oldest_overdue_days != null ? Number(d.oldest_overdue_days) : null
      return (
        <Link href="/billing" className="block h-full hover:opacity-90 transition-opacity">
          <MetricCard
            label="Outstanding AR"
            value={formatCurrency(ar)}
            subtext={oldestDays != null ? `${arCount} unpaid · Oldest: ${oldestDays}d` : `${arCount} unpaid`}
          />
        </Link>
      )
    }
    case 'unbilled_wip_stat': {
      const wip = Number(d.wip_value ?? 0)
      const hours = Number(d.wip_hours ?? 0)
      return (
        <MetricCard
          label="Unbilled WIP"
          value={formatCurrency(wip)}
          subtext={`${hours.toFixed(1)} hours`}
        />
      )
    }
    case 'overdue_engagements_count': {
      const count = Number(d.overdue_engagement_count ?? 0)
      return (
        <MetricCard
          label="Overdue Engagements"
          value={String(count)}
          variant={count > 0 ? 'alert' : undefined}
          valueClassName={count > 0 ? 'text-[#DC2626]' : 'text-brand dark:text-foreground'}
        />
      )
    }
    case 'upcoming_deadlines': {
      const items = (d.upcoming_deadlines ?? []) as UpcomingDeadlineItem[]
      return <UpcomingDeadlinesList items={items} />
    }
    case 'staff_utilization': {
      const items = (d.staff_utilization ?? []) as StaffUtilizationItem[]
      return <StaffUtilizationPanel items={items} />
    }
    case 'overdue_engagements_table': {
      const all = (d.overdue_engagements ?? []) as OverdueEngagementItem[]
      const visible = all.filter((e) => !dismissedIds.has(e.engagement_id))
      return (
        <OverdueEngagementsTable
          items={visible}
          onComplete={(id) => setDismissedIds((prev) => new Set([...prev, id]))}
        />
      )
    }
    case 'awaiting_signature': {
      const items = (d.unsigned_documents ?? []) as UnsignedDocumentItem[]
      return <UnsignedDocumentsTable items={items} onActionComplete={() => void refetch()} />
    }
    case 'my_tasks':
      return <MyTasksWidget data={d} />
    case 'client_communication_gap':
      return <ClientCommunicationGapWidget data={d} />
    case 'outstanding_document_requests':
      return <OutstandingDocumentRequestsWidget data={d} />
    case 'unbilled_hours':
      return <UnbilledHoursWidget data={d} />
    case 'recent_firm_chat_activity':
      return <RecentFirmChatActivityWidget data={d} />
    case 'client_health_snapshot':
      return <ClientHealthSnapshotWidget data={d} />
    case 'single_client_quick_view':
      return <SingleClientQuickViewWidget data={d} />
    default:
      return (
        <div className="flex items-center justify-center h-full bg-surface-card dark:bg-dark-card rounded-[8px] border border-surface-border dark:border-dark-border">
          <p className="text-[12px] text-muted-foreground">Unknown widget: {widget.type_key}</p>
        </div>
      )
  }
}

// ---------------------------------------------------------------------------
// Edit Mode Overlay — rendered on top of each widget during edit mode
// ---------------------------------------------------------------------------

function WidgetEditOverlay({
  onRemove,
  onMinimize,
}: {
  onRemove: () => void
  onMinimize: () => void
}) {
  return (
    <div className="absolute inset-0 z-10 pointer-events-none rounded-[8px]">
      <div className="absolute top-1.5 right-1.5 flex gap-1 pointer-events-auto">
        <button
          onPointerDown={(e) => e.stopPropagation()}
          onClick={(e) => { e.stopPropagation(); onMinimize() }}
          className="w-6 h-6 rounded flex items-center justify-center bg-white/90 dark:bg-dark-card/90 border border-surface-border dark:border-dark-border hover:bg-surface-input dark:hover:bg-dark-page shadow-sm transition-colors"
          title="Minimize"
        >
          <Minus className="w-3.5 h-3.5 text-muted-foreground" />
        </button>
        <button
          onPointerDown={(e) => e.stopPropagation()}
          onClick={(e) => { e.stopPropagation(); onRemove() }}
          className="w-6 h-6 rounded flex items-center justify-center bg-white/90 dark:bg-dark-card/90 border border-surface-border dark:border-dark-border hover:bg-red-50 dark:hover:bg-red-900/20 shadow-sm transition-colors"
          title="Remove"
        >
          <X className="w-3.5 h-3.5 text-muted-foreground" />
        </button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Collapsed Widget Header — shown instead of widget content when minimized
// ---------------------------------------------------------------------------

function CollapsedWidgetHeader({
  displayName,
  onClick,
}: {
  displayName: string
  onClick: () => void
}) {
  return (
    <button
      onPointerDown={(e) => e.stopPropagation()}
      onClick={(e) => { e.stopPropagation(); onClick() }}
      className="w-full h-full bg-surface-card dark:bg-dark-card rounded-[8px] border border-surface-border dark:border-dark-border shadow-sm flex items-center px-4 gap-2 hover:bg-surface-input dark:hover:bg-dark-page text-left transition-colors"
    >
      <span className="text-[13px] font-medium text-foreground flex-1 truncate">{displayName}</span>
      <ChevronDown className="w-4 h-4 text-muted-foreground flex-shrink-0" />
    </button>
  )
}

// ---------------------------------------------------------------------------
// Add Widget Gallery Modal
// ---------------------------------------------------------------------------

const CATEGORY_LABELS: Record<string, string> = {
  overview: "Overview",
  tasks: "Tasks",
  clients: "Clients",
  billing: "Billing",
  calendar: "Calendar",
  engagements: "Engagements",
  documents: "Documents",
  staff: "Staff",
}

function AddWidgetModal({
  open,
  onClose,
  catalog,
  onAdd,
  editedWidgets,
}: {
  open: boolean
  onClose: () => void
  catalog: WidgetCatalogItem[]
  onAdd: (entry: WidgetCatalogItem, config?: Record<string, unknown>) => void
  editedWidgets: DashboardWidgetInstance[]
}) {
  const [pendingEntry, setPendingEntry] = useState<WidgetCatalogItem | null>(null)
  const [selectedClientId, setSelectedClientId] = useState('')
  const [clients, setClients] = useState<{ value: string; label: string }[]>([])
  const [clientsLoading, setClientsLoading] = useState(false)

  useEffect(() => {
    if (!pendingEntry) return
    if (!pendingEntry.config_schema.some((f) => f.type === 'client_picker')) return
    setClientsLoading(true)
    clientsApi
      .list(0, 100)
      .then(({ items }) => setClients(items.map((c) => ({ value: c.id, label: c.name }))))
      .catch(() => setClients([]))
      .finally(() => setClientsLoading(false))
  }, [pendingEntry])

  const grouped = catalog.reduce<Record<string, WidgetCatalogItem[]>>((acc, w) => {
    if (!acc[w.category]) acc[w.category] = []
    acc[w.category].push(w)
    return acc
  }, {})

  const categories = Object.keys(grouped).sort()

  function handleEntryClick(entry: WidgetCatalogItem) {
    if (entry.config_schema.some((f) => f.type === 'client_picker')) {
      setSelectedClientId('')
      setClients([])
      setPendingEntry(entry)
    } else {
      onAdd(entry)
    }
  }

  function handleConfigConfirm() {
    if (!pendingEntry || !selectedClientId) return
    const config: Record<string, unknown> = {}
    pendingEntry.config_schema.forEach((f) => {
      if (f.type === 'client_picker') config[f.field] = selectedClientId
    })
    onAdd(pendingEntry, config)
    setPendingEntry(null)
    setSelectedClientId('')
  }

  function handleConfigCancel() {
    setPendingEntry(null)
    setSelectedClientId('')
  }

  const modalTitle = pendingEntry ? `Configure ${pendingEntry.display_name}` : 'Add Widget'
  const modalClose = pendingEntry ? handleConfigCancel : onClose

  return (
    <Modal open={open} onClose={modalClose} title={modalTitle} size="lg">
      {pendingEntry ? (
        <div className="flex flex-col gap-4">
          <p className="text-[13px] text-muted-foreground">Select a client for this widget.</p>
          <SelectInput
            value={selectedClientId}
            onChange={(e) => setSelectedClientId(e.target.value)}
            options={clients}
            placeholder={clientsLoading ? 'Loading clients...' : 'Select client'}
          />
          <div className="flex justify-end gap-2">
            <button
              onClick={handleConfigCancel}
              className="text-[13px] font-medium px-3.5 py-1.5 rounded border border-surface-border dark:border-dark-border text-foreground hover:bg-surface-input dark:hover:bg-dark-page transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleConfigConfirm}
              disabled={!selectedClientId}
              className="text-[13px] font-medium px-3.5 py-1.5 rounded bg-brand text-white hover:opacity-90 disabled:opacity-50 transition-opacity"
            >
              Add Widget
            </button>
          </div>
        </div>
      ) : categories.length === 0 ? (
        <p className="text-[13px] text-muted-foreground text-center py-6">No widgets available to add.</p>
      ) : (
        <div className="flex flex-col gap-6">
          {categories.map((cat) => (
            <div key={cat}>
              <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide mb-2">
                {CATEGORY_LABELS[cat] ?? cat}
              </p>
              <div className="grid grid-cols-2 gap-2">
                {grouped[cat].map((entry) => {
                  const alreadyAdded = entry.config_schema.length === 0 && editedWidgets.some((w) => w.type_key === entry.type_key)
                  if (alreadyAdded) {
                    return (
                      <div
                        key={entry.type_key}
                        className="text-left px-3.5 py-3 rounded-[8px] border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card opacity-50 cursor-not-allowed"
                      >
                        <p className="text-[13px] font-medium text-foreground">{entry.display_name}</p>
                        <p className="text-[11px] text-muted-foreground mt-0.5">Added</p>
                      </div>
                    )
                  }
                  return (
                    <button
                      key={entry.type_key}
                      onClick={() => handleEntryClick(entry)}
                      className="text-left px-3.5 py-3 rounded-[8px] border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card hover:bg-surface-input dark:hover:bg-dark-page transition-colors"
                    >
                      <p className="text-[13px] font-medium text-foreground">{entry.display_name}</p>
                      {entry.allowed_sizes.length > 0 && (
                        <p className="text-[11px] text-muted-foreground mt-0.5">
                          {entry.allowed_sizes.join(", ")}
                        </p>
                      )}
                    </button>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </Modal>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function DashboardPage() {
  const { width, containerRef, mounted } = useContainerWidth()


  const { user } = useAuth()
  const { confirm, ConfirmDialog } = useConfirm()
  const [editMode, setEditMode] = useState(false)
  const [editedWidgets, setEditedWidgets] = useState<DashboardWidgetInstance[]>([])
  const [saving, setSaving] = useState(false)
  const [showAddWidget, setShowAddWidget] = useState(false)
  const [showSaveTemplate, setShowSaveTemplate] = useState(false)
  const [templateName, setTemplateName] = useState('')
  const [showLoadTemplate, setShowLoadTemplate] = useState(false)
  const [templates, setTemplates] = useState<DashboardTemplateItem[]>([])
  const [templatesLoading, setTemplatesLoading] = useState(false)

  const {
    data: widgets,
    isLoading: layoutLoading,
    isError: layoutError,
    refetch: refetchLayout,
  } = useQuery<DashboardWidgetInstance[]>({
    queryKey: ['dashboard-layout'],
    queryFn: () => dashboardApi.getLayout(),
    staleTime: 60 * 1000,
  })

  const { data: catalog = [] } = useQuery<WidgetCatalogItem[]>({
    queryKey: ['dashboard-widget-catalog'],
    queryFn: () => dashboardApi.getWidgetCatalog(),
    staleTime: 30 * 60 * 1000,
  })

  const catalogByKey = useMemo(
    () => new Map(catalog.map((c) => [c.type_key, c])),
    [catalog]
  )

  const activeWidgets = editMode ? editedWidgets : (widgets ?? [])

  // Build the react-grid-layout layout array from the active widget list
  const layout = useMemo<Layout>(() => {
    return activeWidgets.map((w): LayoutItem => {
      const baseSpan = SIZE_TO_SPAN[w.size] ?? SIZE_TO_SPAN.medium
      const span = w.minimized ? { w: baseSpan.w, h: 1 } : baseSpan
      const catalogEntry = catalogByKey.get(w.type_key)
      const allowedSizes = catalogEntry?.allowed_sizes ?? [w.size]
      const singleSize = allowedSizes.length <= 1

      const item: LayoutItem = {
        i: w.instance_id,
        x: w.grid_x,
        y: w.grid_y,
        ...span,
        isResizable: false,
      }

      if (editMode && !w.minimized) {
        if (!singleSize) {
          const minSpan = SIZE_TO_SPAN[allowedSizes[0]]
          const maxSpan = SIZE_TO_SPAN[allowedSizes[allowedSizes.length - 1]]
          if (minSpan && maxSpan) {
            item.isResizable = true
            item.minW = minSpan.w
            item.minH = minSpan.h
            item.maxW = maxSpan.w
            item.maxH = maxSpan.h
          }
        }
      }

      return item
    })
  }, [activeWidgets, catalogByKey, editMode])

  function handleEnterEdit() {
    if (!widgets) return
    setEditedWidgets(widgets.map((w) => ({ ...w })))
    setEditMode(true)
  }

  function handleCancel() {
    setEditedWidgets([])
    setEditMode(false)
  }

  async function handleResetToDefault() {
    const confirmed = await confirm({
      message: 'This will replace your current arrangement with the default layout. Nothing is saved until you click Done.',
      confirmLabel: 'Reset to Default',
      destructive: true,
    })
    if (!confirmed) return
    try {
      const defaultWidgets = await dashboardApi.getDefaultLayout()
      setEditedWidgets(defaultWidgets)
    } catch {
      toast.error('Failed to load default layout')
    }
  }

  async function handleSaveAsFirmDefault() {
    const confirmed = await confirm({
      message: 'This immediately saves the current arrangement as the firm-wide default for new managers. This is a direct write to a shared firm record and cannot be undone with Cancel.',
      confirmLabel: 'Save as Firm Default',
      destructive: true,
    })
    if (!confirmed) return
    try {
      await dashboardApi.putFirmDefaultLayout(editedWidgets)
      toast.success('Firm default layout saved')
    } catch {
      toast.error('Failed to save firm default layout')
    }
  }

  function handleOpenSaveTemplate() {
    setTemplateName('')
    setShowSaveTemplate(true)
  }

  async function handleConfirmSaveTemplate() {
    if (!templateName.trim()) return
    try {
      await dashboardApi.createTemplate(templateName.trim(), editedWidgets)
      toast.success('Template saved')
      setShowSaveTemplate(false)
      setTemplateName('')
    } catch {
      toast.error('Failed to save template')
    }
  }

  async function handleOpenLoadTemplate() {
    setTemplatesLoading(true)
    setShowLoadTemplate(true)
    try {
      const list = await dashboardApi.getTemplates()
      setTemplates(list)
    } catch {
      toast.error('Failed to load templates')
    } finally {
      setTemplatesLoading(false)
    }
  }

  function handleSelectTemplate(tmpl: DashboardTemplateItem) {
    setEditedWidgets(tmpl.widgets)
    setShowLoadTemplate(false)
  }

  async function handleDeleteTemplate(templateId: string) {
    try {
      await dashboardApi.deleteTemplate(templateId)
      setTemplates((prev) => prev.filter((t) => t.id !== templateId))
    } catch {
      toast.error('Failed to delete template')
    }
  }

  function handleAddWidgetFromGallery(entry: WidgetCatalogItem, config: Record<string, unknown> = {}) {
    const maxBottom = editedWidgets.reduce((acc, w) => {
      const span = SIZE_TO_SPAN[w.size] ?? SIZE_TO_SPAN.medium
      return Math.max(acc, w.grid_y + span.h)
    }, 0)
    const newWidget: DashboardWidgetInstance = {
      instance_id: crypto.randomUUID(),
      type_key: entry.type_key,
      grid_x: 0,
      grid_y: maxBottom,
      size: (entry.allowed_sizes[0] ?? 'medium') as 'small' | 'medium' | 'large',
      minimized: false,
      config,
    }
    setEditedWidgets((prev) => [...prev, newWidget])
    setShowAddWidget(false)
  }

  async function handleDone() {
    setSaving(true)
    try {
      await dashboardApi.updateLayout(editedWidgets)
      await refetchLayout()
      setEditedWidgets([])
      setEditMode(false)
    } catch {
      toast.error('Failed to save layout')
    } finally {
      setSaving(false)
    }
  }

  const handleRemoveWidget = useCallback((instanceId: string) => {
    setEditedWidgets((prev) => prev.filter((w) => w.instance_id !== instanceId))
  }, [])

  const handleMinimizeWidget = useCallback((instanceId: string) => {
    setEditedWidgets((prev) =>
      prev.map((w) => (w.instance_id === instanceId ? { ...w, minimized: true } : w))
    )
  }, [])

  const handleExpandWidget = useCallback(
    async (instanceId: string) => {
      if (editMode) {
        setEditedWidgets((prev) =>
          prev.map((w) => (w.instance_id === instanceId ? { ...w, minimized: false } : w))
        )
        return
      }
      if (!widgets) return
      const updated = widgets.map((w) =>
        w.instance_id === instanceId ? { ...w, minimized: false } : w
      )
      try {
        await dashboardApi.updateLayout(updated)
        await refetchLayout()
      } catch {
        toast.error('Failed to expand widget')
      }
    },
    [editMode, widgets, refetchLayout]
  )

  // Sync grid_x / grid_y for all items whenever the grid layout changes (drag/compaction)
  const handleLayoutChange = useCallback(
    (newLayout: Layout) => {
      if (!editMode) return
      setEditedWidgets((prev) =>
        prev.map((w) => {
          const item = newLayout.find((l) => l.i === w.instance_id)
          if (!item) return w
          return { ...w, grid_x: item.x, grid_y: item.y }
        })
      )
    },
    [editMode]
  )

  // Snap resize to the nearest allowed size on release
  const handleResizeStop: EventCallback = useCallback(
    (_layout, _oldItem, newItem) => {
      if (!editMode || !newItem) return
      setEditedWidgets((prev) => {
        const widget = prev.find((w) => w.instance_id === newItem.i)
        if (!widget) return prev
        const catalogEntry = catalogByKey.get(widget.type_key)
        const allowedSizes = catalogEntry?.allowed_sizes ?? [widget.size]

        let closest = allowedSizes[0]
        let bestDist = Infinity
        for (const sizeName of allowedSizes) {
          const span = SIZE_TO_SPAN[sizeName]
          if (!span) continue
          const dist = Math.abs(newItem.w - span.w) + Math.abs(newItem.h - span.h)
          if (dist < bestDist) {
            bestDist = dist
            closest = sizeName
          }
        }

        return prev.map((w) =>
          w.instance_id === newItem.i
            ? { ...w, size: closest as 'small' | 'medium' | 'large' }
            : w
        )
      })
    },
    [editMode, catalogByKey]
  )

  if (layoutError) {
    return (
      <div className="p-6 flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <p className="text-[14px] text-foreground mb-3">Failed to load dashboard layout.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 flex flex-col gap-4">
        {/* Page header - always renders so edit controls are consistent */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-display font-medium text-brand dark:text-foreground">Dashboard</h1>
            <p className="text-[12px] text-muted-foreground mt-0.5">Priority work across all clients</p>
          </div>
          {!layoutLoading && widgets && (
            <div className="flex items-center gap-2">
              {editMode ? (
                <>
                  <button
                    onClick={() => setShowAddWidget(true)}
                    className="text-[13px] font-medium px-3.5 py-1.5 rounded border border-surface-border dark:border-dark-border text-foreground hover:bg-surface-input dark:hover:bg-dark-page transition-colors flex items-center gap-1.5"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    Add Widget
                  </button>
                  <button
                    onClick={() => void handleResetToDefault()}
                    disabled={saving}
                    className="text-[13px] font-medium px-3.5 py-1.5 text-muted-foreground hover:text-foreground disabled:opacity-50 transition-colors"
                  >
                    Reset to Default
                  </button>
                  {user?.role === 'firm_owner' && (
                    <button
                      onClick={() => void handleSaveAsFirmDefault()}
                      disabled={saving}
                      className="text-[13px] font-medium px-3.5 py-1.5 text-muted-foreground hover:text-foreground disabled:opacity-50 transition-colors"
                    >
                      Save as Firm Default
                    </button>
                  )}
                  <button
                    onClick={handleOpenSaveTemplate}
                    disabled={saving}
                    className="text-[13px] font-medium px-3.5 py-1.5 text-muted-foreground hover:text-foreground disabled:opacity-50 transition-colors"
                  >
                    Save as Template
                  </button>
                  <button
                    onClick={() => void handleOpenLoadTemplate()}
                    disabled={saving}
                    className="text-[13px] font-medium px-3.5 py-1.5 text-muted-foreground hover:text-foreground disabled:opacity-50 transition-colors"
                  >
                    Load Template
                  </button>
                  <button
                    onClick={handleCancel}
                    disabled={saving}
                    className="text-[13px] font-medium px-3.5 py-1.5 rounded border border-surface-border dark:border-dark-border text-foreground hover:bg-surface-input dark:hover:bg-dark-page disabled:opacity-50 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={() => void handleDone()}
                    disabled={saving}
                    className="text-[13px] font-medium px-3.5 py-1.5 rounded bg-brand text-white hover:opacity-90 disabled:opacity-50 transition-opacity"
                  >
                    {saving ? 'Saving...' : 'Done'}
                  </button>
                </>
              ) : (
                <button
                  onClick={handleEnterEdit}
                  className="text-[13px] font-medium px-3.5 py-1.5 rounded border border-surface-border dark:border-dark-border text-foreground hover:bg-surface-input dark:hover:bg-dark-page transition-colors"
                >
                  Edit Dashboard
                </button>
              )}
            </div>
          )}
        </div>

        {/* Concierge Spotlight - only once layout is loaded */}
        {!layoutLoading && widgets && <ConciergeSpotlight />}

        {/* Widget canvas - containerRef always in DOM so useContainerWidth measures on first render.
            Loading skeleton renders inside this div rather than as a separate early return. */}
        <div ref={containerRef} className="w-full">
          {layoutLoading || !widgets ? (
            <div className="flex flex-col gap-6">
              <div className="h-48 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded-[8px]" />
              <div className="h-64 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded-[8px]" />
              <div className="h-40 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded-[8px]" />
            </div>
          ) : (
            <GridLayout
              width={width}
              layout={layout}
              gridConfig={{ cols: 4, rowHeight: 80, margin: [16, 16], containerPadding: [0, 0] }}
              dragConfig={{ enabled: editMode }}
              resizeConfig={{ enabled: editMode, handles: ['se'] }}
              onLayoutChange={handleLayoutChange}
              onResizeStop={handleResizeStop}
            >
              {activeWidgets.map((widget) => (
                <div key={widget.instance_id}>
                  <div
                    style={{
                      overflow: 'hidden',
                      position: 'relative',
                      height: '100%',
                    }}
                  >
                    {widget.minimized ? (
                      <CollapsedWidgetHeader
                        displayName={catalogByKey.get(widget.type_key)?.display_name ?? widget.type_key}
                        onClick={() => void handleExpandWidget(widget.instance_id)}
                      />
                    ) : (
                      <>
                        <div style={{ pointerEvents: editMode ? 'none' : undefined, height: '100%' }}>
                          <WidgetRenderer widget={widget} />
                        </div>
                        {editMode && (
                          <WidgetEditOverlay
                            onRemove={() => handleRemoveWidget(widget.instance_id)}
                            onMinimize={() => handleMinimizeWidget(widget.instance_id)}
                          />
                        )}
                      </>
                    )}
                  </div>
                </div>
              ))}
            </GridLayout>
          )}
        </div>

      {/* Add Widget gallery modal */}
      {editMode && (
        <AddWidgetModal
          open={showAddWidget}
          onClose={() => setShowAddWidget(false)}
          catalog={catalog}
          onAdd={handleAddWidgetFromGallery}
          editedWidgets={editedWidgets}
        />
      )}

      {/* Save as Template name prompt */}
      <Modal open={showSaveTemplate} onClose={() => setShowSaveTemplate(false)} title="Save as Template" size="sm">
        <div className="flex flex-col gap-4">
          <input
            type="text"
            value={templateName}
            onChange={(e) => setTemplateName(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') void handleConfirmSaveTemplate() }}
            placeholder="Template name"
            autoFocus
            className="h-9 w-full px-3 rounded-[6px] text-[13px] bg-surface-input dark:bg-dark-card border border-[0.5px] border-surface-border dark:border-dark-border text-foreground outline-none focus:border-brand transition-colors"
          />
          <div className="flex justify-end gap-2">
            <button
              onClick={() => setShowSaveTemplate(false)}
              className="text-[13px] font-medium px-3.5 py-1.5 rounded border border-surface-border dark:border-dark-border text-foreground hover:bg-surface-input dark:hover:bg-dark-page transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={() => void handleConfirmSaveTemplate()}
              disabled={!templateName.trim()}
              className="text-[13px] font-medium px-3.5 py-1.5 rounded bg-brand text-white hover:opacity-90 disabled:opacity-50 transition-opacity"
            >
              Save
            </button>
          </div>
        </div>
      </Modal>

      {/* Load Template list */}
      <Modal open={showLoadTemplate} onClose={() => setShowLoadTemplate(false)} title="Load Template" size="sm">
        {templatesLoading ? (
          <p className="text-[13px] text-muted-foreground text-center py-6">Loading...</p>
        ) : templates.length === 0 ? (
          <p className="text-[13px] text-muted-foreground text-center py-6">No saved templates yet. Save the current arrangement as a template to get started.</p>
        ) : (
          <div className="flex flex-col divide-y divide-surface-border dark:divide-dark-border">
            {templates.map((tmpl) => (
              <div key={tmpl.id} className="flex items-center px-3 py-2.5 gap-3 border-2 border-transparent hover:border-brand-light dark:hover:border-white transition-colors">
                <button
                  onClick={() => handleSelectTemplate(tmpl)}
                  className="flex-1 text-left text-[13px] font-medium text-foreground hover:text-brand transition-colors truncate"
                >
                  {tmpl.name}
                </button>
                <button
                  onClick={() => void handleDeleteTemplate(tmpl.id)}
                  className="flex-shrink-0 text-muted-foreground hover:text-red-500 transition-colors"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            ))}
          </div>
        )}
      </Modal>

      {ConfirmDialog}
    </div>
  )
}
