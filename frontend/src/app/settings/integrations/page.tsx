// frontend/src/app/settings/integrations/page.tsx
'use client'

import { useEffect, useRef, useState } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { onConciergeAction } from '@/lib/events/conciergeEvents'
import { toast } from 'sonner'
import api from '@/lib/api'

interface QboCustomer {
  quickbooks_customer_id: string
  name: string
  email: string | null
  is_active: boolean
}

function QboImportWizard() {
  const [step, setStep] = useState<'idle' | 'select' | 'empty' | 'done'>('idle')
  const [loading, setLoading] = useState(false)
  const [importing, setImporting] = useState(false)
  const [customers, setCustomers] = useState<QboCustomer[]>([])
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [result, setResult] = useState<{ created: number; skipped: number } | null>(null)

  async function handlePreview() {
    setLoading(true)
    try {
      const res = await api.get('/api/v1/integrations/quickbooks/import-preview')
      const data = res.data
      if (data.customers.length === 0) {
        setStep('empty')
      } else {
        setCustomers(data.customers)
        setSelectedIds(new Set(data.customers.map((c: QboCustomer) => c.quickbooks_customer_id)))
        setStep('select')
      }
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number; data?: { detail?: string } } })?.response?.status
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      if (status === 400) {
        toast.error('QuickBooks is not connected.')
      } else {
        toast.error(detail ?? 'Failed to load QuickBooks customers.')
      }
    } finally {
      setLoading(false)
    }
  }

  async function handleImport() {
    if (selectedIds.size === 0) return
    setImporting(true)
    try {
      const res = await api.post('/api/v1/integrations/quickbooks/import-clients', {
        quickbooks_customer_ids: Array.from(selectedIds),
      })
      setResult(res.data)
      setStep('done')
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(detail ?? 'Import failed. Please try again.')
    } finally {
      setImporting(false)
    }
  }

  function reset() {
    setStep('idle')
    setCustomers([])
    setSelectedIds(new Set())
    setResult(null)
  }

  function toggleAll() {
    if (selectedIds.size === customers.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(customers.map((c) => c.quickbooks_customer_id)))
    }
  }

  function toggleOne(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  return (
    <div className="mt-4 pt-4 border-t border-[0.5px] border-surface-border dark:border-dark-border">
      {step === 'idle' && (
        <button
          onClick={handlePreview}
          disabled={loading}
          className="h-8 px-4 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[12px] font-medium hover:opacity-90 transition-opacity disabled:opacity-60 flex items-center gap-2"
        >
          {loading && (
            <svg className="animate-spin h-3 w-3 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
          )}
          {loading ? 'Loading...' : 'Import from QuickBooks'}
        </button>
      )}

      {step === 'empty' && (
        <p className="text-[12px] text-[#6B7280]">All QuickBooks customers are already in JAMM PX.</p>
      )}

      {step === 'select' && (
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <button
              onClick={toggleAll}
              className="text-[12px] text-brand dark:text-[#EDEEF0] underline"
            >
              {selectedIds.size === customers.length ? 'Deselect all' : 'Select all'}
            </button>
            <span className="text-[12px] text-[#6B7280]">{selectedIds.size} of {customers.length} selected</span>
          </div>
          <div className="flex flex-col divide-y divide-[0.5px] divide-surface-border dark:divide-dark-border rounded-[8px] border border-[0.5px] border-surface-border dark:border-dark-border overflow-hidden">
            {customers.map((c) => (
              <label
                key={c.quickbooks_customer_id}
                className="flex items-center gap-3 px-3 py-2 cursor-pointer hover:bg-[#F3F4F6] dark:hover:bg-[#303030]"
              >
                <input
                  type="checkbox"
                  checked={selectedIds.has(c.quickbooks_customer_id)}
                  onChange={() => toggleOne(c.quickbooks_customer_id)}
                  className="w-3.5 h-3.5 accent-brand"
                />
                <span className="text-[13px] text-brand dark:text-[#EDEEF0] flex-1">{c.name}</span>
                {c.email && (
                  <span className="text-[12px] text-[#6B7280]">{c.email}</span>
                )}
              </label>
            ))}
          </div>
          <div className="flex justify-end">
            <button
              onClick={handleImport}
              disabled={selectedIds.size === 0 || importing}
              className="h-8 px-4 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[12px] font-medium hover:opacity-90 transition-opacity disabled:opacity-60 flex items-center gap-2"
            >
              {importing && (
                <svg className="animate-spin h-3 w-3 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                </svg>
              )}
              {importing ? 'Importing...' : 'Import Selected'}
            </button>
          </div>
        </div>
      )}

      {step === 'done' && result && (
        <div className="flex flex-col gap-3">
          <p className="text-[12px] text-[#374151] dark:text-[#9CA3AF]">
            {result.created} client{result.created !== 1 ? 's' : ''} imported, {result.skipped} skipped.
          </p>
          <div className="flex justify-end">
            <button
              onClick={reset}
              className="h-8 px-4 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[12px] font-medium hover:opacity-90 transition-opacity"
            >
              Done
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

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
          <QboImportWizard />
        </div>
      </div>
    </AppShell>
  )
}
