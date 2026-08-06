// path: frontend/src/app/(app)/dashboard/page.tsx
'use client'

import { useState, useMemo, useCallback } from 'react'
import Link from 'next/link'
import { useQuery } from '@tanstack/react-query'
import { toast } from 'sonner'
import { CheckCircle, X, Minus, ChevronDown } from 'lucide-react'
import { GridLayout, useContainerWidth } from 'react-grid-layout'
import type { Layout, LayoutItem, EventCallback } from 'react-grid-layout'
import { dashboardApi } from '@/lib/api/dashboard'
import { reportsApi } from '@/lib/api/reports'
import type { DashboardWidgetInstance, OverdueEngagementItem, UpcomingDeadlineItem, StaffUtilizationItem, UnsignedDocumentItem, WidgetCatalogItem } from '@/lib/api/dashboard'
import type { WIPSummary } from '@/lib/api/reports'
import api from '@/lib/api'
import { formatEngagementType } from '@/lib/utils'
import { ConciergeSpotlight } from '@/components/dashboard/ConciergeSpotlight'

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
    queryFn: () => dashboardApi.getWidgetData(widget.type_key),
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
// Page
// ---------------------------------------------------------------------------

export default function DashboardPage() {
  const { width, containerRef, mounted } = useContainerWidth({ measureBeforeMount: true })


  const [editMode, setEditMode] = useState(false)
  const [editedWidgets, setEditedWidgets] = useState<DashboardWidgetInstance[]>([])
  const [saving, setSaving] = useState(false)

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

  if (layoutLoading || !widgets) {
    return (
      <div className="p-6 flex flex-col gap-6">
        <div>
          <h1 className="text-2xl font-display font-medium text-brand dark:text-foreground">Dashboard</h1>
          <p className="text-[12px] text-muted-foreground mt-0.5">Priority work across all clients</p>
        </div>
        <div className="h-48 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded-[8px]" />
        <div className="h-64 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded-[8px]" />
        <div className="h-40 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded-[8px]" />
      </div>
    )
  }

  return (
    <div className="p-6 flex flex-col gap-4">
        {/* Page header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-display font-medium text-brand dark:text-foreground">Dashboard</h1>
            <p className="text-[12px] text-muted-foreground mt-0.5">Priority work across all clients</p>
          </div>
          <div className="flex items-center gap-2">
            {editMode ? (
              <>
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
                  {saving ? 'Saving…' : 'Done'}
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
        </div>

        {/* Concierge Spotlight — fixed above the grid */}
        <ConciergeSpotlight />

        {/* Widget canvas */}
        <div ref={containerRef} className="w-full">
          {mounted && (
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
    </div>
  )
}
