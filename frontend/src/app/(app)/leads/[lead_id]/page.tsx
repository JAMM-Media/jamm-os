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

const labelClass = 'text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em]'
const valueClass = 'text-[13px] text-brand dark:text-[#EDEEF0]'

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

  async function handleTransition() {
    if (!transitionStage) return

    if (transitionStage === 'lost' && !lostReason) {
      toast.error('Select a reason before marking as lost.')
      return
    }

    if (transitionStage === 'won') {
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
        transitionStage,
        transitionStage === 'lost' ? lostReason : undefined
      )
      toast.success(`Lead moved to ${transitionStage.replace(/_/g, ' ')}`)
      setTransitionStage('')
      setLostReason('')
      refetch()

      if (transitionStage === 'won') {
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

  const availableStages = LEAD_STAGES.filter((s) => s.value !== lead.stage)

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

        {/* Header */}
        <div className="flex items-start justify-between mb-6">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <h1 className="text-2xl font-medium text-brand dark:text-[#EDEEF0]">{lead.name}</h1>
              {lead.hot && <Flame className="h-5 w-5 text-[#F59E0B]" />}
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

        {/* Info card */}
        <div className="bg-surface-card dark:bg-dark-card rounded-[8px] p-4 mb-4">
          <div className="grid grid-cols-2 gap-x-6 gap-y-4">
            <div className="flex flex-col gap-1">
              <span className={labelClass}>Email</span>
              <span className={valueClass}>{lead.email ?? '-'}</span>
            </div>
            <div className="flex flex-col gap-1">
              <span className={labelClass}>Phone</span>
              <span className={valueClass}>{lead.phone ?? '-'}</span>
            </div>
            <div className="flex flex-col gap-1">
              <span className={labelClass}>Stage</span>
              <div className="w-fit">
                <StatusBadge variant={lead.stage as BadgeVariant} />
              </div>
            </div>
            <div className="flex flex-col gap-1">
              <span className={labelClass}>Hot lead</span>
              <span className={valueClass}>{lead.hot ? 'Yes' : 'No'}</span>
            </div>
            <div className="flex flex-col gap-1">
              <span className={labelClass}>Referral source</span>
              <span className={valueClass}>{formatSource(lead.referralSource)}</span>
            </div>
            <div className="flex flex-col gap-1">
              <span className={labelClass}>Added</span>
              <span className={valueClass}>{formatDate(lead.createdAt)}</span>
            </div>
            {lead.serviceInterest && (
              <div className="flex flex-col gap-1">
                <span className={labelClass}>Service interest</span>
                <span className={valueClass}>{formatSource(lead.serviceInterest)}</span>
              </div>
            )}
            {lead.urgency && (
              <div className="flex flex-col gap-1">
                <span className={labelClass}>Urgency</span>
                <span className={valueClass}>{formatSource(lead.urgency)}</span>
              </div>
            )}
          </div>
        </div>

        {/* Stage transition */}
        {lead.stage !== 'won' && (
          <div className="bg-surface-card dark:bg-dark-card rounded-[8px] p-4">
            <h2 className="text-[13px] font-medium text-brand dark:text-[#EDEEF0] mb-3">
              Move stage
            </h2>
            <div className="flex items-end gap-3 flex-wrap">
              <div className="flex flex-col gap-1">
                <label className={labelClass}>New stage</label>
                <select
                  value={transitionStage}
                  onChange={(e) => { setTransitionStage(e.target.value); setLostReason('') }}
                  className="h-8 px-2.5 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[12px] text-brand dark:text-[#EDEEF0] focus:outline-none focus:border-brand dark:focus:border-[#4A7FA5]"
                >
                  <option value="">Select stage...</option>
                  {availableStages.map((s) => (
                    <option key={s.value} value={s.value}>{s.label}</option>
                  ))}
                </select>
              </div>

              {transitionStage === 'lost' && (
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
              )}

              <button
                onClick={handleTransition}
                disabled={
                  !transitionStage ||
                  transitioning ||
                  (transitionStage === 'lost' && !lostReason)
                }
                className={cn(
                  'h-8 px-3 rounded-[6px] text-[12px] font-medium transition-colors',
                  transitionStage === 'won'
                    ? 'bg-status-green text-status-green-text hover:opacity-90'
                    : transitionStage === 'lost'
                    ? 'bg-status-red text-status-red-text hover:opacity-90'
                    : 'bg-brand dark:bg-brand-btn text-white hover:opacity-90',
                  'disabled:opacity-40 disabled:cursor-not-allowed'
                )}
              >
                {transitioning ? 'Moving...' : 'Move'}
              </button>
            </div>
          </div>
        )}
      </div>
    </>
  )
}
