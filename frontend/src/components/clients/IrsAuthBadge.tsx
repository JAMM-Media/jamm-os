// frontend/src/components/clients/IrsAuthBadge.tsx
'use client'
import { formatLocalDate } from '@/lib/utils'

import { useFetch } from '@/lib/hooks/useFetch'
import {
  irsAuthorizationsApi,
  type IrsAuthStatusResponse,
  type IrsAuthorizationRecord,
  type IrsAuthResolvedState,
} from '@/lib/api/irsAuthorizationsApi'
import {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
  TooltipProvider,
} from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'

type CompositeStatus =
  | 'active'
  | 'expiring_soon'
  | 'pending'
  | 'revoked'
  | 'expired'
  | 'none'

const STATUS_CONFIG: Record<
  CompositeStatus,
  { bg: string; text: string; label: string; border?: string }
> = {
  active: { bg: '#D1FAE5', text: '#065F46', label: 'IRS Auth: Active' },
  expiring_soon: { bg: '#FEF3C7', text: '#92400E', label: 'IRS Auth: Expiring Soon' },
  expired: { bg: '#FEE2E2', text: '#991B1B', label: 'IRS Auth: Expired' },
  revoked: { bg: '#FEE2E2', text: '#991B1B', label: 'IRS Auth: Revoked' },
  pending: { bg: '#DBEAFE', text: '#1E40AF', label: 'IRS Auth: Pending' },
  none: {
    bg: '#E5E7EB',
    text: '#1F3148',
    label: 'IRS Auth: None on File',
    border: '0.5px solid #1F3148',
  },
}

/** Worst first. Where the two form types disagree, the badge shows the worst. */
const STATUS_PRECEDENCE_WORST_FIRST: CompositeStatus[] = [
  'none',
  'expired',
  'revoked',
  'pending',
  'expiring_soon',
  'active',
]

const THIRTY_DAYS_MS = 30 * 24 * 60 * 60 * 1000

/**
 * Collapse one form type's resolved state into a badge status.
 *
 * The 'expiring_soon' distinction lives only here, on the client, because it
 * is a function of the current clock rather than of anything the backend
 * stored. Everything else is read straight off the resolved state.
 */
function statusForForm(
  state: IrsAuthResolvedState,
  expiresOn: string | null
): CompositeStatus {
  switch (state) {
    case 'lapsed':
      return 'expired'
    case 'revoked':
      return 'revoked'
    case 'pending':
      return 'pending'
    case 'none':
      return 'none'
    case 'active': {
      if (expiresOn !== null) {
        const expiry = new Date(expiresOn).getTime()
        const now = Date.now()
        if (expiry > now && expiry - now <= THIRTY_DAYS_MS) return 'expiring_soon'
      }
      return 'active'
    }
  }
}

function deriveStatus(res: IrsAuthStatusResponse | null): CompositeStatus {
  if (!res) return 'none'

  const perForm: CompositeStatus[] = [
    statusForForm(res.state_8821, res.expires_on_8821),
    statusForForm(res.state_2848, res.expires_on_2848),
  ]

  // A form type that has never existed does not drag the badge down. Most
  // clients only ever hold an 8821, so counting a missing 2848 as the worst
  // case would label every one of them "None on File" and reintroduce the
  // exact false statement this badge was fixed to stop making. 'none' is the
  // badge only when it is true of both form types.
  const present = perForm.filter((status) => status !== 'none')
  if (present.length === 0) return 'none'

  return present.reduce((worst, status) =>
    STATUS_PRECEDENCE_WORST_FIRST.indexOf(status) <
    STATUS_PRECEDENCE_WORST_FIRST.indexOf(worst)
      ? status
      : worst
  )
}

function fmtDate(dateStr: string): string {
  return formatLocalDate(dateStr, { month: 'short', day: 'numeric', year: 'numeric' })
}

function daysUntil(dateStr: string): number {
  return Math.ceil((new Date(dateStr).getTime() - Date.now()) / (1000 * 60 * 60 * 24))
}

const STATE_LABEL: Record<Exclude<IrsAuthResolvedState, 'none'>, string> = {
  active: 'Active',
  pending: 'Awaiting signature',
  lapsed: 'Expired',
  revoked: 'Revoked',
}

interface FormEntry {
  type: '8821' | '2848'
  state: Exclude<IrsAuthResolvedState, 'none'>
  rec: IrsAuthorizationRecord
  expiresOn: string | null
}

function collectEntries(res: IrsAuthStatusResponse | null): FormEntry[] {
  if (!res) return []
  const entries: FormEntry[] = []
  const source = [
    { type: '8821' as const, state: res.state_8821, rec: res['8821'], expiresOn: res.expires_on_8821 },
    { type: '2848' as const, state: res.state_2848, rec: res['2848'], expiresOn: res.expires_on_2848 },
  ]
  for (const item of source) {
    // state 'none' and a null record are the same condition, but the record
    // is what the body actually renders, so narrow on it.
    if (item.state === 'none' || item.rec === null) continue
    entries.push({ type: item.type, state: item.state, rec: item.rec, expiresOn: item.expiresOn })
  }
  return entries
}

function TooltipBody({ res }: { res: IrsAuthStatusResponse | null }) {
  const entries = collectEntries(res)

  if (entries.length === 0) {
    return (
      <span style={{ fontSize: 11, color: '#EDEEF0' }}>
        No IRS authorization on file.
      </span>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {entries.map(({ type, state, rec, expiresOn }) => (
        <div key={type} style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <span style={{ fontSize: 12, fontWeight: 500, color: '#EDEEF0' }}>
            Form {type}
          </span>
          <span style={{ fontSize: 11, color: '#9CA3AF' }}>
            {STATE_LABEL[state]}
          </span>
          {expiresOn &&
            (state === 'lapsed' ? (
              // Never "(-412 days)". A lapse is stated as a past event.
              <span style={{ fontSize: 11, color: '#9CA3AF' }}>
                Expired {fmtDate(expiresOn)}
              </span>
            ) : (
              <span style={{ fontSize: 11, color: '#9CA3AF' }}>
                Expires {fmtDate(expiresOn)} ({daysUntil(expiresOn)} days)
              </span>
            ))}
          {rec.tax_years && rec.tax_years.length > 0 && (
            <span style={{ fontSize: 11, color: '#9CA3AF' }}>
              Tax years: {rec.tax_years.join(', ')}
            </span>
          )}
        </div>
      ))}
    </div>
  )
}

interface IrsAuthBadgeProps {
  clientId: string
  onClick?: () => void
  className?: string
}

export function IrsAuthBadge({ clientId, onClick, className }: IrsAuthBadgeProps) {
  const { data: statusRes, isLoading } = useFetch(
    () =>
      irsAuthorizationsApi
        .checkClientStatus(clientId)
        .then((r) => r.data as IrsAuthStatusResponse),
    [clientId]
  )

  if (isLoading) {
    return (
      <div
        style={{ width: 72, height: 22, borderRadius: 9999 }}
        className={cn('bg-[#D5D8DE] dark:bg-[#444444] animate-pulse', className)}
      />
    )
  }

  const status = deriveStatus(statusRes)
  const config = STATUS_CONFIG[status]

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger
          onClick={(e: React.MouseEvent) => {
            e.stopPropagation()
            onClick?.()
          }}
          style={{
            height: 22,
            fontSize: 11,
            fontWeight: 500,
            borderRadius: 9999,
            padding: '0 10px',
            background: config.bg,
            color: config.text,
            border: config.border ?? 'none',
            cursor: 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
            whiteSpace: 'nowrap',
          }}
          className={className}
        >
          {config.label}
        </TooltipTrigger>
        <TooltipContent
          side="bottom"
          className="bg-[#1F3148] text-[#EDEEF0] rounded-[6px] py-2 px-3 max-w-[240px] flex-col items-start gap-0"
        >
          <TooltipBody res={statusRes} />
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
