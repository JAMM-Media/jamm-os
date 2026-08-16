// path: frontend/src/app/(app)/leads/[lead_id]/page.tsx
'use client'

import { useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { toast } from 'sonner'
import { Flame } from 'lucide-react'
import { leadsApi } from '@/lib/api'
import { useFetch } from '@/lib/hooks/useFetch'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { Breadcrumb } from '@/components/layout/Breadcrumb'
import { useConfirm } from '@/lib/hooks/useConfirm'
import { cn } from '@/lib/utils'
import type { BadgeVariant } from '@/components/ui/StatusBadge'

const LEAD_STAGES = [
  { value: 'identified', label: 'Identified' },
  { value: 'contacted', label: 'Contacted' },
  { value: 'call_booked', label: 'Call Booked' },
  { value: 'proposal', label: 'Proposal' },
  { value: 'won', label: 'Won' },
  { value: 'lost', label: 'Lost' },
]

const LOST_REASONS = [
  { value: 'unqualified', label: 'Unqualified' },
  { value: 'unresponsive', label: 'Unresponsive' },
  { value: 'chose_competitor', label: 'Chose Competitor' },
  { value: 'price', label: 'Price' },
  { value: 'timing', label: 'Timing' },
  { value: 'other', label: 'Other' },
]

// Realistic next steps per stage. Won always uses the confirm gate.
// Lost always shows the reason picker. Everything else is a direct transition.
type QuickAction = { value: string; label: string; style: 'primary' | 'win' | 'danger' }
const QUICK_TRANSITIONS: Record<string, QuickAction[]> = {
  identified: [
    { value: 'contacted',   label: 'Mark Contacted', style: 'primary' },
    { value: 'lost',        label: 'Mark Lost',       style: 'danger'  },
  ],
  contacted: [
    { value: 'call_booked', label: 'Book Call',       style: 'primary' },
    { value: 'lost',        label: 'Mark Lost',       style: 'danger'  },
  ],
  call_booked: [
    { value: 'proposal',   label: 'Send Proposal',   style: 'primary' },
    { value: 'won',        label: 'Mark Won',         style: 'win'     },
    { value: 'lost',       label: 'Mark Lost',        style: 'danger'  },
  ],
  proposal: [
    { value: 'won',        label: 'Mark Won',         style: 'win'     },
    { value: 'lost',       label: 'Mark Lost',        style: 'danger'  },
  ],
  lost: [
    { value: 'contacted',  label: 'Reopen',           style: 'primary' },
  ],
}

// Top accent strip color per stage, matching StatusBadge color tokens.
const STAGE_ACCENT_BG: Record<string, string> = {
  identified: 'bg-[#9CA3AF]',
  contacted:  'bg-[#F59E0B]',
  call_booked:'bg-[#3B82F6]',
  proposal:   'bg-[#1E40AF]',
  won:        'bg-[#22C55E]',
  lost:       'bg-[#EF4444]',
}

const labelClass = 'text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em]'
const valueClass = 'text-[13px] text-brand dark:text-[#EDEEF0]'
const sectionHeadClass = 'text-[11px] font-semibold text-[#6B7280] uppercase tracking-[0.06em] mb-3'

function formatDate(iso: string | null | undefined): string {
  if (!iso) return '-'
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function formatSource(raw: string | null): string {
  if (!raw) return '-'
  return raw.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

export default function LeadDetailPage() {
  const params = useParams()
  const router = useRouter()
  const leadId = params.lead_id as string

  const { confirm, ConfirmDialog } = useConfirm()

  const [transitionStage, setTransitionStage] = useState('')
  const [lostReason, setLostReason] = useState('')
  const [transitioning, setTransitioning] = useState(false)

  const { data: lead, isLoading, refetch } = useFetch(
    () => leadsApi.get(leadId),
    [leadId]
  )

  // stageOverride lets quick-action buttons bypass state latency.
  // All logic (confirm gate for won, lost_reason gate) is preserved exactly.
  async function handleTransition(stageOverride?: string) {
    const stage = stageOverride ?? transitionStage
    if (!stage) return

    if (stage === 'lost' && !lostReason) {
      toast.error('Select a reason before marking as lost.')
      return
    }

    if (stage === 'won') {
      const confirmed = await confirm({
        message:
          'Marking this lead as Won creates a real Client record from their information.\n\nThis action cannot be undone through this screen. A dedicated un-convert action would be required to reverse it.',
        confirmLabel: 'Mark as Won',
        cancelLabel: 'Cancel',
        destructive: true,
      })
      if (!confirmed) return
    }

    setTransitioning(true)
    try {
      await leadsApi.transition(
        leadId,
        stage,
        stage === 'lost' ? lostReason : undefined
      )
      toast.success(`Lead moved to ${stage.replace(/_/g, ' ')}`)
      setTransitionStage('')
      setLostReason('')
      refetch()

      if (stage === 'won') {
        router.push('/clients')
      }
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(detail ?? 'Failed to transition lead')
    } finally {
      setTransitioning(false)
    }
  }

  if (isLoading) {
    return (
      <div className="p-6">
        <div className="h-4 w-32 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded mb-6" />
        <div className="h-8 w-64 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded mb-2" />
        <div className="h-4 w-40 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
      </div>
    )
  }

  if (!lead) {
    return (
      <div className="flex items-center justify-center h-full p-6">
        <p className="text-[13px] text-[#6B7280]">Lead not found.</p>
      </div>
    )
  }

  const quickActions = QUICK_TRANSITIONS[lead.stage] ?? []
  const quickValues = new Set(quickActions.map((a) => a.value))
  const otherStages = LEAD_STAGES.filter(
    (s) => s.value !== lead.stage && !quickValues.has(s.value)
  )

  return (
    <>
      {ConfirmDialog}
      <div className="p-6">
        <Breadcrumb
          items={[
            { label: 'Pipeline', href: '/leads' },
            { label: lead.name },
          ]}
        />

        {/* Header card with stage-colored top accent */}
        <div className="bg-surface-card dark:bg-dark-card rounded-[8px] border border-[0.5px] border-surface-border dark:border-dark-border overflow-hidden mb-4">
          <div className={cn('h-[3px]', STAGE_ACCENT_BG[lead.stage] ?? 'bg-[#9CA3AF]')} />
          <div className="px-5 py-4 flex items-start justify-between">
            <div>
              <div className="flex items-center gap-2 mb-1.5">
                <h1 className="text-xl font-semibold text-brand dark:text-[#EDEEF0]">{lead.name}</h1>
                {lead.hot && <Flame className="h-4.5 w-4.5 text-[#F59E0B]" />}
              </div>
              <div className="flex items-center gap-2">
                <StatusBadge variant={lead.stage as BadgeVariant} />
                {lead.lostReason && (
                  <span className="text-[12px] text-[#6B7280]">
                    {formatSource(lead.lostReason)}
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Contact section */}
        <div className="bg-surface-card dark:bg-dark-card rounded-[8px] border border-[0.5px] border-surface-border dark:border-dark-border p-4 mb-3">
          <p className={sectionHeadClass}>Contact</p>
          <div className="grid grid-cols-2 gap-x-6 gap-y-3">
            <div className="flex flex-col gap-0.5">
              <span className={labelClass}>Email</span>
              <span className={valueClass}>{lead.email ?? '-'}</span>
            </div>
            <div className="flex flex-col gap-0.5">
              <span className={labelClass}>Phone</span>
              <span className={valueClass}>{lead.phone ?? '-'}</span>
            </div>
          </div>
        </div>

        {/* Details section */}
        <div className="bg-surface-card dark:bg-dark-card rounded-[8px] border border-[0.5px] border-surface-border dark:border-dark-border p-4 mb-4">
          <p className={sectionHeadClass}>Details</p>
          <div className="grid grid-cols-2 gap-x-6 gap-y-3">
            <div className="flex flex-col gap-0.5">
              <span className={labelClass}>Referral source</span>
              <span className={valueClass}>{formatSource(lead.referralSource)}</span>
            </div>
            <div className="flex flex-col gap-0.5">
              <span className={labelClass}>Hot lead</span>
              <span className={valueClass}>{lead.hot ? 'Yes' : 'No'}</span>
            </div>
            <div className="flex flex-col gap-0.5">
              <span className={labelClass}>Added</span>
              <span className={valueClass}>{formatDate(lead.createdAt)}</span>
            </div>
            {lead.serviceInterest && (
              <div className="flex flex-col gap-0.5">
                <span className={labelClass}>Service interest</span>
                <span className={valueClass}>{formatSource(lead.serviceInterest)}</span>
              </div>
            )}
            {lead.urgency && (
              <div className="flex flex-col gap-0.5">
                <span className={labelClass}>Urgency</span>
                <span className={valueClass}>{formatSource(lead.urgency)}</span>
              </div>
            )}
          </div>
        </div>

        {/* Stage transition */}
        {lead.stage !== 'won' && (
          <div className="bg-surface-card dark:bg-dark-card rounded-[8px] border border-[0.5px] border-surface-border dark:border-dark-border p-4 mb-4">
            <h2 className="text-[13px] font-medium text-brand dark:text-[#EDEEF0] mb-3">
              Move stage
            </h2>

            {transitionStage !== 'lost' ? (
              /* Quick action buttons */
              <div className="flex items-center gap-2 flex-wrap">
                {quickActions.map((action) => (
                  <button
                    key={action.value}
                    disabled={transitioning}
                    onClick={() => {
                      if (action.value === 'lost') {
                        setTransitionStage('lost')
                      } else {
                        handleTransition(action.value)
                      }
                    }}
                    className={cn(
                      'h-8 px-3 rounded-[6px] text-[12px] font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed',
                      action.style === 'primary' && 'bg-brand dark:bg-brand-btn text-white hover:opacity-90',
                      action.style === 'win'     && 'bg-status-green text-status-green-text hover:opacity-90',
                      action.style === 'danger'  && 'bg-[#FEF2F2] border border-[#FECACA] text-[#DC2626] hover:bg-[#FEE2E2] dark:bg-[#3B1818] dark:border-[#7F1D1D] dark:text-[#FCA5A5]',
                    )}
                  >
                    {transitioning ? '...' : action.label}
                  </button>
                ))}

                {otherStages.length > 0 && (
                  <select
                    value=""
                    disabled={transitioning}
                    onChange={(e) => {
                      const val = e.target.value
                      if (!val) return
                      if (val === 'lost') {
                        setTransitionStage('lost')
                      } else {
                        handleTransition(val)
                      }
                    }}
                    className="h-8 px-2.5 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[12px] text-[#6B7280] dark:text-[#9CA3AF] focus:outline-none focus:border-brand dark:focus:border-[#4A7FA5]"
                  >
                    <option value="">Other stage...</option>
                    {otherStages.map((s) => (
                      <option key={s.value} value={s.value}>{s.label}</option>
                    ))}
                  </select>
                )}
              </div>
            ) : (
              /* Lost reason picker -- same gate as before */
              <div className="flex items-end gap-3 flex-wrap">
                <div className="flex flex-col gap-1">
                  <label className={labelClass}>Reason (required)</label>
                  <select
                    value={lostReason}
                    onChange={(e) => setLostReason(e.target.value)}
                    className="h-8 px-2.5 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[12px] text-brand dark:text-[#EDEEF0] focus:outline-none focus:border-brand dark:focus:border-[#4A7FA5]"
                  >
                    <option value="">Select reason...</option>
                    {LOST_REASONS.map((r) => (
                      <option key={r.value} value={r.value}>{r.label}</option>
                    ))}
                  </select>
                </div>
                <button
                  onClick={() => handleTransition()}
                  disabled={!lostReason || transitioning}
                  className="h-8 px-3 rounded-[6px] text-[12px] font-medium bg-[#FEF2F2] border border-[#FECACA] text-[#DC2626] hover:bg-[#FEE2E2] dark:bg-[#3B1818] dark:border-[#7F1D1D] dark:text-[#FCA5A5] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {transitioning ? 'Marking...' : 'Confirm Lost'}
                </button>
                <button
                  onClick={() => { setTransitionStage(''); setLostReason('') }}
                  className="h-8 px-3 rounded-[6px] text-[12px] font-medium text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] transition-colors"
                >
                  Cancel
                </button>
              </div>
            )}
          </div>
        )}

        {/* Activity placeholder */}
        <div className="bg-surface-card dark:bg-dark-card rounded-[8px] border border-[0.5px] border-surface-border dark:border-dark-border p-4">
          <h2 className="text-[13px] font-medium text-brand dark:text-[#EDEEF0] mb-3">Activity</h2>
          <p className="text-[12px] text-[#9CA3AF] text-center py-6">
            Activity will appear here.
          </p>
        </div>
      </div>
    </>
  )
}
