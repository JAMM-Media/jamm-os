// path: frontend/src/app/dashboard/page.tsx
'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useQuery } from '@tanstack/react-query'
import { toast } from 'sonner'
import { CheckCircle } from 'lucide-react'
import { dashboardApi } from '@/lib/api/dashboard'
import { reportsApi } from '@/lib/api/reports'
import type { DashboardMetrics, OverdueEngagementItem, UpcomingDeadlineItem, StaffUtilizationItem, UnsignedDocumentItem } from '@/lib/api/dashboard'
import type { WIPSummary } from '@/lib/api/reports'
import api from '@/lib/api'
import { formatEngagementType } from '@/lib/utils'

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
}

function MetricCard({ label, value, subtext, valueClassName }: MetricCardProps) {
  return (
    <div className="bg-surface-card dark:bg-dark-card rounded-[8px] p-5 border border-surface-border dark:border-dark-border shadow-sm flex flex-col gap-1">
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
    <div className="bg-surface-card dark:bg-dark-card rounded-[8px] p-5 border border-surface-border dark:border-dark-border shadow-sm flex flex-col gap-2">
      <div className="h-3 w-24 bg-surface-border dark:bg-dark-border animate-pulse rounded" />
      <div className="h-8 w-32 bg-surface-border dark:bg-dark-border animate-pulse rounded" />
      <div className="h-3 w-20 bg-surface-border dark:bg-dark-border animate-pulse rounded" />
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
    <div className="bg-surface-card dark:bg-dark-card rounded-[8px] border border-surface-border dark:border-dark-border shadow-sm overflow-hidden">
      <div className="px-4 py-3 border-b border-surface-border dark:border-dark-border">
        <span className="text-[13px] font-medium text-foreground">Upcoming Deadlines</span>
      </div>
      {items.length === 0 ? (
        <div className="px-4 py-8 text-center">
          <p className="text-[13px] text-green-600 dark:text-green-400 font-medium">No deadlines in the next 14 days.</p>
          <p className="text-[12px] text-muted-foreground mt-1">Your runway is clear — keep it that way.</p>
        </div>
      ) : (
        <div className="divide-y divide-surface-border dark:divide-dark-border">
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
              View full calendar →
            </Link>
          </div>
        </div>
      )}
    </div>
  )
}

function UpcomingDeadlinesSkeleton() {
  return (
    <div className="bg-surface-card dark:bg-dark-card rounded-[8px] border border-surface-border dark:border-dark-border shadow-sm overflow-hidden">
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
    <div className="bg-surface-card dark:bg-dark-card rounded-[8px] border border-surface-border dark:border-dark-border shadow-sm overflow-hidden">
      <div className="px-4 py-3 border-b border-surface-border dark:border-dark-border">
        <span className="text-[13px] font-medium text-foreground">Staff Utilization</span>
      </div>
      {items.length === 0 ? (
        <div className="px-4 py-8 text-center">
          <p className="text-[12px] text-muted-foreground">No time logged this week.</p>
        </div>
      ) : (
        <div className="px-4 py-3 flex flex-col gap-3">
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
    <div className="bg-surface-card dark:bg-dark-card rounded-[8px] border border-surface-border dark:border-dark-border shadow-sm overflow-hidden">
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
    <div className="bg-surface-card dark:bg-dark-card rounded-[8px] border border-surface-border dark:border-dark-border shadow-sm overflow-hidden">
      <div className="px-4 py-3 border-b border-surface-border dark:border-dark-border flex items-center gap-2">
        <span className="text-[13px] font-medium text-foreground">Overdue Engagements</span>
        {items.length > 0 && (
          <span className="text-[11px] font-medium px-1.5 py-0.5 rounded bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">
            {items.length}
          </span>
        )}
      </div>
      {items.length === 0 ? (
        <div className="px-4 py-8 text-center flex flex-col items-center gap-2">
          <CheckCircle className="w-5 h-5 text-green-500" />
          <p className="text-[13px] text-green-600 dark:text-green-400 font-medium">Nothing overdue. Good work.</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
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
    <div className="bg-surface-card dark:bg-dark-card rounded-[8px] border border-surface-border dark:border-dark-border shadow-sm overflow-hidden">
      <div className="px-4 py-3 border-b border-surface-border dark:border-dark-border flex items-center gap-2">
        <span className="text-[13px] font-medium text-foreground">Awaiting Signature</span>
        {items.length > 0 && (
          <span className="text-[11px] font-medium px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
            {items.length}
          </span>
        )}
      </div>
      {items.length === 0 ? (
        <div className="px-4 py-8 text-center">
          <p className="text-[13px] text-green-600 dark:text-green-400 font-medium">All signatures are in.</p>
          <p className="text-[12px] text-muted-foreground mt-1">No envelopes are sitting unsigned across your clients.</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
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
// WIP Widget
// ---------------------------------------------------------------------------

function WIPWidget() {
  const { data, isLoading, isError } = useQuery<WIPSummary>({
    queryKey: ['wip-summary'],
    queryFn: reportsApi.getWip,
    staleTime: 5 * 60 * 1000,
  })

  return (
    <div className="bg-surface-card dark:bg-dark-card rounded-[8px] border border-surface-border dark:border-dark-border shadow-sm overflow-hidden">
      <div className="px-4 py-3 border-b border-surface-border dark:border-dark-border flex items-start justify-between">
        <span className="text-[13px] font-medium text-foreground">Work in Progress</span>
        {isLoading ? (
          <div className="flex flex-col items-end gap-1">
            <div className="h-7 w-28 bg-surface-border dark:bg-dark-border animate-pulse rounded" />
            <div className="h-3 w-20 bg-surface-border dark:bg-dark-border animate-pulse rounded" />
          </div>
        ) : !isError && data ? (
          <div className="text-right">
            <p className="text-[22px] font-display font-medium text-brand dark:text-foreground leading-none">{formatCurrency(data?.totalWipValue ?? 0)}</p>
            <p className="text-[11px] text-muted-foreground mt-0.5">{data?.totalHours ?? 0} hrs unbilled</p>
          </div>
        ) : null}
      </div>
      {isLoading ? (
        <div className="divide-y divide-surface-border dark:divide-dark-border">
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
        <div className="px-4 py-8 text-center">
          <p className="text-[12px] text-muted-foreground">WIP data unavailable.</p>
        </div>
      ) : !data || (data?.topEngagements ?? []).length === 0 ? (
        <div className="px-4 py-8 text-center">
          <p className="text-[13px] text-green-600 dark:text-green-400 font-medium">All billable work is accounted for.</p>
          <p className="text-[12px] text-muted-foreground mt-1">Nothing sitting uninvoiced right now.</p>
        </div>
      ) : (
        <div className="divide-y divide-surface-border dark:divide-dark-border">
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
// Page
// ---------------------------------------------------------------------------

export default function DashboardPage() {
  const {
    data: metrics,
    isLoading,
    isError,
    refetch,
  } = useQuery<DashboardMetrics>({
    queryKey: ['dashboard-metrics'],
    queryFn: () => dashboardApi.getMetrics(),
    staleTime: 60 * 1000,
  })

  // Track engagements that have been optimistically removed
  const [dismissedIds, setDismissedIds] = useState<Set<string>>(new Set())

  function handleEngagementComplete(id: string) {
    setDismissedIds((prev) => new Set([...prev, id]))
  }

  const visibleOverdue = (metrics?.overdue_engagements ?? []).filter(
    (e) => !dismissedIds.has(e.engagement_id)
  )

  if (isError) {
    return (
        <div className="p-6 flex items-center justify-center min-h-[400px]">
          <div className="text-center">
            <p className="text-[14px] text-foreground mb-3">Failed to load dashboard metrics.</p>
            <button
              onClick={() => refetch()}
              className="text-[13px] font-medium px-4 py-2 rounded-[6px] bg-brand text-white hover:opacity-90 transition-opacity"
            >
              Retry
            </button>
          </div>
        </div>
    )
  }

  if (!metrics) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-sm text-muted-foreground">Loading dashboard...</p>
      </div>
    )
  }

  return (
      <div className="p-6 flex flex-col gap-6">

        {/* Page header */}
        <div>
          <h1 className="text-2xl font-display font-medium text-brand dark:text-foreground">Dashboard</h1>
          <p className="text-[12px] text-muted-foreground mt-0.5">Priority work across all clients</p>
        </div>

        {/* ROW 1 — Stat cards */}
        <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
          {isLoading ? (
            Array.from({ length: 4 }).map((_, i) => <MetricCardSkeleton key={i} />)
          ) : (
            <>
              <MetricCard
                label="Revenue This Month"
                value={formatCurrency(metrics?.mrr)}
                subtext={`${metrics?.mrr_invoice_count} invoice${metrics?.mrr_invoice_count !== 1 ? 's' : ''} paid`}
              />
              <Link href="/billing" className="block hover:opacity-90 transition-opacity">
                <MetricCard
                  label="Outstanding AR"
                  value={formatCurrency(metrics?.outstanding_ar)}
                  subtext={
                    metrics?.oldest_overdue_days != null
                      ? `${metrics?.outstanding_ar_count} unpaid · Oldest: ${metrics?.oldest_overdue_days}d`
                      : `${metrics?.outstanding_ar_count} unpaid`
                  }
                />
              </Link>
              <MetricCard
                label="Unbilled WIP"
                value={formatCurrency(metrics?.wip_value)}
                subtext={`${metrics?.wip_hours.toFixed(1)} hours`}
              />
              <MetricCard
                label="Overdue Engagements"
                value={String(visibleOverdue.length)}
                valueClassName={
                  visibleOverdue.length > 0
                    ? 'text-[#DC2626]'
                    : 'text-brand dark:text-foreground'
                }
              />
            </>
          )}
        </div>

        {/* ROW WIP — Work in Progress */}
        <WIPWidget />

        {/* ROW 2 — Upcoming Deadlines + Staff Utilization */}
        <div className="flex gap-4">
          <div className="flex-[3]">
            {isLoading
              ? <UpcomingDeadlinesSkeleton />
              : <UpcomingDeadlinesList items={metrics?.upcoming_deadlines} />
            }
          </div>
          <div className="flex-[2]">
            {isLoading
              ? <StaffUtilizationSkeleton />
              : <StaffUtilizationPanel items={metrics?.staff_utilization} />
            }
          </div>
        </div>

        {/* ROW 3 — Overdue Engagements */}
        {!isLoading && (
          <OverdueEngagementsTable
            items={visibleOverdue}
            onComplete={handleEngagementComplete}
          />
        )}

        {/* ROW 4 — Awaiting Signature */}
        {!isLoading && (
          <UnsignedDocumentsTable
            items={metrics?.unsigned_documents ?? []}
            onActionComplete={() => refetch()}
          />
        )}

      </div>
  )
}
