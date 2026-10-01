// frontend/src/app/(app)/settings/billing/page.tsx
'use client'

import { useEffect, Suspense } from 'react'
import { useSearchParams } from 'next/navigation'
import { toast } from 'sonner'
import { BillingTab } from '@/components/settings/BillingTab'

function SettingsBillingContent() {
  const searchParams = useSearchParams()

  useEffect(() => {
    const connected = searchParams.get('connected')
    const error = searchParams.get('error')
    if (connected === 'stripe') {
      toast.success('Stripe connected successfully.')
    }
    if (error === 'stripe_already_connected') toast.error('This firm already has a Stripe account connected.')
    if (error === 'stripe_failed') toast.error('Stripe connection failed. Please try again.')
  }, [searchParams])

  return (
    <div className="p-6 flex flex-col gap-6 max-w-2xl">
      <div>
        <h1 className="text-2xl font-medium text-brand dark:text-[#EDEEF0]">Billing</h1>
        <p className="text-[12px] text-[#6B7280] mt-0.5">
          Connect Stripe to accept online payments from clients.
        </p>
      </div>
      <BillingTab />
    </div>
  )
}

export default function SettingsBillingPage() {
  return (
    <Suspense fallback={<div />}>
      <SettingsBillingContent />
    </Suspense>
  )
}
