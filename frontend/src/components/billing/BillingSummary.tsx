// frontend/src/components/billing/BillingSummary.tsx

import { type Invoice } from '@/lib/api'
import { formatCurrency } from '@/lib/utils'
import { cn } from '@/lib/utils'

interface BillingSummaryProps {
  invoices: Invoice[]
}

function SummaryPill({
  label,
  value,
  accent,
}: {
  label: string
  value: string
  accent?: 'danger' | 'warning' | 'success'
}) {
  return (
    <div className="bg-surface-card dark:bg-dark-card rounded-card px-4 py-3 flex flex-col gap-0.5">
      <span className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em]">
        {label}
      </span>
      <span
        className={cn(
          'text-[15px] font-medium',
          accent === 'danger' && 'text-[#DC2626]',
          accent === 'warning' && 'text-[#D97706]',
          accent === 'success' && 'text-[#16A34A]',
          !accent && 'text-brand dark:text-[#EDEEF0]'
        )}
      >
        {value}
      </span>
    </div>
  )
}

export function BillingSummary({ invoices }: BillingSummaryProps) {
  const outstanding = invoices
    .filter((i) => i.status === 'sent' || i.status === 'overdue')
    .reduce((sum, i) => sum + i.totalAmount, 0)

  const overdue = invoices
    .filter((i) => i.status === 'overdue')
    .reduce((sum, i) => sum + i.totalAmount, 0)

  const collected = invoices
    .filter((i) => i.status === 'paid')
    .reduce((sum, i) => sum + i.totalAmount, 0)

  const draft = invoices
    .filter((i) => i.status === 'draft')
    .reduce((sum, i) => sum + i.totalAmount, 0)

  return (
    <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
      <SummaryPill label="Outstanding" value={formatCurrency(outstanding)} accent="warning" />
      <SummaryPill label="Overdue" value={formatCurrency(overdue)} accent="danger" />
      <SummaryPill label="Collected" value={formatCurrency(collected)} accent="success" />
      <SummaryPill label="Draft" value={formatCurrency(draft)} />
    </div>
  )
}
