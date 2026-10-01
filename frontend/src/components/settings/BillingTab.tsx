// path: frontend/src/components/settings/BillingTab.tsx
'use client'

import { useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { onConciergeAction } from '@/lib/events/conciergeEvents'
import api from '@/lib/api'

interface StripeStatus {
  connected: boolean
  charges_enabled: boolean
  payouts_enabled: boolean
  details_submitted: boolean
  stripe_account_id?: string
}

export function BillingTab() {
  const stripeRef = useRef<HTMLDivElement>(null)
  const [connecting, setConnecting] = useState(false)
  const [status, setStatus] = useState<StripeStatus | null>(null)
  const [loadingStatus, setLoadingStatus] = useState(true)

  useEffect(() => {
    return onConciergeAction((action) => {
      if (action.modal === 'stripe-scroll') {
        stripeRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }
    })
  }, [])

  async function fetchStatus() {
    try {
      const resp = await api.get('/stripe/status')
      setStatus(resp.data)
    } catch {
      toast.error('Failed to load Stripe connection status.')
    } finally {
      setLoadingStatus(false)
    }
  }

  useEffect(() => {
    fetchStatus()
  }, [])

  async function handleConnectStripe() {
    setConnecting(true)
    try {
      const resp = await api.get('/stripe/connect')
      window.location.href = resp.data.url
    } catch {
      toast.error('Failed to start Stripe connection.')
      setConnecting(false)
    }
  }

  return (
    <div
      ref={stripeRef}
      className="bg-surface-card dark:bg-dark-card rounded-[10px] border border-surface-border dark:border-dark-border p-5"
      style={{ borderWidth: "0.5px" }}
    >
      <div className="flex items-center gap-3 mb-3">
        <div className="flex items-center justify-center w-8 h-8 rounded-md bg-brand dark:bg-brand-btn">
          <span className="text-white font-medium text-[13px]">S</span>
        </div>
        <div>
          <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">Stripe Connect</p>
          <p className="text-[11px] text-[#6B7280]">Accept online payments from clients</p>
        </div>
      </div>
      <p className="text-[12px] text-[#374151] dark:text-[#9CA3AF] mb-4">
        Connect your Stripe account to send invoices for online payment. Clients pay
        directly through the portal. Required before any invoice can be sent for online
        collection.
      </p>
      {loadingStatus ? (
        <div className="flex flex-col gap-2">
          <div className="h-5 w-24 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded-full" />
          <div className="h-3 w-40 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
        </div>
      ) : status?.connected ? (
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <StatusBadge variant="complete" label="Connected" />
            {status.stripe_account_id && (
              <span className="text-[11px] text-[#6B7280]">{status.stripe_account_id}</span>
            )}
          </div>
          {status.charges_enabled && status.payouts_enabled ? (
            <p className="text-[11px] text-[#6B7280]">Charges and payouts are enabled.</p>
          ) : (
            <p className="text-[11px] text-status-amber-text">
              Stripe needs additional details before payments can go live.
            </p>
          )}
        </div>
      ) : (
        <button
          className="h-8 px-4 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[12px] font-medium hover:opacity-90 transition-opacity disabled:opacity-60"
          onClick={handleConnectStripe}
          disabled={connecting}
        >
          {connecting ? 'Connecting…' : 'Connect Stripe'}
        </button>
      )}
    </div>
  )
}
