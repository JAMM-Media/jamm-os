// path: frontend/src/app/billing/[id]/page.tsx
'use client'

import { useParams } from 'next/navigation'
import { AppShell } from '@/components/layout/AppShell'
import { Breadcrumb } from '@/components/layout/Breadcrumb'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { invoicesApi } from '@/lib/api'
import { useFetch } from '@/lib/hooks/useFetch'
import { formatCurrency } from '@/lib/utils'

type BadgeVariant = Parameters<typeof StatusBadge>[0]['variant']

export default function InvoiceDetailPage() {
  const params = useParams()
  const id = params.id as string
  const { data: invoice, isLoading } = useFetch(() => invoicesApi.get(id), [id])

  if (isLoading) {
    return (
      <AppShell>
        <div className="p-6">
          <div className="h-4 w-32 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded mb-4" />
          <div className="h-8 w-48 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded mb-2" />
          <div className="h-4 w-36 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
        </div>
      </AppShell>
    )
  }

  if (!invoice) {
    return (
      <AppShell>
        <div className="flex items-center justify-center h-full p-6">
          <p className="text-[13px] text-[#6B7280]">Invoice not found.</p>
        </div>
      </AppShell>
    )
  }

  return (
    <AppShell>
      <div className="p-6">
        <Breadcrumb
          items={[
            { label: 'Billing', href: '/billing' },
            { label: invoice.invoiceNumber },
          ]}
        />
        <div className="flex items-start justify-between mb-6">
          <div>
            <h1 className="text-2xl font-medium text-brand dark:text-[#EDEEF0] mb-1">
              {invoice.invoiceNumber}
            </h1>
            <div className="flex items-center gap-2">
              <StatusBadge variant={invoice.status as BadgeVariant} />
              {invoice.dueDate && (
                <span className="text-[12px] text-[#6B7280]">
                  Due {invoice.dueDate}
                </span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-2xl font-medium text-brand dark:text-[#EDEEF0]">
              {formatCurrency(invoice.totalAmount)}
            </span>
            {invoice.status !== 'paid' && (
              <button className="h-9 px-3 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[13px] font-medium hover:opacity-90 transition-opacity">
                Mark as Paid
              </button>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-4 gap-4 mb-4">
          <div className="bg-surface-card dark:bg-dark-card rounded-card p-4">
            <p className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] mb-2">Subtotal</p>
            <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">{formatCurrency(invoice.subtotal)}</p>
          </div>
          <div className="bg-surface-card dark:bg-dark-card rounded-card p-4">
            <p className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] mb-2">Tax</p>
            <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">{formatCurrency(invoice.taxAmount)}</p>
          </div>
          <div className="bg-surface-card dark:bg-dark-card rounded-card p-4">
            <p className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] mb-2">Total</p>
            <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">{formatCurrency(invoice.totalAmount)}</p>
          </div>
          <div className="bg-surface-card dark:bg-dark-card rounded-card p-4">
            <p className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] mb-2">Status</p>
            <StatusBadge variant={invoice.status as BadgeVariant} />
          </div>
        </div>

        {invoice.notes && (
          <div className="bg-surface-card dark:bg-dark-card rounded-card p-4">
            <p className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] mb-2">Notes</p>
            <p className="text-[13px] text-[#374151] dark:text-[#9CA3AF]">{invoice.notes}</p>
          </div>
        )}

        <div className="bg-surface-card dark:bg-dark-card rounded-card p-4 mt-4">
          <p className="text-[12px] text-[#6B7280]">
            Invoice line items and payment history coming in a future phase.
          </p>
        </div>
      </div>
    </AppShell>
  )
}
