// path: frontend/src/app/(app)/leads/[lead_id]/page.tsx
'use client'

import { useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { toast } from 'sonner'
import { Flame, Phone, FileText, Trophy } from 'lucide-react'
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

// Left border accent on the header card, matching StatusBadge color tokens.
const STAGE_LEFT_BORDER: Record<string, string> = {
  identified: 'border-l-[#9CA3AF]',
  contacted:  'border-l-[#F59E0B]',
  call_booked:'border-l-[#3B82F6]',
  proposal:   'border-l-[#1E40AF]',
  won:        'border-l-[#22C55E]',
  lost:       'border-l-[#EF4444]',
}

const labelClass = 'text-[11px] font-semibold text-[#9CA3AF] uppercase tracking-[0.07em]'
const valueClass = 'text-[14px] font-medium text-brand dark:text-[#EDEEF0] mt-0.5'
const sectionHeadClass = 'text-[11px] font-semibold text-[#9CA3AF] uppercase tracking-[0.07em] mb-4'

function formatDate(iso: string | null | undefined): string {
  if (!iso) return '-'
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function formatSource(raw: string | null): string {
  if (!raw) return '-'
  return raw.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}


const PIPELINE_STAGE_KEYS = ['identified', 'contacted', 'call_booked', 'proposal', 'won']
const PIPELINE_STAGE_SHORT: Record<string, string> = {
  identified: 'Identified',
  contacted: 'Contacted',
  call_booked: 'Call Booked',
  proposal: 'Proposal',
  won: 'Won',
}

function StageProgressBar({ stage }: { stage: string }) {
  const isLost = stage === 'lost'
  const currentIdx = PIPELINE_STAGE_KEYS.indexOf(stage)

  return (
    <div className="flex items-end gap-1 mb-5">
      {PIPELINE_STAGE_KEYS.map((s, idx) => {
        const isPast = !isLost && idx < currentIdx
        const isCurrent = !isLost && idx === currentIdx
        return (
          <div key={s} className="flex flex-col items-center gap-[5px]">
            <span className={cn(
              'text-[10px] whitespace-nowrap',
              isCurrent ? 'font-semibold text-brand dark:text-[#EDEEF0]' :
              isPast ? 'font-medium text-[#9CA3AF]' :
              'font-medium text-[#D1D5DB] dark:text-[#3D4654]',
            )}>
              {PIPELINE_STAGE_SHORT[s]}
            </span>
            <div className={cn(
              'h-1.5 w-14 rounded-sm transition-all',
              isCurrent ? 'bg-brand dark:bg-[#4A7FA5]' :
              isPast ? 'bg-[#93C5FD] dark:bg-[#3B5E7A]' :
              isLost ? 'bg-[#F3F4F6] dark:bg-[#252D3A]' :
              'bg-[#E5E7EB] dark:bg-[#2D3748]',
            )} />
          </div>
        )
      })}
      {isLost && (
        <div className="flex flex-col items-center gap-[5px] ml-1">
          <span className="text-[10px] font-semibold text-[#EF4444]">Lost</span>
          <div className="h-1.5 w-10 rounded-sm bg-[#EF4444] opacity-60" />
        </div>
      )}
    </div>
  )
}

function actionIcon(value: string) {
  if (value === 'call_booked') return <Phone className="h-3.5 w-3.5 flex-shrink-0" />
  if (value === 'proposal') return <FileText className="h-3.5 w-3.5 flex-shrink-0" />
  if (value === 'won') return <Trophy className="h-3.5 w-3.5 flex-shrink-0" />
  return null
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
      <div className="p-8">
        <div className="h-4 w-32 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded mb-8" />
        <div className="bg-white dark:bg-dark-card rounded-[10px] shadow-md p-6 mb-5">
          <div className="h-9 w-64 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded mb-3" />
          <div className="h-5 w-24 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
        </div>
      </div>
    )
  }

  if (!lead) {
    return (
      <div className="flex items-center justify-center h-full p-8">
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
      <div className="p-8 max-w-3xl">
        <div className="mb-6">
          <Breadcrumb
            items={[
              { label: 'Pipeline', href: '/leads' },
              { label: lead.name },
            ]}
          />
        </div>

        {/* Header card: name, stage, quick actions -- all in one place */}
        <div className={cn(
          'bg-white dark:bg-dark-card rounded-[10px] shadow-md overflow-hidden mb-5 border-l-4',
          STAGE_LEFT_BORDER[lead.stage] ?? 'border-l-[#9CA3AF]'
        )}>
          <div className="px-6 pt-6 pb-5">
            {/* Name + hot indicator */}
            <div className="flex items-start gap-3 mb-3">
              <h1 className="text-3xl font-bold tracking-tight text-brand dark:text-[#EDEEF0] leading-tight">
                {lead.name}
              </h1>
              {lead.hot && <Flame className="h-6 w-6 text-[#F59E0B] flex-shrink-0 mt-1" />}
            </div>

            {/* Stage + lost reason + time in stage */}
            <div className="flex items-center gap-2 mb-3">
              <StatusBadge variant={lead.stage as BadgeVariant} />
              {lead.lostReason && (
                <span className="text-[12px] text-[#6B7280]">
                  {formatSource(lead.lostReason)}
                </span>
              )}

            </div>

            {/* Stage progress tracker */}
            <StageProgressBar stage={lead.stage} />

            {/* Quick actions live here, near the stage badge */}
            {lead.stage !== 'won' && (
              <div className="pt-4 border-t border-[0.5px] border-[#E8EDF3] dark:border-dark-border">
                {transitionStage !== 'lost' ? (
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
                          'rounded-[6px] text-[12px] font-semibold transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1.5',
                          action.style === 'primary' && 'h-9 px-5 bg-brand dark:bg-brand-btn text-white hover:opacity-90',
                          action.style === 'win'     && 'h-9 px-5 bg-status-green text-status-green-text hover:opacity-90',
                          action.style === 'danger'  && 'h-8 px-4 bg-[#FEF2F2] border border-[#FECACA] text-[#DC2626] hover:bg-[#FEE2E2] dark:bg-[#3B1818] dark:border-[#7F1D1D] dark:text-[#FCA5A5]',
                        )}
                      >
                        {action.style !== 'danger' && actionIcon(action.value)}
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
                        className="h-8 px-2.5 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border bg-white dark:bg-dark-page text-[12px] text-brand dark:text-[#EDEEF0] focus:outline-none focus:border-brand dark:focus:border-[#4A7FA5]"
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
                      className="h-8 px-4 rounded-[6px] text-[12px] font-semibold bg-[#FEF2F2] border border-[#FECACA] text-[#DC2626] hover:bg-[#FEE2E2] dark:bg-[#3B1818] dark:border-[#7F1D1D] dark:text-[#FCA5A5] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
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
          </div>
        </div>

        {/* Contact */}
        <div className="bg-white dark:bg-dark-card rounded-[10px] shadow-sm p-6 mb-4">
          <p className={sectionHeadClass}>Contact</p>
          <div className="grid grid-cols-2 gap-x-8 gap-y-5">
            <div>
              <p className={labelClass}>Email</p>
              <p className={valueClass}>{lead.email ?? '-'}</p>
            </div>
            <div>
              <p className={labelClass}>Phone</p>
              <p className={valueClass}>{lead.phone ?? '-'}</p>
            </div>
          </div>
        </div>

        {/* Details */}
        <div className="bg-white dark:bg-dark-card rounded-[10px] shadow-sm p-6 mb-5">
          <p className={sectionHeadClass}>Details</p>
          <div className="grid grid-cols-2 gap-x-8 gap-y-5">
            <div>
              <p className={labelClass}>Referral source</p>
              <p className={valueClass}>{formatSource(lead.referralSource)}</p>
            </div>
            <div>
              <p className={labelClass}>Hot lead</p>
              <p className={valueClass}>{lead.hot ? 'Yes' : 'No'}</p>
            </div>
            <div>
              <p className={labelClass}>Added</p>
              <p className={valueClass}>{formatDate(lead.createdAt)}</p>
            </div>
            {lead.serviceInterest && (
              <div>
                <p className={labelClass}>Service interest</p>
                <p className={valueClass}>{formatSource(lead.serviceInterest)}</p>
              </div>
            )}
            {lead.urgency && (
              <div>
                <p className={labelClass}>Urgency</p>
                <p className={valueClass}>{formatSource(lead.urgency)}</p>
              </div>
            )}
          </div>
        </div>

        {/* Activity placeholder */}
        <div className="bg-white dark:bg-dark-card rounded-[10px] shadow-sm p-6">
          <h2 className="text-[13px] font-semibold text-brand dark:text-[#EDEEF0] mb-1">Activity</h2>
          <p className="text-[12px] text-[#9CA3AF] text-center py-8">
            Activity will appear here.
          </p>
        </div>
      </div>
    </>
  )
}
