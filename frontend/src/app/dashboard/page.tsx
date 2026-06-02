// path: frontend/src/app/dashboard/page.tsx
'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useQuery } from '@tanstack/react-query'
import { toast } from 'sonner'
import { CheckCircle } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
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
    <div className="bg-white dark:bg-dark-card rounded-[8px] p-5 border border-surface-border dark:border-dark-border flex flex-col gap-1">
      <span className="text-[12px] text-[#6B7280]">{label}</span>
      <span className={`text-[28px] font-medium leading-none ${valueClassName ?? 'text-brand dark:text-[#EDEEF0]'}`}>
        {value}
      </span>
      {subtext && <span className="text-[11px] text-[#6B7280] mt-0.5">{subtext}</span>}
    </div>
  )
}

function MetricCardSkeleton() {
  return (
    <div className="bg-white dark:bg-dark-card rounded-[8px] p-5 border border-surface-border dark:border-dark-border flex flex-col gap-2">
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
    <div className="bg-white dark:bg-dark-card rounded-[8px] border border-surface-border dark:border-dark-border overflow-hidden">
      <div className="px-4 py-3 border-b border-surface-border dark:border-dark-border">
        <span className="text-[13px] font-medium text-[#111827] dark:text-[#EDEEF0]">Upcoming Deadlines</span>
      </div>
      {items.length === 0 ? (
        <div className="px-4 py-8 text-center">
          <p className="text-[13px] text-green-600 dark:text-green-400 font-medium">No deadlines in the next 14 days.</p>
          <p className="text-[12px] text-[#6B7280] mt-1">Your runway is clear — keep it that way.</p>
        </div>
      ) : (
        <div className="divide-y divide-surface-border dark:divide-dark-border">
          {items.map((item) => (
            <div key={item.engagement_id} className="flex items-center px-4 py-2.5 gap-3">
              <div className="flex-1 min-w-0">
                <p className="text-[13px] font-medium text-[#111827] dark:text-[#EDEEF0] truncate">{item.client_name}</p>
              </div>
              <p className="text-[12px] text-[#6B7280] truncate flex-shrink-0">{formatEngagementType(item.engagement_type)}</p>
              <p className="text-[12px] text-[#6B7280] flex-shrink-0 w-24 text-right">{item.deadline}</p>
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
    <div className="bg-white dark:bg-dark-card rounded-[8px] border border-surface-border dark:border-dark-border overflow-hidden">
      <div className="px-4 py-3 border-b border-surface-border dark:border-dark-border">
        <div className="h-4 w-36 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
      </div>
      <div className="divide-y divide-surface-border dark:divide-dark-border">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="flex items-center px-4 py-3 gap-3">
            <div className="flex-1 h-4 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
            <div className="h-4 w-20 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
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
    <div className="bg-white dark:bg-dark-card rounded-[8px] border border-surface-border dark:border-dark-border overflow-hidden">
      <div className="px-4 py-3 border-b border-surface-border dark:border-dark-border">
        <span className="text-[13px] font-medium text-[#111827] dark:text-[#EDEEF0]">Staff Utilization</span>
      </div>
      {items.length === 0 ? (
        <div className="px-4 py-8 text-center">
          <p className="text-[12px] text-[#6B7280]">No time logged this week.</p>
        </div>
      ) : (
        <div className="px-4 py-3 flex flex-col gap-3">
          {items.map((item) => (
            <div key={item.user_id}>
              <div className="flex justify-between mb-1">
                <span className="text-[12px] text-[#111827] dark:text-[#EDEEF0]">{item.full_name}</span>
                <span className="text-[12px] text-[#6B7280]">{Math.round(item.utilization_pct)}%</span>
              </div>
              <div className="h-2 w-full bg-[#E5E7EB] dark:bg-[#333333] rounded-full overflow-hidden">
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
    <div className="bg-white dark:bg-dark-card rounded-[8px] border border-surface-border dark:border-dark-border overflow-hidden">
      <div className="px-4 py-3 border-b border-surface-border dark:border-dark-border">
        <div className="h-4 w-32 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
      </div>
      <div className="px-4 py-3 flex flex-col gap-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i}>
            <div className="h-3 w-28 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded mb-2" />
            <div className="h-2 w-full bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded-full" />
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
    <div className="bg-white dark:bg-dark-card rounded-[8px] border border-surface-border dark:border-dark-border overflow-hidden">
      <div className="px-4 py-3 border-b border-surface-border dark:border-dark-border flex items-center gap-2">
        <span className="text-[13px] font-medium text-[#111827] dark:text-[#EDEEF0]">Overdue Engagements</span>
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
              <tr className="border-b border-surface-border dark:border-dark-border text-[#6B7280]">
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
                  <td className="px-4 py-2.5 font-medium text-[#111827] dark:text-[#EDEEF0]">{item.client_name}</td>
                  <td className="px-4 py-2.5 text-[#6B7280]">{formatEngagementType(item.engagement_type)}</td>
                  <td className="px-4 py-2.5 text-[#6B7280]">{item.deadline}</td>
                  <td className="px-4 py-2.5">
                    <span className="font-medium text-[#DC2626]">{item.days_overdue}d</span>
                  </td>
                  <td className="px-4 py-2.5 text-[#6B7280]">{item.assigned_staff_name ?? '—'}</td>
                  <td className="px-4 py-2.5">
                    <button
                      onClick={() => handleComplete(item.engagement_id)}
                      disabled={completing === item.engagement_id}
                      className="text-[11px] font-medium px-2.5 py-1 rounded border border-surface-border dark:border-dark-border text-[#374151] dark:text-[#D1D5DB] hover:bg-[#F9FAFB] dark:hover:bg-[#2A2A2A] disabled:opacity-50 transition-colors"
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

function UnsignedDocumentsTable({ items }: { items: UnsignedDocumentItem[] }) {
  const [sending, setSending] = useState<string | null>(null)

  async function handleRemind(envelopeId: string) {
    setSending(envelopeId)
    try {
      await api.post(`/esign/envelopes/${envelopeId}/remind`)
      toast.success('Reminder sent')
    } catch {
      toast.error('Failed to send reminder')
    } finally {
      setSending(null)
    }
  }

  return (
    <div className="bg-white dark:bg-dark-card rounded-[8px] border border-surface-border dark:border-dark-border overflow-hidden">
      <div className="px-4 py-3 border-b border-surface-border dark:border-dark-border flex items-center gap-2">
        <span className="text-[13px] font-medium text-[#111827] dark:text-[#EDEEF0]">Awaiting Signature</span>
        {items.length > 0 && (
          <span className="text-[11px] font-medium px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
            {items.length}
          </span>
        )}
      </div>
      {items.length === 0 ? (
        <div className="px-4 py-8 text-center">
          <p className="text-[12px] text-[#6B7280]">No documents awaiting signature.</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-[12px]">
            <thead>
              <tr className="border-b border-surface-border dark:border-dark-border text-[#6B7280]">
                <th className="px-4 py-2 text-left font-medium">Client</th>
                <th className="px-4 py-2 text-left font-medium">Document</th>
                <th className="px-4 py-2 text-left font-medium">Sent</th>
                <th className="px-4 py-2 text-left font-medium">Days Waiting</th>
                <th className="px-4 py-2 text-left font-medium">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border dark:divide-dark-border">
              {items.map((item) => (
                <tr key={item.envelope_id}>
                  <td className="px-4 py-2.5 font-medium text-[#111827] dark:text-[#EDEEF0]">{item.client_name}</td>
                  <td className="px-4 py-2.5 text-[#6B7280]">{item.document_title || '—'}</td>
                  <td className="px-4 py-2.5 text-[#6B7280]">{new Date(item.sent_at).toLocaleDateString()}</td>
                  <td className="px-4 py-2.5 text-[#6B7280]">{item.days_waiting}d</td>
                  <td className="px-4 py-2.5">
                    <button
                      onClick={() => handleRemind(item.envelope_id)}
                      disabled={sending === item.envelope_id}
                      className="text-[11px] font-medium px-2.5 py-1 rounded border border-surface-border dark:border-dark-border text-brand dark:text-[#EDEEF0] hover:bg-surface-card dark:hover:bg-dark-card disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      {sending === item.envelope_id ? 'Sending...' : 'Send Reminder'}
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
// WIP Widget
// ---------------------------------------------------------------------------

function WIPWidget() {
  const { data, isLoading, isError } = useQuery<WIPSummary>({
    queryKey: ['wip-summary'],
    queryFn: reportsApi.getWip,
    staleTime: 5 * 60 * 1000,
  })

  return (
    <div className="bg-white dark:bg-dark-card rounded-[8px] border border-surface-border dark:border-dark-border overflow-hidden">
      <div className="px-4 py-3 border-b border-surface-border dark:border-dark-border flex items-start justify-between">
        <span className="text-[13px] font-medium text-[#111827] dark:text-[#EDEEF0]">Work in Progress</span>
        {isLoading ? (
          <div className="flex flex-col items-end gap-1">
            <div className="h-7 w-28 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
            <div className="h-3 w-20 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
          </div>
        ) : !isError && data ? (
          <div className="text-right">
            <p className="text-[22px] font-medium text-brand dark:text-[#EDEEF0] leading-none">{formatCurrency(data?.totalWipValue ?? 0)}</p>
            <p className="text-[11px] text-[#6B7280] mt-0.5">{data?.totalHours ?? 0} hrs unbilled</p>
          </div>
        ) : null}
      </div>
      {isLoading ? (
        <div className="divide-y divide-[#E5E7EB] dark:divide-[#333333]">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="flex items-center justify-between px-4 py-2.5">
              <div className="flex flex-col gap-1 flex-1">
                <div className="h-3.5 w-40 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                <div className="h-3 w-24 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
              </div>
              <div className="h-4 w-16 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
            </div>
          ))}
        </div>
      ) : isError ? (
        <div className="px-4 py-8 text-center">
          <p className="text-[12px] text-[#6B7280]">WIP data unavailable.</p>
        </div>
      ) : !data || (data?.topEngagements ?? []).length === 0 ? (
        <div className="px-4 py-8 text-center">
          <p className="text-[12px] text-[#6B7280]">No unbilled work in progress.</p>
        </div>
      ) : (
        <div className="divide-y divide-[#E5E7EB] dark:divide-[#333333]">
          {(data?.topEngagements ?? []).slice(0, 5).map((eng) => (
            <div key={eng.engagementId} className="flex items-center justify-between px-4 py-2.5">
              <div className="min-w-0 flex-1">
                <p className="text-[13px] font-medium text-[#111827] dark:text-[#EDEEF0] truncate">{eng.engagementName}</p>
                <p className="text-[11px] text-[#6B7280] truncate">{eng.clientName}</p>
              </div>
              <span className="text-[13px] font-medium text-[#92400E] dark:text-amber-400 ml-4 flex-shrink-0">
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
      <AppShell>
        <div className="p-6 flex items-center justify-center min-h-[400px]">
          <div className="text-center">
            <p className="text-[14px] text-[#374151] dark:text-[#D1D5DB] mb-3">Failed to load dashboard metrics.</p>
            <button
              onClick={() => refetch()}
              className="text-[13px] font-medium px-4 py-2 rounded-[6px] bg-brand text-white hover:opacity-90 transition-opacity"
            >
              Retry
            </button>
          </div>
        </div>
      </AppShell>
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
    <AppShell>
      <div className="p-6 flex flex-col gap-6">

        {/* Page header */}
        <div>
          <h1 className="text-2xl font-medium text-brand dark:text-[#EDEEF0]">Dashboard</h1>
          <p className="text-[12px] text-[#6B7280] mt-0.5">Priority work across all clients</p>
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
                    : 'text-brand dark:text-[#EDEEF0]'
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
          <UnsignedDocumentsTable items={metrics?.unsigned_documents} />
        )}

      </div>
    </AppShell>
  )
}
