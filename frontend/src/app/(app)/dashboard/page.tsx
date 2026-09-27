// path: frontend/src/app/(app)/dashboard/page.tsx
'use client'

import { useState, useEffect, useCallback } from 'react'
import { TrendingUp, TrendingDown, Settings2 } from 'lucide-react'
import { dashboardApi } from '@/lib/api/dashboard'
import type { DashboardMetrics, DashboardSectionItem, UpcomingDeadlineItem, UnsignedDocumentItem, StaffUtilizationItem } from '@/lib/api/dashboard'
import { BriefingCard } from '@/components/dashboard/BriefingCard'
import { DashboardCustomizePanel } from '@/components/dashboard/DashboardCustomizePanel'
import type { DashboardSection } from '@/components/dashboard/DashboardCustomizePanel'
import { formatCurrency, formatEngagementType } from '@/lib/utils'

// ---------------------------------------------------------------------------
// Section labels
// ---------------------------------------------------------------------------

const SECTION_LABELS: Record<string, string> = {
  morning_briefing:   'Morning Briefing',
  financial_stats:    'Financial Stats',
  work_in_progress:   'Work in Progress',
  staff_utilization:  'Staff Utilization',
  upcoming_deadlines: 'Upcoming Deadlines',
  awaiting_signature: 'Awaiting Signature',
}

const DEFAULT_SECTIONS: DashboardSectionItem[] = [
  { key: 'morning_briefing',   visible: true, order: 0 },
  { key: 'financial_stats',    visible: true, order: 1 },
  { key: 'work_in_progress',   visible: true, order: 2 },
  { key: 'staff_utilization',  visible: true, order: 3 },
  { key: 'upcoming_deadlines', visible: true, order: 4 },
  { key: 'awaiting_signature', visible: true, order: 5 },
]

// ---------------------------------------------------------------------------
// Trend arrow
// ---------------------------------------------------------------------------

function TrendBadge({ pct, direction }: { pct: number | null; direction: 'up' | 'down' | null }) {
  if (pct === null || direction === null) return null
  const isUp = direction === 'up'
  return (
    <span className={`flex items-center gap-0.5 text-[11px] font-medium ${
      isUp ? 'text-green-600 dark:text-green-400' : 'text-red-500 dark:text-red-400'
    }`}>
      {isUp ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
      {Math.abs(pct)}%
    </span>
  )
}

// ---------------------------------------------------------------------------
// Section components
// ---------------------------------------------------------------------------

interface WIPEngagement {
  engagement_id: string
  engagement_name: string
  client_name: string
  total_hours: number
  wip_value: number
}

function FinancialStats({ metrics }: { metrics: DashboardMetrics }) {
  return (
    <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
      {/* Revenue This Month */}
      <div className="bg-surface-card dark:bg-dark-card rounded-card border border-surface-border dark:border-dark-border p-6">
        <p className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] mb-3">Revenue This Month</p>
        <p className="text-[16px] font-semibold text-brand dark:text-[#EDEEF0] mb-1">{formatCurrency(metrics.mrr)}</p>
        <div className="min-h-[18px]">
          {metrics.mrr_trend_pct !== null
            ? <TrendBadge pct={metrics.mrr_trend_pct} direction={metrics.mrr_trend_direction} />
            : metrics.mrr_invoice_count > 0 && (
                <span className="text-[11px] text-[#6B7280]">
                  {metrics.mrr_invoice_count} invoice{metrics.mrr_invoice_count === 1 ? '' : 's'} paid
                </span>
              )
          }
        </div>
      </div>
      {/* Outstanding AR */}
      <div className="bg-surface-card dark:bg-dark-card rounded-card border border-surface-border dark:border-dark-border p-6">
        <p className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] mb-3">Outstanding AR</p>
        <p className="text-[16px] font-semibold text-brand dark:text-[#EDEEF0] mb-1">{formatCurrency(metrics.outstanding_ar)}</p>
        <div className="min-h-[18px]">
          <TrendBadge pct={metrics.ar_trend_pct} direction={metrics.ar_trend_direction} />
        </div>
      </div>
      {/* Unbilled WIP */}
      <div className="bg-surface-card dark:bg-dark-card rounded-card border border-surface-border dark:border-dark-border p-6">
        <p className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] mb-3">Unbilled WIP</p>
        <p className="text-[16px] font-semibold text-brand dark:text-[#EDEEF0] mb-1">{formatCurrency(metrics.wip_value)}</p>
        <div className="min-h-[18px]">
          <TrendBadge pct={metrics.wip_trend_pct} direction={metrics.wip_trend_direction} />
        </div>
      </div>
      {/* Overdue Engagements */}
      <div className="bg-surface-card dark:bg-dark-card rounded-card border border-surface-border dark:border-dark-border p-6">
        <p className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] mb-3">Overdue Engagements</p>
        <p className="text-[16px] font-semibold text-brand dark:text-[#EDEEF0] mb-1">{metrics.overdue_engagement_count}</p>
        <div className="min-h-[18px]">
          {metrics.oldest_overdue_days != null && (
            <span className="text-[11px] text-[#6B7280]">
              Oldest {metrics.oldest_overdue_days}d overdue
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

function WorkInProgress({ engagements }: { engagements: WIPEngagement[] }) {
  if (engagements.length === 0) {
    return <p className="text-[13px] text-[#6B7280]">No unbilled work in progress.</p>
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full table-fixed text-[13px]">
        <colgroup>
          <col style={{ width: '40%' }} />
          <col style={{ width: '30%' }} />
          <col style={{ width: '15%' }} />
          <col style={{ width: '15%' }} />
        </colgroup>
        <thead>
          <tr className="border-b-[3px] border-surface-border dark:border-dark-border">
            <th className="text-left text-[11px] font-semibold text-[#6B7280] uppercase tracking-[0.05em] pb-3">Description</th>
            <th className="text-left text-[11px] font-semibold text-[#6B7280] uppercase tracking-[0.05em] pb-3">Client</th>
            <th className="text-right text-[11px] font-semibold text-[#6B7280] uppercase tracking-[0.05em] pb-3">Hours</th>
            <th className="text-right text-[11px] font-semibold text-[#6B7280] uppercase tracking-[0.05em] pb-3">Value</th>
          </tr>
        </thead>
        <tbody>
          {engagements.map((e) => (
            <tr key={e.engagement_id} className="border-b border-surface-border dark:border-dark-border last:border-0">
              <td className="py-3.5 text-[#374151] dark:text-[#9CA3AF]">{e.engagement_name}</td>
              <td className="py-3.5 text-[#374151] dark:text-[#9CA3AF]">{e.client_name}</td>
              <td className="py-3.5 text-right text-[#374151] dark:text-[#9CA3AF]">{e.total_hours.toFixed(1)}</td>
              <td className="py-3.5 text-right text-[#374151] dark:text-[#9CA3AF]">{formatCurrency(e.wip_value)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

const STAFF_PREVIEW_COUNT = 5

function StaffUtilization({ staff }: { staff: StaffUtilizationItem[] }) {
  const [expanded, setExpanded] = useState(false)
  const visible = expanded ? staff : staff.slice(0, STAFF_PREVIEW_COUNT)
  const hasMore = staff.length > STAFF_PREVIEW_COUNT

  if (staff.length === 0) {
    return <p className="text-[13px] text-[#6B7280]">No staff to display.</p>
  }
  return (
    <div className="flex flex-col gap-3">
      {visible.map((s) => (
        <div key={String(s.user_id)}>
          <div className="flex items-center justify-between mb-1">
            <span className="text-[13px] text-[#374151] dark:text-[#9CA3AF]">{s.full_name}</span>
            <span className="text-[12px] text-[#6B7280]">{Math.round(s.utilization_pct)}%</span>
          </div>
          <div className="h-1.5 w-full bg-[#E5E7EB] dark:bg-[#2A2A2A] rounded-full overflow-hidden">
            <div
              className="h-full rounded-full bg-brand dark:bg-brand-btn transition-all"
              style={{ width: `${Math.min(s.utilization_pct, 100)}%` }}
            />
          </div>
        </div>
      ))}
      {hasMore && (
        <button
          onClick={() => setExpanded((prev) => !prev)}
          className="mt-1 text-[12px] text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] transition-colors text-left"
        >
          {expanded ? 'Show fewer' : `View all ${staff.length} staff`}
        </button>
      )}
    </div>
  )
}

function UpcomingDeadlines({ deadlines }: { deadlines: UpcomingDeadlineItem[] }) {
  if (deadlines.length === 0) {
    return <p className="text-[13px] text-[#6B7280]">No upcoming deadlines in the next 14 days.</p>
  }
  return (
    <div className="flex flex-col">
      {deadlines.map((d) => (
        <div key={String(d.engagement_id)} className="flex items-center justify-between py-2.5 border-b border-surface-border dark:border-dark-border last:border-0">
          <div>
            <p className="text-[13px] text-brand dark:text-[#EDEEF0]">{d.client_name}</p>
            <p className="text-[11px] text-[#6B7280]">{formatEngagementType(d.engagement_type)}</p>
          </div>
          <div className="text-right">
            <p className="text-[12px] text-[#374151] dark:text-[#9CA3AF]">{d.deadline}</p>
            <p className="text-[11px] text-[#6B7280]">{d.days_until === 0 ? 'Today' : `${d.days_until}d`}</p>
          </div>
        </div>
      ))}
    </div>
  )
}

function AwaitingSignature({ documents }: { documents: UnsignedDocumentItem[] }) {
  if (documents.length === 0) {
    return <p className="text-[13px] text-[#6B7280]">No documents awaiting signature.</p>
  }
  return (
    <div className="flex flex-col">
      {documents.map((d) => (
        <div key={String(d.envelope_id)} className="flex items-center justify-between py-2.5 border-b border-surface-border dark:border-dark-border last:border-0">
          <div>
            <p className="text-[13px] text-brand dark:text-[#EDEEF0]">{d.document_title}</p>
            <p className="text-[11px] text-[#6B7280]">{d.client_name}</p>
          </div>
          <p className="text-[12px] text-[#6B7280] flex-shrink-0">{d.days_waiting}d waiting</p>
        </div>
      ))}
    </div>
  )
}

function SectionCard({ title, children }: { title?: string; children: React.ReactNode }) {
  return (
    <div className="bg-surface-card dark:bg-dark-card rounded-card border border-surface-border dark:border-dark-border p-5">
      {title && (
        <h2 className="text-[13px] font-semibold text-brand dark:text-[#EDEEF0] mb-4">{title}</h2>
      )}
      {children}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function DashboardPage() {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null)
  const [sections, setSections] = useState<DashboardSectionItem[]>(DEFAULT_SECTIONS)
  const [loading, setLoading] = useState(true)
  const [customizeOpen, setCustomizeOpen] = useState(false)

  const load = useCallback(async () => {
    try {
      const [m, s] = await Promise.all([
        dashboardApi.getMetrics(),
        dashboardApi.getSections(),
      ])
      setMetrics(m)
      setSections(s)
    } catch {
      // non-fatal: show with defaults
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  async function handleSaveSections(updated: DashboardSection[]) {
    const payload: DashboardSectionItem[] = updated.map((s) => ({
      key: s.key,
      visible: s.visible,
      order: s.order,
    }))
    setSections(payload)
    try {
      await dashboardApi.updateSections(payload)
    } catch {
      // persist failed silently
    }
  }

  const orderedSections = [...sections].sort((a, b) => a.order - b.order)
  const customizeSections: DashboardSection[] = orderedSections.map((s) => ({
    ...s,
    label: SECTION_LABELS[s.key] ?? s.key,
  }))

  if (loading) {
    return (
      <div className="p-6 flex flex-col gap-6">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-32 bg-surface-card dark:bg-dark-card rounded-card border border-surface-border dark:border-dark-border animate-pulse" />
        ))}
      </div>
    )
  }

  function renderSection(key: string) {
    if (!metrics) return null
    switch (key) {
      case 'morning_briefing':
        return <BriefingCard key="morning_briefing" />
      case 'financial_stats':
        return <FinancialStats key="financial_stats" metrics={metrics} />
      case 'work_in_progress':
        return (
          <SectionCard key="work_in_progress" title="Work in Progress">
            <WorkInProgress engagements={metrics.top_engagements ?? []} />
          </SectionCard>
        )
      case 'staff_utilization':
        return (
          <SectionCard key="staff_utilization" title="Staff Utilization">
            <StaffUtilization staff={metrics.staff_utilization} />
          </SectionCard>
        )
      case 'upcoming_deadlines':
        return (
          <SectionCard key="upcoming_deadlines" title="Upcoming Deadlines">
            <UpcomingDeadlines deadlines={metrics.upcoming_deadlines} />
          </SectionCard>
        )
      case 'awaiting_signature':
        return (
          <SectionCard key="awaiting_signature" title="Awaiting Signature">
            <AwaitingSignature documents={metrics.unsigned_documents} />
          </SectionCard>
        )
      default:
        return null
    }
  }

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-[22px] font-semibold text-brand dark:text-[#EDEEF0]">Dashboard</h1>
        <button
          onClick={() => setCustomizeOpen(true)}
          className="flex items-center gap-1.5 text-[13px] text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] transition-colors"
        >
          <Settings2 className="h-3.5 w-3.5" />
          Customize
        </button>
      </div>

      {/* Sections */}
      <div className="flex flex-col gap-6">
        {orderedSections
          .filter((s) => s.visible)
          .map((s) => renderSection(s.key))
        }
      </div>

      {/* Customize panel */}
      <DashboardCustomizePanel
        isOpen={customizeOpen}
        onClose={() => setCustomizeOpen(false)}
        sections={customizeSections}
        onSave={handleSaveSections}
      />
    </div>
  )
}
