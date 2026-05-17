// path: frontend/src/app/billing/page.tsx
'use client'

import { useState } from 'react'
import { toast } from 'sonner'
import { AppShell } from '@/components/layout/AppShell'
import { ViewToggle } from '@/components/ui/ViewToggle'
import { InvoiceTable } from '@/components/billing/InvoiceTable'
import { InvoiceCard } from '@/components/billing/InvoiceCard'
import { BillingEmptyState } from '@/components/billing/BillingEmptyState'
import { BillingSummary } from '@/components/billing/BillingSummary'
import { NewInvoiceModal } from '@/components/billing/NewInvoiceModal'
import { invoicesApi, clientsApi } from '@/lib/api'
import { useFetch } from '@/lib/hooks/useFetch'
import { Search, X } from 'lucide-react'
import type { Invoice } from '@/lib/api'

type ViewMode = 'table' | 'card'

export default function BillingPage() {
  const [view, setView] = useState<ViewMode>('table')
  const [search, setSearch] = useState('')
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [bulkLoading, setBulkLoading] = useState(false)
  const [voidConfirmOpen, setVoidConfirmOpen] = useState(false)
  const [newInvoiceOpen, setNewInvoiceOpen] = useState(false)
  const [localInvoices, setLocalInvoices] = useState<Invoice[]>([])

  const { data, isLoading, error } = useFetch(() => invoicesApi.list(0, 50), [])
  const { data: clientsData, isLoading: clientsLoading } = useFetch(() => clientsApi.list(0, 100), [])
  const serverInvoices = data?.items ?? []
  const invoices = [...localInvoices, ...serverInvoices]

  const clientMap: Record<string, string> = Object.fromEntries(
    (clientsData?.items ?? []).map((c) => [c.id, c.name])
  )

  const filtered = invoices.filter((inv) => {
    const q = search.toLowerCase()
    const clientName = (clientMap[inv.clientId] ?? '').toLowerCase()
    return (
      inv.invoiceNumber.toLowerCase().includes(q) ||
      clientName.includes(q)
    )
  })

  function handleSelect(id: string, checked: boolean) {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (checked) next.add(id)
      else next.delete(id)
      return next
    })
  }

  function handleSelectAll(checked: boolean) {
    if (checked) setSelectedIds(new Set(filtered.map((inv) => inv.id)))
    else setSelectedIds(new Set())
  }

  const selectedInvoices = filtered.filter((inv) => selectedIds.has(inv.id))
  const allDraft = selectedInvoices.every((inv) => inv.status === 'draft')
  const canSend = selectedInvoices.length > 0 && allDraft

  async function handleBulkSend() {
    setBulkLoading(true)
    const ids = Array.from(selectedIds)
    setLocalInvoices((lis) =>
      lis.map((inv) => selectedIds.has(inv.id) ? { ...inv, status: 'sent' } : inv)
    )
    try {
      await invoicesApi.bulkUpdate(ids, 'send')
      setSelectedIds(new Set())
      toast.success(`Sent ${ids.length} invoice${ids.length !== 1 ? 's' : ''}`)
    } catch {
      setLocalInvoices((lis) =>
        lis.map((inv) => selectedIds.has(inv.id) ? { ...inv, status: 'draft' } : inv)
      )
      toast.error('Bulk send failed')
    } finally {
      setBulkLoading(false)
    }
  }

  async function handleBulkVoid() {
    setVoidConfirmOpen(false)
    setBulkLoading(true)
    const ids = Array.from(selectedIds)
    setLocalInvoices((lis) =>
      lis.map((inv) => selectedIds.has(inv.id) ? { ...inv, status: 'void' } : inv)
    )
    try {
      await invoicesApi.bulkUpdate(ids, 'void')
      setSelectedIds(new Set())
      toast.success(`Voided ${ids.length} invoice${ids.length !== 1 ? 's' : ''}`)
    } catch {
      setLocalInvoices((lis) =>
        lis.map((inv) => selectedIds.has(inv.id) ? { ...inv, status: 'sent' } : inv)
      )
      toast.error('Bulk void failed')
    } finally {
      setBulkLoading(false)
    }
  }

  const selCount = selectedIds.size

  if (error) {
    return (
      <AppShell>
        <div className="flex flex-col h-full p-6 items-center justify-center">
          <p className="text-sm text-[#DC2626]">Failed to load invoices.</p>
        </div>
      </AppShell>
    )
  }

  return (
    <AppShell>
      <div className="flex flex-col h-full p-6 gap-4">

        <h1 className="text-2xl font-medium text-brand dark:text-[#EDEEF0]">
          Billing
        </h1>

        {/* Summary bar */}
        <BillingSummary invoices={invoices} />

        {/* Toolbar */}
        <div className="flex items-center gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-[#6B7280]" />
            <input
              type="text"
              placeholder="Search invoices..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full h-9 pl-8 pr-3 rounded-[6px] bg-surface-input dark:bg-dark-card border border-[0.5px] border-surface-border dark:border-dark-border text-[13px] text-brand dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-brand-light transition-colors"
            />
          </div>
          <ViewToggle value={view} onChange={setView} />
          <button
            onClick={() => setNewInvoiceOpen(true)}
            className="h-9 px-3 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[13px] font-medium hover:opacity-90 transition-opacity whitespace-nowrap flex-shrink-0"
          >
            + New Invoice
          </button>
        </div>

        {/* Content */}
        {isLoading ? (
          <div className="rounded-modal border border-[0.5px] border-surface-border dark:border-dark-border overflow-hidden">
            {Array.from({ length: 5 }).map((_, i) => (
              <div
                key={i}
                className="flex gap-4 px-4 py-3 border-b border-[0.5px] border-[#D5D8DE] dark:border-dark-card last:border-0"
              >
                {Array.from({ length: 6 }).map((_, j) => (
                  <div key={j} className="h-4 flex-1 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                ))}
              </div>
            ))}
          </div>
        ) : filtered.length === 0 && search === '' ? (
          <BillingEmptyState onNew={() => {}} />
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center flex-1 py-24 gap-2">
            <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">
              No results for &ldquo;{search}&rdquo;
            </p>
            <p className="text-[12px] text-[#6B7280]">
              Try a different invoice number or client name.
            </p>
          </div>
        ) : view === 'table' ? (
          <InvoiceTable
            invoices={filtered}
            clientMap={clientMap}
            lookupsLoading={clientsLoading}
            selectedIds={selectedIds}
            onSelect={handleSelect}
            onSelectAll={handleSelectAll}
          />
        ) : (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
            {filtered.map((inv) => (
              <InvoiceCard key={inv.id} invoice={inv} clientMap={clientMap} lookupsLoading={clientsLoading} />
            ))}
          </div>
        )}

        {/* Floating bulk action bar */}
        {selCount > 0 && (
          <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50">
            <div className="bg-[#1F3148] dark:bg-[#1A2535] rounded-lg shadow-lg px-5 py-3 flex items-center gap-3">
              <span className="text-[13px] text-white font-medium whitespace-nowrap">
                {selCount} selected
              </span>

              {/* Send Selected */}
              <div className="relative group">
                <button
                  disabled={bulkLoading || !canSend}
                  onClick={handleBulkSend}
                  className="text-white text-[12px] border border-white/30 rounded px-3 py-1.5 hover:bg-white/10 disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
                >
                  Send Selected
                </button>
                {!canSend && selCount > 0 && (
                  <div className="absolute bottom-full mb-2 left-1/2 -translate-x-1/2 bg-[#111827] text-white text-[11px] rounded px-2 py-1 whitespace-nowrap pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity">
                    Select only draft invoices to send in bulk
                  </div>
                )}
              </div>

              {/* Void Selected */}
              <button
                disabled={bulkLoading}
                onClick={() => setVoidConfirmOpen(true)}
                className="text-white text-[12px] border border-white/30 rounded px-3 py-1.5 hover:bg-white/10 disabled:opacity-50 whitespace-nowrap"
              >
                Void Selected
              </button>

              {/* Clear */}
              <button
                onClick={() => setSelectedIds(new Set())}
                className="text-white/60 hover:text-white transition-colors ml-1"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}

        {/* Void confirmation */}
        {voidConfirmOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
            <div className="bg-white dark:bg-dark-card rounded-[10px] p-6 shadow-xl max-w-sm w-full mx-4">
              <p className="text-[14px] font-medium text-[#111827] dark:text-[#EDEEF0] mb-2">
                Void {selCount} invoice{selCount !== 1 ? 's' : ''}?
              </p>
              <p className="text-[12px] text-[#6B7280] mb-5">This action cannot be undone.</p>
              <div className="flex gap-2 justify-end">
                <button
                  onClick={() => setVoidConfirmOpen(false)}
                  className="px-4 py-2 text-[13px] rounded-[6px] border border-surface-border dark:border-dark-border text-[#374151] dark:text-[#D1D5DB] hover:bg-[#F9FAFB] dark:hover:bg-[#2A2A2A]"
                >
                  Cancel
                </button>
                <button
                  onClick={handleBulkVoid}
                  className="px-4 py-2 text-[13px] rounded-[6px] bg-red-600 text-white hover:bg-red-700"
                >
                  Void
                </button>
              </div>
            </div>
          </div>
        )}

      </div>

      <NewInvoiceModal
        open={newInvoiceOpen}
        onClose={() => setNewInvoiceOpen(false)}
      />
    </AppShell>
  )
}
