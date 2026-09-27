// path: frontend/src/app/billing/[id]/page.tsx
'use client'

import { useState } from 'react'
import { useParams } from 'next/navigation'
import { Breadcrumb } from '@/components/layout/Breadcrumb'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { invoicesApi, clientsApi } from '@/lib/api'
import { useFetch } from '@/lib/hooks/useFetch'
import { useConfirm } from '@/lib/hooks/useConfirm'
import { useAlert } from '@/lib/hooks/useAlert'
import { formatCurrency } from '@/lib/utils'

type BadgeVariant = Parameters<typeof StatusBadge>[0]['variant']

function BillingDetailBodySkeleton() {
  return (
    <div className="p-6 pt-0 flex flex-col gap-4">
      <div className="grid grid-cols-1 xl:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="bg-surface-card dark:bg-dark-card rounded-card border border-surface-border dark:border-dark-border p-6">
            <div className="h-2.5 w-16 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded mb-3" />
            <div className="h-4 w-14 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
          </div>
        ))}
      </div>
      <div className="bg-surface-card dark:bg-dark-card rounded-card border border-surface-border dark:border-dark-border p-5">
        <div className="h-3 w-3/4 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
      </div>
    </div>
  )
}

export default function InvoiceDetailPage() {
  const params = useParams()
  const id = params.id as string
  const { data: invoice, isLoading, refetch } = useFetch(() => invoicesApi.get(id), [id])
  const { data: client } = useFetch(
    () => invoice ? clientsApi.get(invoice.clientId) : Promise.resolve(null),
    [invoice?.clientId],
  )
  const { confirm, ConfirmDialog } = useConfirm()
  const { alert, AlertDialog } = useAlert()
  const [actionLoading, setActionLoading] = useState(false)

  async function handleSend() {
    setActionLoading(true)
    try {
      await invoicesApi.send(id)
      refetch()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Send failed.'
      await alert(msg)
    } finally {
      setActionLoading(false)
    }
  }

  async function handleVoid() {
    const ok = await confirm({ message: 'Void this invoice? This cannot be undone.', confirmLabel: 'Void', destructive: true })
    if (!ok) return
    setActionLoading(true)
    try {
      await invoicesApi.void(id)
      refetch()
    } catch {
      await alert('Void failed. Please try again.')
    } finally {
      setActionLoading(false)
    }
  }

  if (isLoading) {
    return (
      <>
        <div className="p-6">
          <div className="h-4 w-32 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded mb-4" />
          <div className="h-8 w-48 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded mb-2" />
          <div className="h-4 w-36 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
        </div>
        <BillingDetailBodySkeleton />
      </>
    )
  }

  if (!invoice) {
    return (
        <div className="flex items-center justify-center h-full p-6">
          <p className="text-[13px] text-[#6B7280]">Invoice not found.</p>
        </div>
    )
  }

  return (
      <div className="p-6">
        {ConfirmDialog}
        {AlertDialog}
        <Breadcrumb
          items={[
            { label: 'Billing', href: '/billing' },
            { label: invoice.invoiceNumber },
          ]}
        />
        <div className="flex items-start justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold text-brand dark:text-[#EDEEF0] mb-1">
              {invoice.invoiceNumber}
            </h1>
            {client && (
              <p className="text-[13px] text-[#6B7280] mb-2">{client.name}</p>
            )}
            <div className="flex items-center gap-3">
              <StatusBadge variant={invoice.status as BadgeVariant} />
              {invoice.dueDate && (
                <span className="text-[11px] text-[#6B7280]">
                  Due {invoice.dueDate}
                </span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-3xl font-bold text-brand dark:text-[#EDEEF0]">
              {formatCurrency(invoice.totalAmount)}
            </span>
            {!invoice.sentAt && !['paid', 'void'].includes(invoice.status) && (
              <button
                onClick={handleSend}
                disabled={actionLoading}
                className="h-9 px-3 rounded-[6px] border border-surface-border dark:border-dark-border text-[13px] font-medium text-brand dark:text-[#EDEEF0] hover:opacity-80 disabled:opacity-50 transition-opacity"
              >
                Send
              </button>
            )}
            {!['paid', 'void'].includes(invoice.status) && (
              <button
                onClick={handleVoid}
                disabled={actionLoading}
                className="h-9 px-3 rounded-[6px] border border-surface-border dark:border-dark-border text-[13px] font-medium text-[#6B7280] hover:text-red-600 dark:hover:text-red-400 disabled:opacity-50 transition-colors"
              >
                Void
              </button>
            )}
            {!['paid', 'void'].includes(invoice.status) && (
              <button className="h-9 px-3 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[13px] font-medium hover:opacity-90 transition-opacity">
                Mark as Paid
              </button>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-4 gap-4 mb-6">
          <div className="bg-surface-card dark:bg-dark-card rounded-card border border-surface-border dark:border-dark-border p-6">
            <p className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] mb-3">Subtotal</p>
            <p className="text-[16px] font-semibold text-brand dark:text-[#EDEEF0]">{formatCurrency(invoice.subtotal)}</p>
          </div>
          <div className="bg-surface-card dark:bg-dark-card rounded-card border border-surface-border dark:border-dark-border p-6">
            <p className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] mb-3">Tax</p>
            <p className="text-[16px] font-semibold text-brand dark:text-[#EDEEF0]">{formatCurrency(invoice.taxAmount)}</p>
          </div>
          <div className="bg-surface-card dark:bg-dark-card rounded-card border border-surface-border dark:border-dark-border p-6">
            <p className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] mb-3">Total</p>
            <p className="text-[16px] font-semibold text-brand dark:text-[#EDEEF0]">{formatCurrency(invoice.totalAmount)}</p>
          </div>
          <div className="bg-surface-card dark:bg-dark-card rounded-card border border-surface-border dark:border-dark-border p-6">
            <p className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] mb-3">Status</p>
            <StatusBadge variant={invoice.status as BadgeVariant} />
          </div>
        </div>

        {invoice.notes && (
          <div className="bg-surface-card dark:bg-dark-card rounded-card border border-surface-border dark:border-dark-border p-5 mb-6">
            <p className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] mb-2">Notes</p>
            <p className="text-[13px] text-[#374151] dark:text-[#9CA3AF]">{invoice.notes}</p>
          </div>
        )}

        <div className="bg-surface-card dark:bg-dark-card rounded-card border border-surface-border dark:border-dark-border p-5">
          {invoice.lineItems.length > 0 ? (
            <table className="w-full table-fixed text-[13px]">
              <colgroup>
                <col style={{ width: '50%' }} />
                <col style={{ width: '15%' }} />
                <col style={{ width: '17.5%' }} />
                <col style={{ width: '17.5%' }} />
              </colgroup>
              <thead>
                <tr className="border-b-[3px] border-surface-border dark:border-dark-border">
                  <th className="text-left text-[11px] font-semibold text-[#6B7280] uppercase tracking-[0.05em] pb-4">Description</th>
                  <th className="text-right text-[11px] font-semibold text-[#6B7280] uppercase tracking-[0.05em] pb-4">Quantity</th>
                  <th className="text-right text-[11px] font-semibold text-[#6B7280] uppercase tracking-[0.05em] pb-4">Rate</th>
                  <th className="text-right text-[11px] font-semibold text-[#6B7280] uppercase tracking-[0.05em] pb-4">Amount</th>
                </tr>
              </thead>
              <tbody>
                {invoice.lineItems.map((item, i) => (
                  <tr key={i} className="border-b border-surface-border dark:border-dark-border last:border-0">
                    <td className="py-3.5 text-[#374151] dark:text-[#9CA3AF]">{item.description}</td>
                    <td className="py-3.5 text-right text-[#374151] dark:text-[#9CA3AF]">{item.quantity}</td>
                    <td className="py-3.5 text-right text-[#374151] dark:text-[#9CA3AF]">{formatCurrency(item.unitPrice)}</td>
                    <td className="py-3.5 text-right text-[#374151] dark:text-[#9CA3AF]">{formatCurrency(item.total ?? item.amount ?? 0)}</td>
                  </tr>
                ))}
                <tr>
                  <td colSpan={3} className="pt-4 text-right text-[13px] font-semibold text-brand dark:text-[#EDEEF0]">Subtotal</td>
                  <td className="pt-4 text-right text-[13px] font-semibold text-brand dark:text-[#EDEEF0]">{formatCurrency(invoice.subtotal)}</td>
                </tr>
              </tbody>
            </table>
          ) : (
            <p className="text-[12px] text-[#6B7280]">No line items recorded for this invoice.</p>
          )}
        </div>
      </div>
  )
}
