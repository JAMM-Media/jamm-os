// frontend/src/app/settings/billing/page.tsx
'use client'

import { useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import { AppShell } from '@/components/layout/AppShell'
import { onConciergeAction } from '@/lib/events/conciergeEvents'
import api from '@/lib/api'

export default function SettingsBillingPage() {
  const stripeRef = useRef<HTMLDivElement>(null)
  const [connecting, setConnecting] = useState(false)

  useEffect(() => {
    return onConciergeAction((action) => {
      if (action.modal === 'stripe-scroll') {
        stripeRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }
    })
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
    <AppShell>
      <div className="p-6 flex flex-col gap-6 max-w-2xl">
        <div>
          <h1 className="text-2xl font-medium text-brand dark:text-[#EDEEF0]">Billing</h1>
          <p className="text-[12px] text-[#6B7280] mt-0.5">
            Connect Stripe to accept online payments from clients.
          </p>
        </div>

        {/* Stripe */}
        <div
          ref={stripeRef}
          className="bg-surface-card dark:bg-dark-card rounded-[10px] border border-surface-border dark:border-dark-border p-5"
          style={{ borderWidth: '0.5px' }}
        >
          <div className="flex items-center gap-3 mb-3">
            <div className="flex items-center justify-center w-8 h-8 rounded-md bg-[#635BFF]">
              <span className="text-white font-bold text-[13px]">S</span>
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
          <button
            className="h-8 px-4 rounded-[6px] bg-[#635BFF] text-white text-[12px] font-medium hover:opacity-90 transition-opacity disabled:opacity-60"
            onClick={handleConnectStripe}
            disabled={connecting}
          >
            {connecting ? 'Connecting…' : 'Connect Stripe'}
          </button>
        </div>
      </div>
    </AppShell>
  )
}
