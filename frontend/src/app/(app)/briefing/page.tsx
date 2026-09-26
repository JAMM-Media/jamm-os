// frontend/src/app/(app)/briefing/page.tsx
'use client'

import { useState, useRef, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ChevronDown } from 'lucide-react'
import { toast } from 'sonner'
import { useAuth } from '@/lib/hooks/useAuth'
import { Breadcrumb } from '@/components/layout/Breadcrumb'
import {
  surfaceItemsApi,
  type SurfaceItemOut,
  type SurfaceItemDetailOut,
  type DismissalReason,
} from '@/lib/api/surfaceItems'

// ---------------------------------------------------------------------------
// Navigation targets -- correction #7
// Signature types have no confirmed frontend destination; headlines are plain text.
// ---------------------------------------------------------------------------

const SIGNATURE_TYPES = new Set([
  'signature_stalled',
  'signature_declined',
  'signature_expired',
])

function getItemHref(item: SurfaceItemOut): string | null {
  const p = item.payload
  switch (item.item_type) {
    case 'invoice_overdue':
      return p.invoice_id ? `/billing/${p.invoice_id}` : null
    case 'irs_auth_expiring':
      return p.client_id ? `/clients/${p.client_id}?tab=irs-auth` : null
    case 'deadline_with_blockers':
      return p.engagement_id ? `/engagements/${p.engagement_id}` : null
    case 'work_unbilled':
      return p.engagement_id ? `/engagements/${p.engagement_id}` : null
    default:
      return null
  }
}

// ---------------------------------------------------------------------------
// Entity line -- correction #8
// deadline_with_blockers and work_unbilled prefer payload.engagement_name;
// all others use item.client_name directly.
// ---------------------------------------------------------------------------

function getEntityLine(item: SurfaceItemOut): string | null {
  if (
    item.item_type === 'deadline_with_blockers' ||
    item.item_type === 'work_unbilled'
  ) {
    return (item.payload.engagement_name as string | undefined) ?? item.client_name ?? null
  }
  return item.client_name ?? null
}

// ---------------------------------------------------------------------------
// Dismiss dropdown
// ---------------------------------------------------------------------------

const DISMISS_OPTIONS: { label: string; value: DismissalReason }[] = [
  { label: 'Not relevant', value: 'not_relevant' },
  { label: 'Already handling', value: 'already_handling' },
  { label: 'Wrong', value: 'was_wrong' },
]

interface DismissDropdownProps {
  onSelect: (reason: DismissalReason) => void
  disabled: boolean
}

function DismissDropdown({ onSelect, disabled }: DismissDropdownProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  return (
    <div ref={ref} className="relative">
      <button
        disabled={disabled}
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1 h-7 px-2.5 rounded border border-[0.5px] border-surface-border dark:border-dark-border text-[12px] text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] hover:border-brand-light transition-colors disabled:opacity-40 disabled:cursor-default"
        aria-label="Dismiss"
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        Dismiss
        <ChevronDown className="h-3 w-3" />
      </button>
      {open && (
        <div
          role="listbox"
          className="absolute right-0 top-full mt-1 w-44 bg-surface-page dark:bg-dark-page border border-[0.5px] border-surface-border dark:border-dark-border rounded-[6px] shadow-lg z-20 py-1"
        >
          {DISMISS_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              role="option"
              onClick={() => {
                setOpen(false)
                onSelect(opt.value)
              }}
              className="w-full text-left px-3 py-2 text-[12px] text-[#374151] dark:text-[#9CA3AF] hover:bg-surface-input dark:hover:bg-dark-card hover:text-brand dark:hover:text-[#EDEEF0] transition-colors"
            >
              {opt.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Detail field rendering
// ---------------------------------------------------------------------------

function DetailField({ label, value }: { label: string; value: string | number }) {
  const displayValue = String(value)
  const isMuted = displayValue === 'Not recorded' || displayValue === 'None recorded'
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[10px] font-bold uppercase tracking-wide text-[#6B7280]">{label}</span>
      <span className={`text-[12px] leading-snug ${isMuted ? 'text-[#9CA3AF]' : 'text-[#374151] dark:text-[#D1D5DB]'}`}>
        {displayValue}
      </span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Single briefing row
// ---------------------------------------------------------------------------

interface BriefingRowProps {
  item: SurfaceItemOut
  onDismiss: (id: string, reason: DismissalReason) => void
  onImplement: (id: string) => void
  actingId: string | null
}

function BriefingRow({ item, onDismiss, onImplement, actingId }: BriefingRowProps) {
  const href = getItemHref(item)
  const entityLine = getEntityLine(item)
  const isSignature = SIGNATURE_TYPES.has(item.item_type)
  const busy = actingId === item.id
  const [expanded, setExpanded] = useState(false)

  const { data: detail, isLoading: detailLoading } = useQuery<SurfaceItemDetailOut>({
    queryKey: ['item-detail', item.id],
    queryFn: () => surfaceItemsApi.getItemDetail(item.id),
    enabled: expanded,
    staleTime: 60_000 * 5,
    retry: false,
  })

  return (
    <div className="px-4 py-3.5 border-b-[0.5px] border-surface-border dark:border-dark-border last:border-0">
      <div className="flex items-start justify-between gap-4">
        <div className="flex flex-col gap-0.5 min-w-0 flex-1">
          {/* Headline: clickable link or plain text (per correction #7) */}
          {href && !isSignature ? (
            <a
              href={href}
              className="text-[14px] font-medium text-brand dark:text-[#EDEEF0] hover:underline"
            >
              {item.headline}
            </a>
          ) : (
            <span className="text-[14px] font-medium text-brand dark:text-[#EDEEF0]">
              {item.headline}
            </span>
          )}
          {entityLine && (
            <span className="text-[12px] text-[#6B7280]">{entityLine}</span>
          )}
          {expanded && detail && (
            <p className="text-[11px] text-[#6B7280] mt-0.5 leading-snug">
              {detail.issued_date}
              <span className="mx-1 opacity-40 select-none">·</span>
              {detail.days_overdue}
              <span className="mx-1 opacity-40 select-none">·</span>
              {detail.invoice_balance}
            </p>
          )}
        </div>

        {/* Actions: expand chevron + Implement + Dismiss */}
        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            onClick={() => setExpanded((v) => !v)}
            className="flex items-center justify-center h-7 w-7 rounded text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] transition-colors focus:outline-none"
            aria-label={expanded ? 'Collapse detail' : 'Expand detail'}
          >
            <ChevronDown className={`h-3.5 w-3.5 transition-transform duration-150 ${expanded ? 'rotate-180' : ''}`} />
          </button>
          <button
            disabled={busy}
            onClick={() => onImplement(item.id)}
            className="h-7 px-2.5 rounded bg-brand text-white text-[12px] font-medium hover:opacity-90 disabled:opacity-50 disabled:cursor-default transition-opacity"
          >
            Implement
          </button>
          <DismissDropdown
            disabled={busy}
            onSelect={(reason) => onDismiss(item.id, reason)}
          />
        </div>
      </div>

      {expanded && (
        <div className="mt-2 pt-2 border-t-[0.5px] border-surface-border dark:border-dark-border">
          {detailLoading ? (
            <div className="flex gap-6 w-full max-w-[900px]">
              <div className="flex-1 flex flex-col gap-2.5">
                {Array.from({ length: 6 }).map((_, i) => (
                  <div key={i} className="flex flex-col gap-1">
                    <div className="h-2 w-14 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                    <div className="h-3 w-24 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                  </div>
                ))}
              </div>
              <div className="flex-1 flex flex-col gap-2.5">
                {Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="flex flex-col gap-1">
                    <div className="h-2 w-14 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                    <div className="h-3 w-24 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                  </div>
                ))}
              </div>
            </div>
          ) : detail ? (
            <div className="flex gap-6 w-full max-w-[900px]">
              <div className="flex-1 flex flex-col gap-3">
                <DetailField label="Client" value={detail.client} />
                <DetailField label="Engagement" value={detail.engagement} />
                <DetailField label="Invoice / Balance" value={detail.invoice_balance} />
                <DetailField label="Days Overdue" value={detail.days_overdue} />
                <DetailField label="Current Workflow Status" value={detail.current_workflow_status.charAt(0).toUpperCase() + detail.current_workflow_status.slice(1)} />
                <DetailField label="Issued Date" value={detail.issued_date} />
              </div>
              <div className="flex-1 flex flex-col gap-3">
                <DetailField label="Assigned Staff" value={detail.assigned_staff} />
                <DetailField label="Last Client Communication" value={detail.last_client_communication} />
                <DetailField
                  label="Related Documents on File"
                  value={detail.related_documents_count === 0 ? 'None recorded' : String(detail.related_documents_count)}
                />
                <DetailField label="Open Items Already in the Record" value={detail.open_items} />
              </div>
            </div>
          ) : (
            <p className="text-[12px] text-[#6B7280]">Could not load detail. Please try again.</p>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function BriefingPage() {
  const { user, isLoading: authLoading } = useAuth()
  const queryClient = useQueryClient()
  const [actingId, setActingId] = useState<string | null>(null)
  const [promoting, setPromoting] = useState(false)

  // Role gate -- correction #11: only firm_owner or manager may view this page.
  const canView =
    user?.role === 'firm_owner' || user?.role === 'manager'

  const { data, isLoading, isError } = useQuery({
    queryKey: ['briefing'],
    queryFn: surfaceItemsApi.getBriefing,
    enabled: !authLoading && canView,
    staleTime: 30_000,
  })

  const dismissMut = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: DismissalReason }) =>
      surfaceItemsApi.dismissItem(id, reason),
    onMutate: ({ id }) => setActingId(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['briefing'] })
      queryClient.invalidateQueries({ queryKey: ['briefing-card'] })
    },
    onError: () => toast.error('Could not dismiss item. Please try again.'),
    onSettled: () => setActingId(null),
  })

  const implementMut = useMutation({
    mutationFn: (id: string) => surfaceItemsApi.implementItem(id),
    onMutate: (id) => setActingId(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['briefing'] })
      queryClient.invalidateQueries({ queryKey: ['briefing-card'] })
    },
    onError: () => toast.error('Could not mark item as implemented. Please try again.'),
    onSettled: () => setActingId(null),
  })

  async function handlePromoteNext() {
    setPromoting(true)
    try {
      const result = await surfaceItemsApi.promoteNext()
      if (!result.promoted) {
        toast.info('Nothing else is waiting right now.')
      }
      queryClient.invalidateQueries({ queryKey: ['briefing'] })
      queryClient.invalidateQueries({ queryKey: ['briefing-card'] })
    } catch {
      toast.error('Could not load next item. Please try again.')
    } finally {
      setPromoting(false)
    }
  }

  // Auth still loading
  if (authLoading) {
    return (
      <div className="p-6">
        <div className="h-4 w-40 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded mb-6" />
        <div className="h-8 w-64 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
      </div>
    )
  }

  // Access denied for staff
  if (!canView) {
    return (
      <div className="p-6">
        <p className="text-[14px] text-[#6B7280]">
          Morning Briefing is available to firm owners and managers only.
        </p>
      </div>
    )
  }

  return (
    <div className="p-6 flex flex-col gap-4">
      <Breadcrumb
        items={[
          { label: 'Dashboard', href: '/dashboard' },
          { label: 'Morning Briefing' },
        ]}
      />

      <div>
        <h1 className="text-[22px] font-medium text-brand dark:text-[#EDEEF0] mb-1">
          Morning Briefing
        </h1>
        <p className="text-[13px] text-[#6B7280]">
          Current items from your firm's records, refreshed each morning.
        </p>
      </div>

      {isLoading && (
        <div className="rounded-[8px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card overflow-hidden">
          {Array.from({ length: 3 }).map((_, i) => (
            <div
              key={i}
              className="flex items-center justify-between px-4 py-3.5 border-b border-[0.5px] border-surface-border dark:border-dark-border last:border-0"
            >
              <div className="flex flex-col gap-1.5 flex-1">
                <div className="h-3.5 w-64 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                <div className="h-3 w-32 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
              </div>
              <div className="flex gap-2">
                <div className="h-7 w-20 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                <div className="h-7 w-20 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
              </div>
            </div>
          ))}
        </div>
      )}

      {isError && (
        <p className="text-[13px] text-[#6B7280]">
          Could not load your briefing. Please refresh the page.
        </p>
      )}

      {!isLoading && !isError && data && (
        <>
          {data.items.length === 0 ? (
            // Empty state -- correction #6: exact copy required
            <p className="text-[14px] text-[#6B7280] py-4">
              You&apos;re all caught up. Check back tomorrow morning.
            </p>
          ) : (
            <>
              <div className="rounded-[8px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card overflow-hidden">
                {data.items.map((item) => (
                  <BriefingRow
                    key={item.id}
                    item={item}
                    actingId={actingId}
                    onDismiss={(id, reason) => dismissMut.mutate({ id, reason })}
                    onImplement={(id) => implementMut.mutate(id)}
                  />
                ))}
              </div>

              {/* Show next item affordance -- correction #9: manual only, never auto */}
              {data.items.length < 5 && (
                <div>
                  <button
                    onClick={handlePromoteNext}
                    disabled={promoting}
                    className="text-[13px] text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] transition-colors disabled:opacity-40"
                  >
                    {promoting ? 'Loading...' : 'Show next item'}
                  </button>
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  )
}
