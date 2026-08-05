// frontend/src/components/clients/IrsAuthTab.tsx
'use client'
import { formatLocalDate } from '@/lib/utils'

import { useState } from 'react'
import { toast } from 'sonner'
import { ShieldCheck } from 'lucide-react'
import { useAuth } from '@/lib/hooks/useAuth'
import { useFetch } from '@/lib/hooks/useFetch'
import {
  irsAuthorizationsApi,
  type IrsAuthorizationRecord,
  type IrsAuthSendRequest,
} from '@/lib/api/irsAuthorizationsApi'
import { Modal } from '@/components/ui/Modal'

type RecordStatus = IrsAuthorizationRecord['status']

const RECORD_STATUS_CONFIG: Record<
  RecordStatus,
  { bg: string; text: string; label: string; border?: string }
> = {
  active: { bg: 'var(--color-status-green)', text: 'var(--color-status-green-text)', label: 'Active' },
  pending_signature: { bg: 'var(--color-status-blue)', text: 'var(--color-status-blue-text)', label: 'Pending' },
  expired: { bg: 'var(--color-status-red)', text: 'var(--color-status-red-text)', label: 'Expired' },
  revoked: { bg: 'var(--color-status-red)', text: 'var(--color-status-red-text)', label: 'Revoked' },
  superseded: { bg: 'var(--color-status-gray)', text: 'var(--color-status-gray-text)', label: 'Replaced', border: '0.5px solid #1F3148' },
}

function fmtDate(d: string | null): string {
  if (!d) return '—'
  return new Date(d).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

interface SendModalProps {
  clientId: string
  onClose: () => void
  onSuccess: () => void
}

function SendAuthModal({ clientId, onClose, onSuccess }: SendModalProps) {
  const [formType, setFormType] = useState<'8821' | '2848' | ''>('')
  const [taxYearsInput, setTaxYearsInput] = useState('')
  const [validFrom, setValidFrom] = useState('')
  const [validUntil, setValidUntil] = useState('')
  const [isSending, setIsSending] = useState(false)

  async function handleSend() {
    if (!formType) {
      toast.error('Please select a form type.')
      return
    }

    const taxYears = taxYearsInput
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
      .map(Number)
      .filter((n) => !isNaN(n) && n > 0)

    const payload: IrsAuthSendRequest = {
      client_id: clientId,
      form_type: formType,
      tax_years: taxYears,
      ...(validFrom ? { valid_from: validFrom } : {}),
      ...(validUntil ? { valid_until: validUntil } : {}),
    }

    setIsSending(true)
    try {
      await irsAuthorizationsApi.send(payload)
      toast.success('IRS authorization sent.')
      onSuccess()
    } catch {
      toast.error('Failed to send authorization.', {
        description: 'Please try again or contact support.',
      })
    } finally {
      setIsSending(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Send IRS Authorization"
      size="md"
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            className="h-8 px-3 rounded-[6px] text-[12px] font-medium text-muted-foreground hover:text-brand dark:hover:text-foreground transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSend}
            disabled={isSending}
            className="h-8 px-3 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[12px] font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {isSending ? 'Sending…' : 'Send'}
          </button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {/* Form type */}
        <div className="flex flex-col gap-1.5">
          <span className="text-[12px] font-medium text-brand dark:text-foreground">
            Form Type <span className="text-status-red-text">*</span>
          </span>
          <div className="flex flex-col gap-2">
            {(
              [
                { value: '8821', label: 'Form 8821 (Tax Info)' },
                { value: '2848', label: 'Form 2848 (Power of Attorney)' },
              ] as const
            ).map((opt) => (
              <label
                key={opt.value}
                className="flex items-center gap-2 cursor-pointer"
              >
                <input
                  type="radio"
                  name="form_type"
                  value={opt.value}
                  checked={formType === opt.value}
                  onChange={() => setFormType(opt.value)}
                  className="accent-brand"
                />
                <span className="text-[12px] text-foreground dark:text-muted-foreground">
                  {opt.label}
                </span>
              </label>
            ))}
          </div>
        </div>

        {/* Tax years */}
        <div className="flex flex-col gap-1.5">
          <span className="text-[12px] font-medium text-brand dark:text-foreground">
            Tax Years
          </span>
          <input
            type="text"
            value={taxYearsInput}
            onChange={(e) => setTaxYearsInput(e.target.value)}
            placeholder="e.g. 2022, 2023, 2024"
            className="h-8 px-2.5 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[12px] text-brand dark:text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-brand"
          />
          <span className="text-[11px] text-muted-foreground">
            Enter the tax years this authorization covers.
          </span>
        </div>

        {/* Valid from */}
        <div className="flex flex-col gap-1.5">
          <span className="text-[12px] font-medium text-brand dark:text-foreground">
            Valid From <span className="text-[11px] font-normal text-muted-foreground">(optional)</span>
          </span>
          <input
            type="date"
            value={validFrom}
            onChange={(e) => setValidFrom(e.target.value)}
            className="h-8 px-2.5 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[12px] text-brand dark:text-foreground focus:outline-none focus:ring-1 focus:ring-brand"
          />
        </div>

        {/* Valid until */}
        <div className="flex flex-col gap-1.5">
          <span className="text-[12px] font-medium text-brand dark:text-foreground">
            Valid Until <span className="text-[11px] font-normal text-muted-foreground">(optional)</span>
          </span>
          <input
            type="date"
            value={validUntil}
            onChange={(e) => setValidUntil(e.target.value)}
            className="h-8 px-2.5 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[12px] text-brand dark:text-foreground focus:outline-none focus:ring-1 focus:ring-brand"
          />
        </div>
      </div>
    </Modal>
  )
}

interface IrsAuthTabProps {
  clientId: string
}

export function IrsAuthTab({ clientId }: IrsAuthTabProps) {
  const { user } = useAuth()
  const canSend =
    user?.role === 'manager' || user?.role === 'firm_owner'

  const [showModal, setShowModal] = useState(false)

  const {
    data: authsRaw,
    isLoading,
    refetch,
  } = useFetch(
    () =>
      irsAuthorizationsApi
        .listForClient(clientId)
        .then((r) => r.data as IrsAuthorizationRecord[]),
    [clientId]
  )

  const auths: IrsAuthorizationRecord[] = Array.isArray(authsRaw) ? authsRaw : []

  function handleModalSuccess() {
    setShowModal(false)
    refetch()
  }

  return (
    <>
      {/* Header row */}
      <div className="flex items-center justify-between mb-4">
        <span
          style={{ fontSize: 16, fontWeight: 500 }}
          className="text-brand dark:text-foreground"
        >
          IRS Authorizations
        </span>
        {canSend && (
          <button
            type="button"
            onClick={() => setShowModal(true)}
            style={{ height: 32, borderRadius: 6, fontSize: 12, fontWeight: 500 }}
            className="px-3 bg-brand text-white hover:opacity-90 transition-opacity"
          >
            + Send Authorization
          </button>
        )}
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="flex flex-col gap-3">
          {Array.from({ length: 2 }).map((_, i) => (
            <div
              key={i}
              className="h-24 rounded-[8px] bg-surface-border dark:bg-dark-border animate-pulse"
            />
          ))}
        </div>
      ) : auths.length === 0 ? (
        /* Empty state */
        <div className="flex flex-col items-center justify-center py-24 gap-[10px]">
          <div className="flex items-center justify-center w-10 h-10 rounded-[10px] bg-surface-card dark:bg-dark-card border border-[0.5px] border-surface-border dark:border-dark-border">
            <ShieldCheck className="h-[18px] w-[18px] text-muted-foreground" />
          </div>
          <p className="text-[13px] font-medium text-brand dark:text-foreground">
            No IRS authorizations on file
          </p>
          <p className="text-[12px] text-muted-foreground text-center max-w-xs">
            Send a Form 8821 or 2848 to authorize this firm to represent this client
            with the IRS.
          </p>
          {canSend && (
            <button
              type="button"
              onClick={() => setShowModal(true)}
              style={{ height: 32, borderRadius: 6, fontSize: 12, fontWeight: 500 }}
              className="mt-1 px-3 bg-brand text-white hover:opacity-90 transition-opacity"
            >
              + Send Authorization
            </button>
          )}
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {auths.map((rec) => {
            const statusCfg = RECORD_STATUS_CONFIG[rec.status]
            return (
              <div
                key={rec.id}
                style={{ borderRadius: 8, padding: '12px 14px' }}
                className="bg-surface-card dark:bg-dark-card"
              >
                {/* Top row */}
                <div className="flex items-center justify-between mb-1.5">
                  <span
                    style={{ fontSize: 14, fontWeight: 500 }}
                    className="text-brand dark:text-foreground"
                  >
                    Form {rec.form_type}
                  </span>
                  <span
                    style={{
                      height: 22,
                      fontSize: 11,
                      fontWeight: 500,
                      borderRadius: 9999,
                      padding: '0 10px',
                      background: statusCfg.bg,
                      color: statusCfg.text,
                      border: statusCfg.border ?? 'none',
                      display: 'inline-flex',
                      alignItems: 'center',
                    }}
                  >
                    {statusCfg.label}
                  </span>
                </div>

                {/* Second row */}
                <p style={{ fontSize: 12 }} className="text-muted-foreground mb-0.5">
                  Tax years:{' '}
                  {rec.tax_years && rec.tax_years.length > 0
                    ? rec.tax_years.join(', ')
                    : 'All years'}
                </p>

                {/* Third row */}
                <p style={{ fontSize: 12 }} className="text-muted-foreground mb-0.5">
                  {rec.valid_from || rec.valid_until
                    ? `Valid ${formatLocalDate(rec.valid_from, { month: 'short', day: 'numeric', year: 'numeric' })} → ${formatLocalDate(rec.valid_until, { month: 'short', day: 'numeric', year: 'numeric' })}`
                    : 'Validity dates not set'}
                </p>

                {/* Fourth row */}
                <p style={{ fontSize: 11 }} className="text-muted-foreground">
                  Sent {fmtDate(rec.created_at)}
                </p>
              </div>
            )
          })}
        </div>
      )}

      {showModal && (
        <SendAuthModal
          clientId={clientId}
          onClose={() => setShowModal(false)}
          onSuccess={handleModalSuccess}
        />
      )}
    </>
  )
}
