// frontend/src/app/settings/integrations/page.tsx
'use client'

import { useEffect, useRef } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { onConciergeAction } from '@/lib/events/conciergeEvents'

export default function SettingsIntegrationsPage() {
  const qboRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    return onConciergeAction((action) => {
      if (action.modal === 'quickbooks-scroll') {
        qboRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }
    })
  }, [])

  return (
    <AppShell>
      <div className="p-6 flex flex-col gap-6 max-w-2xl">
        <div>
          <h1 className="text-2xl font-medium text-brand dark:text-[#EDEEF0]">Integrations</h1>
          <p className="text-[12px] text-[#6B7280] mt-0.5">
            Connect third-party services to JAMM PX.
          </p>
        </div>

        {/* QuickBooks */}
        <div
          ref={qboRef}
          className="bg-surface-card dark:bg-dark-card rounded-[10px] border border-surface-border dark:border-dark-border p-5"
          style={{ borderWidth: '0.5px' }}
        >
          <div className="flex items-center gap-3 mb-3">
            <div className="flex items-center justify-center w-8 h-8 rounded-md bg-[#2CA01C]">
              <svg width="18" height="18" viewBox="0 0 32 32" fill="none">
                <circle cx="16" cy="16" r="16" fill="#2CA01C" />
                <path d="M13 16.5l2.5 2.5 4.5-5" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
            <div>
              <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">QuickBooks Online</p>
              <p className="text-[11px] text-[#6B7280]">Import clients and sync AR balances</p>
            </div>
          </div>
          <p className="text-[12px] text-[#374151] dark:text-[#9CA3AF] mb-4">
            Connect your QuickBooks Online account to import clients, view outstanding
            balances, and keep records in sync. Use the Import Preview to select which
            clients come over before committing.
          </p>
          <button
            className="h-8 px-4 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[12px] font-medium hover:opacity-90 transition-opacity"
            onClick={() => {
              // Navigate to the QuickBooks OAuth flow
              window.location.href = '/api/backend/integrations/quickbooks/connect'
            }}
          >
            Connect QuickBooks
          </button>
        </div>
      </div>
    </AppShell>
  )
}
