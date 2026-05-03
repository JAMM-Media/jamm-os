// frontend/src/components/billing/InvoiceCard.tsx
'use client'

import { useRouter } from 'next/navigation'
import { type Invoice } from '@/lib/api'
import { formatCurrency } from '@/lib/mock/invoices'
import { StatusBadge } from '@/components/ui/StatusBadge'

type BadgeVariant = Parameters<typeof StatusBadge>[0]['variant']

interface InvoiceCardProps {
  invoice: Invoice
  clientMap?: Record<string, string>
  lookupsLoading?: boolean
}

export function InvoiceCard({ invoice, clientMap = {}, lookupsLoading = false }: InvoiceCardProps) {
  const router = useRouter()

  return (
    <div
      onClick={() => router.push(`/billing/${invoice.id}`)}
      className="bg-surface-card dark:bg-dark-card rounded-card p-[13px] cursor-pointer hover:brightness-95 dark:hover:brightness-110 transition-all"
    >
      <div className="flex items-start justify-between mb-1">
        <span className="text-[12px] font-medium text-brand dark:text-[#EDEEF0]">
          {invoice.invoiceNumber}
        </span>
        <StatusBadge variant={invoice.status as BadgeVariant} />
      </div>
      <div className="text-[11px] text-[#6B7280] mb-2 truncate">
        {lookupsLoading ? (
          <div className="h-2 w-[60px] bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded inline-block" />
        ) : (
          clientMap[invoice.clientId] ?? (invoice.clientId ? <span className="text-[#6B7280]">Unknown</span> : '—')
        )}
      </div>
      <div className="flex items-center justify-between">
        <span className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">
          {formatCurrency(invoice.totalAmount)}
        </span>
        <span className="text-[11px] text-[#6B7280]">
          Due {invoice.dueDate ?? '—'}
        </span>
      </div>
    </div>
  )
}
