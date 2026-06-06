// frontend/src/components/settings/SendingDomainTab.tsx
'use client'

import { useState, useEffect } from 'react'
import { toast } from 'sonner'
import { Check } from 'lucide-react'
import api from '@/lib/api'
import { settingsApi, type FirmDetails } from '@/lib/api/settingsApi'
import { useFetch } from '@/lib/hooks/useFetch'
import { cn } from '@/lib/utils'

interface DnsRecord {
  type: 'TXT' | 'CNAME'
  host: string
  value: string
}

interface DnsRecordsState {
  domain: string
  dkim_host: string
  dkim_value: string
  return_path_host: string
  return_path_value: string
  verified: boolean
}

type TabState = 'none' | 'registered' | 'verified'

function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false)

  function handleCopy() {
    navigator.clipboard.writeText(value).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <button
      type="button"
      onClick={handleCopy}
      className="flex-shrink-0 h-7 px-2.5 text-[11px] font-medium rounded-[5px] border border-surface-border dark:border-dark-border text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] transition-colors"
    >
      {copied ? 'Copied!' : 'Copy'}
    </button>
  )
}

function DnsRecordCard({ record }: { record: DnsRecord }) {
  const inputClass =
    'flex-1 min-w-0 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[12px] text-brand dark:text-[#EDEEF0] px-3 py-1.5 focus:outline-none font-mono truncate'

  return (
    <div className="bg-surface-page dark:bg-dark-page rounded-[8px] border border-surface-border dark:border-dark-border p-3 flex flex-col gap-2">
      <span className="inline-flex w-fit text-[10px] font-semibold px-2 py-0.5 rounded bg-[#E5E7EB] dark:bg-[#444444] text-[#374151] dark:text-[#EDEEF0] tracking-wide">
        {record.type}
      </span>
      <div className="flex flex-col gap-1.5">
        <div>
          <p className="text-[10px] font-medium text-[#6B7280] uppercase tracking-[0.05em] mb-1">Host</p>
          <div className="flex items-center gap-2">
            <input readOnly value={record.host} className={inputClass} />
            <CopyButton value={record.host} />
          </div>
        </div>
        <div>
          <p className="text-[10px] font-medium text-[#6B7280] uppercase tracking-[0.05em] mb-1">Value</p>
          <div className="flex items-center gap-2">
            <input readOnly value={record.value} className={inputClass} />
            <CopyButton value={record.value} />
          </div>
        </div>
      </div>
    </div>
  )
}

export default function SendingDomainTab() {
  const { data: firmData } = useFetch<FirmDetails>(
    () => settingsApi.getMyFirm().then((r) => r.data as FirmDetails),
    []
  )

  const firm = firmData as (FirmDetails & {
    sending_domain?: string | null
    sending_domain_verified?: boolean
    sending_domain_dkim_host?: string | null
    sending_domain_dkim_value?: string | null
    sending_domain_return_path_host?: string | null
    sending_domain_return_path_value?: string | null
  }) | undefined

  const [tabState, setTabState] = useState<TabState>('none')
  const [dnsRecords, setDnsRecords] = useState<DnsRecordsState | null>(null)
  const [domainInput, setDomainInput] = useState('')
  const [registering, setRegistering] = useState(false)
  const [registerError, setRegisterError] = useState<string | null>(null)
  const [verifying, setVerifying] = useState(false)
  const [verifyMessage, setVerifyMessage] = useState<string | null>(null)
  const [removing, setRemoving] = useState(false)
  const [confirmRemove, setConfirmRemove] = useState(false)

  useEffect(() => {
    if (!firm) return
    if (firm.sending_domain && firm.sending_domain_verified) {
      setTabState('verified')
      setDnsRecords({
        domain: firm.sending_domain,
        dkim_host: firm.sending_domain_dkim_host ?? '',
        dkim_value: firm.sending_domain_dkim_value ?? '',
        return_path_host: firm.sending_domain_return_path_host ?? '',
        return_path_value: firm.sending_domain_return_path_value ?? '',
        verified: true,
      })
    } else if (firm.sending_domain) {
      setTabState('registered')
      setDnsRecords({
        domain: firm.sending_domain,
        dkim_host: firm.sending_domain_dkim_host ?? '',
        dkim_value: firm.sending_domain_dkim_value ?? '',
        return_path_host: firm.sending_domain_return_path_host ?? '',
        return_path_value: firm.sending_domain_return_path_value ?? '',
        verified: false,
      })
    } else {
      setTabState('none')
    }
  }, [firm])

  async function handleRegister() {
    setRegisterError(null)
    setRegistering(true)
    try {
      const resp = await api.post('/api/v1/sending-domain/register', { domain: domainInput })
      setDnsRecords(resp.data)
      setTabState('registered')
      setDomainInput('')
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setRegisterError(detail ?? 'Something went wrong.')
    } finally {
      setRegistering(false)
    }
  }

  async function handleVerify() {
    setVerifyMessage(null)
    setVerifying(true)
    try {
      const resp = await api.post('/api/v1/sending-domain/verify')
      if (resp.data.verified) {
        setTabState('verified')
        if (dnsRecords) setDnsRecords({ ...dnsRecords, verified: true })
        toast.success('Domain verified successfully.')
      } else {
        setVerifyMessage(resp.data.message)
      }
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(detail ?? 'Verification failed.')
    } finally {
      setVerifying(false)
    }
  }

  async function handleRemove() {
    setRemoving(true)
    try {
      await api.delete('/api/v1/sending-domain')
      setTabState('none')
      setDnsRecords(null)
      setConfirmRemove(false)
      toast.success('Sending domain removed.')
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(detail ?? 'Failed to remove domain.')
    } finally {
      setRemoving(false)
    }
  }

  const cardClass = 'bg-surface-card dark:bg-dark-card rounded-[10px] p-4 flex flex-col gap-4 max-w-lg'
  const inputClass =
    'w-full rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[13px] text-brand dark:text-[#EDEEF0] px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-brand'
  const labelClass = 'text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em]'
  const btnPrimary =
    'h-8 px-3 text-[13px] font-medium rounded-[6px] bg-brand text-white hover:bg-brand/90 transition-colors disabled:opacity-60 flex items-center gap-2'

  if (tabState === 'none') {
    return (
      <div className={cardClass}>
        <div>
          <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">Custom Sending Domain</p>
          <p className="text-[12px] text-[#6B7280] mt-1">
            Send client emails from your own domain instead of noreply@jammpx.com. Requires adding two DNS records to your domain.
          </p>
        </div>
        <div className="flex flex-col gap-1.5">
          <label className={labelClass}>Domain</label>
          <input
            type="text"
            value={domainInput}
            onChange={(e) => setDomainInput(e.target.value)}
            placeholder="smithcpa.com"
            className={inputClass}
          />
          {registerError && (
            <p className="text-[12px] text-red-600 dark:text-red-400">{registerError}</p>
          )}
        </div>
        <div className="flex justify-end">
          <button
            onClick={handleRegister}
            disabled={registering || !domainInput.trim()}
            className={btnPrimary}
          >
            {registering && (
              <svg className="animate-spin h-3.5 w-3.5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
            )}
            {registering ? 'Registering...' : 'Register Domain'}
          </button>
        </div>
      </div>
    )
  }

  if (tabState === 'registered' && dnsRecords) {
    const records: DnsRecord[] = [
      { type: 'TXT', host: dnsRecords.dkim_host, value: dnsRecords.dkim_value },
      { type: 'CNAME', host: dnsRecords.return_path_host, value: dnsRecords.return_path_value },
    ]

    return (
      <div className={cardClass}>
        <div>
          <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">Add these DNS records</p>
          <p className="text-[12px] text-[#6B7280] mt-1">
            Add both records to your domain registrar (GoDaddy, Namecheap, Cloudflare, etc.), then click Verify. DNS changes can take up to 48 hours to propagate.
          </p>
        </div>
        <div className="flex flex-col gap-3">
          {records.map((r, i) => (
            <DnsRecordCard key={i} record={r} />
          ))}
        </div>
        {verifyMessage && (
          <p className="text-[12px] text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 rounded-[6px] px-3 py-2">
            {verifyMessage}
          </p>
        )}
        <div className="flex items-center justify-between">
          <button
            onClick={handleVerify}
            disabled={verifying}
            className={btnPrimary}
          >
            {verifying && (
              <svg className="animate-spin h-3.5 w-3.5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
            )}
            {verifying ? 'Verifying...' : 'Verify DNS Records'}
          </button>
          {!confirmRemove ? (
            <button
              type="button"
              onClick={() => setConfirmRemove(true)}
              className="text-[12px] text-[#6B7280] hover:text-red-600 transition-colors"
            >
              Remove domain
            </button>
          ) : (
            <div className="flex items-center gap-2">
              <span className="text-[12px] text-[#6B7280]">Remove?</span>
              <button
                type="button"
                onClick={handleRemove}
                disabled={removing}
                className="text-[12px] text-red-600 hover:text-red-700 font-medium transition-colors disabled:opacity-60"
              >
                {removing ? 'Removing...' : 'Yes, remove'}
              </button>
              <button
                type="button"
                onClick={() => setConfirmRemove(false)}
                className="text-[12px] text-[#6B7280] hover:text-brand transition-colors"
              >
                Cancel
              </button>
            </div>
          )}
        </div>
      </div>
    )
  }

  if (tabState === 'verified' && dnsRecords) {
    return (
      <div className={cardClass}>
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-8 h-8 rounded-full bg-[#D1FAE5] flex-shrink-0">
            <Check className="w-4 h-4 text-[#065F46]" />
          </div>
          <div>
            <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">
              {dnsRecords.domain} is verified
            </p>
            <p className="text-[12px] text-[#6B7280]">
              Client emails will now be sent from noreply@{dnsRecords.domain}
            </p>
          </div>
        </div>
        {!confirmRemove ? (
          <div className="flex justify-end">
            <button
              type="button"
              onClick={() => setConfirmRemove(true)}
              className={cn(
                'h-8 px-3 text-[13px] font-medium rounded-[6px] border transition-colors',
                'border-red-300 dark:border-red-700 text-red-600 dark:text-red-400',
                'hover:bg-red-50 dark:hover:bg-red-900/20',
              )}
            >
              Remove Domain
            </button>
          </div>
        ) : (
          <div className="flex items-center justify-end gap-2">
            <span className="text-[12px] text-[#6B7280]">Remove sending domain?</span>
            <button
              type="button"
              onClick={handleRemove}
              disabled={removing}
              className="h-7 px-2.5 text-[12px] font-medium rounded-[5px] bg-red-600 text-white hover:bg-red-700 transition-colors disabled:opacity-60"
            >
              {removing ? 'Removing...' : 'Yes, remove'}
            </button>
            <button
              type="button"
              onClick={() => setConfirmRemove(false)}
              className="h-7 px-2.5 text-[12px] font-medium rounded-[5px] border border-surface-border dark:border-dark-border text-[#6B7280] hover:text-brand transition-colors"
            >
              Cancel
            </button>
          </div>
        )}
      </div>
    )
  }

  return null
}
