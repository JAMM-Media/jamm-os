import { formatLocalDate } from '@/lib/utils'
// frontend/src/components/clients/IrsAuthBadge.tsx
'use client'

import { useFetch } from '@/lib/hooks/useFetch'
import {
  irsAuthorizationsApi,
  type IrsAuthStatusResponse,
  type IrsAuthorizationRecord,
} from '@/lib/api/irsAuthorizationsApi'
import {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
  TooltipProvider,
} from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'

type CompositeStatus = 'active' | 'expiring_soon' | 'expired' | 'pending' | 'none'

const STATUS_CONFIG: Record<
  CompositeStatus,
  { bg: string; text: string; label: string; border?: string }
> = {
  active: { bg: '#D1FAE5', text: '#065F46', label: 'IRS Auth: Active' },
  expiring_soon: { bg: '#FEF3C7', text: '#92400E', label: 'IRS Auth: Expiring Soon' },
  expired: { bg: '#FEE2E2', text: '#991B1B', label: 'IRS Auth: Expired' },
  pending: { bg: '#DBEAFE', text: '#1E40AF', label: 'IRS Auth: Pending' },
  none: {
    bg: '#E5E7EB',
    text: '#1F3148',
    label: 'IRS Auth: None on File',
    border: '0.5px solid #1F3148',
  },
}

function deriveStatus(res: IrsAuthStatusResponse | null): CompositeStatus {
  if (!res) return 'none'
  const r8821 = res['8821']
  const r2848 = res['2848']
  if (!r8821 && !r2848) return 'none'

  const records = [r8821, r2848].filter((r): r is IrsAuthorizationRecord => r !== null)

  if (records.some((r) => r.status === 'expired' || r.status === 'revoked')) return 'expired'

  const now = Date.now()
  const thirtyDaysMs = 30 * 24 * 60 * 60 * 1000
  if (
    records.some(
      (r) =>
        r.status === 'active' &&
        r.valid_until !== null &&
        new Date(r.valid_until).getTime() - now <= thirtyDaysMs &&
        new Date(r.valid_until).getTime() > now
    )
  )
    return 'expiring_soon'

  if (records.some((r) => r.status === 'pending_signature')) return 'pending'

  return 'active'
}

function fmtDate(dateStr: string): string {
  return formatLocalDate(dateStr, { month: 'short', day: 'numeric', year: 'numeric' })
}

function daysUntil(dateStr: string): number {
  return Math.ceil((new Date(dateStr).getTime() - Date.now()) / (1000 * 60 * 60 * 24))
}

function TooltipBody({ res }: { res: IrsAuthStatusResponse | null }) {
  const records: Array<{ type: '8821' | '2848'; rec: IrsAuthorizationRecord }> = []
  if (res?.['8821']) records.push({ type: '8821', rec: res['8821'] })
  if (res?.['2848']) records.push({ type: '2848', rec: res['2848'] })

  if (records.length === 0) {
    return (
      <span style={{ fontSize: 11, color: '#EDEEF0' }}>
        No IRS authorization on file.
      </span>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {records.map(({ type, rec }) => (
        <div key={type} style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <span style={{ fontSize: 12, fontWeight: 500, color: '#EDEEF0' }}>
            Form {type}
          </span>
          <span style={{ fontSize: 11, color: '#9CA3AF', textTransform: 'capitalize' }}>
            {rec.status.replace('_', ' ')}
          </span>
          {rec.valid_until && (
            <span style={{ fontSize: 11, color: '#9CA3AF' }}>
              Expires {fmtDate(rec.valid_until)} ({daysUntil(rec.valid_until)} days)
            </span>
          )}
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
