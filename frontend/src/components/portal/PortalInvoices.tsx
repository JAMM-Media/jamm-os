// frontend/src/components/portal/PortalInvoices.tsx
'use client'

import { formatLocalDate } from '@/lib/utils'
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  CardCvcElement,
  CardExpiryElement,
  CardNumberElement,
  useElements,
  useStripe,
} from '@stripe/react-stripe-js'
import type { StripeCardNumberElementOptions } from '@stripe/stripe-js'
import { toast } from 'sonner'
import {
  CheckCircle2,
  DollarSign,
  Download,
  FileText,
  Loader2,
  Mail,
  MoreHorizontal,
  Receipt,
} from 'lucide-react'
import { getPortalInvoices } from '@/lib/portal-api'
import type { PortalInvoice as PortalInvoiceItem } from '@/lib/portal-api'

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount)
}

function formatDate(dateStr: string | null): string {
  return formatLocalDate(dateStr, { month: 'short', day: 'numeric', year: 'numeric' })
}

function getDescription(inv: PortalInvoiceItem): string {
  const items = inv.line_items ?? []
  if (items.length === 0) return 'Invoice'
  if (items.length === 1) return items[0].description
  return `${items[0].description} +${items.length - 1} more`
}

function StatusBadge({ status }: { status: PortalInvoiceItem['status'] }) {
  const styleMap: Record<string, { bg: string; text: string; label: string }> = {
    sent:    { bg: '#FEF3C7', text: '#92400E', label: 'Due' },
    overdue: { bg: '#FEE2E2', text: '#991B1B', label: 'Overdue' },
    paid:    { bg: '#D1FAE5', text: '#065F46', label: 'Paid' },
    draft:   { bg: '#F3F4F6', text: '#9CA3AF', label: 'Draft' },
    void:    { bg: '#F3F4F6', text: '#9CA3AF', label: 'Void' },
  }
  const s = styleMap[status] ?? styleMap.draft
  return (
    <span
      className="text-[11px] font-medium px-2 py-0.5 rounded-full whitespace-nowrap"
      style={{ backgroundColor: s.bg, color: s.text }}
    >
      {s.label}
    </span>
  )
}

// PaymentForm: real Stripe card-entry widget. Preserved exactly from prior implementation.
// Hardcoded to light theme since the portal page is always light-themed.
interface PaymentFormProps {
  clientSecret: string
  onSuccess: () => void
  onCancel: () => void
}

function PaymentForm({ clientSecret, onSuccess, onCancel }: PaymentFormProps) {
  const stripe = useStripe()
  const elements = useElements()
  const [loading, setLoading] = useState(false)
  const [stripeError, setStripeError] = useState<string | null>(null)

  const elementStyle: StripeCardNumberElementOptions['style'] = {
    base: {
      color: '#1F3148',
      fontSize: '13px',
      fontFamily: 'Inter, sans-serif',
      '::placeholder': { color: '#9CA3AF' },
    },
    invalid: { color: '#991B1B' },
  }

  const fieldStyle: React.CSSProperties = {
    background: '#F7F8FA',
    border: '1px solid #E5E7EB',
    borderRadius: 6,
    height: 36,
    padding: '0 12px',
    display: 'flex',
    alignItems: 'center',
  }

  async function handleConfirm() {
    if (!stripe || !elements) return
    const cardElement = elements.getElement(CardNumberElement)
    if (!cardElement) return

    setLoading(true)
    setStripeError(null)

    const { error, paymentIntent } = await stripe.confirmCardPayment(clientSecret, {
      payment_method: { card: cardElement },
    })

    setLoading(false)

    if (error) {
      setStripeError(error.message ?? 'Payment failed. Please try again.')
      return
    }

    if (paymentIntent?.status === 'succeeded') {
      toast.success('Payment received. Thank you.')
      onSuccess()
    }
  }

  return (
    <div className="mt-3 bg-white rounded-xl border border-gray-100 p-4 flex flex-col gap-3">
      <p className="text-[13px] font-medium" style={{ color: '#1F3148' }}>Enter card details</p>
      <div style={fieldStyle}>
        <CardNumberElement options={{ style: elementStyle, classes: { base: 'w-full' } }} />
      </div>
      <div className="flex gap-3">
        <div style={{ ...fieldStyle, flex: 1 }}>
          <CardExpiryElement options={{ style: elementStyle, classes: { base: 'w-full' } }} />
        </div>
        <div style={{ ...fieldStyle, flex: 1 }}>
          <CardCvcElement options={{ style: elementStyle, classes: { base: 'w-full' } }} />
        </div>
      </div>

      {stripeError && (
        <p className="text-[12px]" style={{ color: '#DC2626' }}>{stripeError}</p>
      )}

      <div className="flex items-center gap-2 mt-1">
        <button
          onClick={handleConfirm}
          disabled={loading || !stripe}
          className="h-9 px-4 rounded-md text-[13px] font-medium text-white flex items-center gap-2 disabled:opacity-60 transition-opacity hover:opacity-90"
          style={{ backgroundColor: '#1F3148' }}
        >
          {loading ? (
            <><Loader2 className="w-3.5 h-3.5 animate-spin" />Processing...</>
          ) : (
            'Confirm payment'
          )}
        </button>
        <button
          onClick={onCancel}
          disabled={loading}
          className="h-9 px-4 rounded-md text-[13px] border border-gray-200 transition-colors hover:bg-gray-50 disabled:opacity-60"
          style={{ color: '#6B7280' }}
        >
          Cancel
        </button>
      </div>
    </div>
  )
}

type StatusFilter = 'all' | 'sent' | 'overdue' | 'paid' | 'draft' | 'void'

// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function PortalInvoices({ accentColor: _a, cardColor: _c, portalMode: _p, textPrimary: _tp, textMuted: _tm }: { accentColor?: string; cardColor?: string; portalMode?: 'light' | 'dark'; textPrimary?: string; textMuted?: string }) {
  const [invoices, setInvoices] = useState<PortalInvoiceItem[]>([])
  const [loading, setLoading] = useState(true)
  const [fetchError, setFetchError] = useState(false)

  // Payment state
  const [activePayId, setActivePayId] = useState<string | null>(null)
  const [clientSecrets, setClientSecrets] = useState<Record<string, string>>({})
  const [payLoading, setPayLoading] = useState<string | null>(null)

  // Filter state
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')

  // Three-dot menu state
  const [openMenuId, setOpenMenuId] = useState<string | null>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  const fetchInvoices = useCallback(async () => {
    setLoading(true)
    setFetchError(false)
    try {
      const data = await getPortalInvoices()
      setInvoices(data.items ?? [])
    } catch {
      setFetchError(true)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchInvoices()
  }, [fetchInvoices])

  // Close three-dot menu on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpenMenuId(null)
      }
    }
    if (openMenuId) {
      document.addEventListener('mousedown', handleClickOutside)
    }
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [openMenuId])

  async function handlePayNow(invoiceId: string) {
    if (clientSecrets[invoiceId]) {
      setActivePayId(invoiceId)
      return
    }
    setPayLoading(invoiceId)
    try {
      const token = localStorage.getItem('portal_access_token')
      const res = await fetch(`/api/backend/portal/invoices/${invoiceId}/pay`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      })
      if (!res.ok) throw new Error('pay failed')
      const data = await res.json()
      setClientSecrets((prev) => ({ ...prev, [invoiceId]: data.client_secret }))
      setActivePayId(invoiceId)
    } catch {
      toast.error('Could not initiate payment. Please try again.')
    } finally {
      setPayLoading(null)
    }
  }

  function handlePaymentSuccess(invoiceId: string) {
    setInvoices((prev) =>
      prev.map((inv) => (inv.id === invoiceId ? { ...inv, status: 'paid' as const } : inv))
    )
    setActivePayId(null)
  }

  // Download PDF: real -- fetches with auth header, triggers browser download
  async function handleDownloadPdf(inv: PortalInvoiceItem) {
    setOpenMenuId(null)
    const token = localStorage.getItem('portal_access_token')
    try {
      const res = await fetch(`/api/backend/portal/invoices/${inv.id}/pdf`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (!res.ok) throw new Error('Download failed')
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `invoice-${inv.invoice_number}.pdf`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch {
      toast.error('Could not download invoice. Please try again.')
    }
  }

  // Compute stats
  const currentYear = new Date().getFullYear()
  const unpaid = invoices.filter((i) => i.status === 'sent' || i.status === 'overdue')
  const paid = invoices.filter((i) => i.status === 'paid')
  const paidThisYear = paid.filter((i) => {
    if (!i.paid_at) return false
    return new Date(i.paid_at).getFullYear() === currentYear
  })
  const totalDue = unpaid.reduce((sum, i) => sum + Number(i.total_amount), 0)
  const totalPaidThisYear = paidThisYear.reduce((sum, i) => sum + Number(i.total_amount), 0)
  const totalCount = invoices.filter((i) => i.status !== 'draft').length

  // Apply status filter
  const filtered = statusFilter === 'all'
    ? invoices
    : invoices.filter((i) => i.status === statusFilter)

  if (loading) {
    return (
      <div className="p-6 flex flex-col gap-4">
        <div className="grid grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="bg-white rounded-xl border border-gray-100 p-4 h-24 animate-pulse" />
          ))}
        </div>
        <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-14 border-b border-gray-100 animate-pulse bg-gray-50" />
          ))}
        </div>
      </div>
    )
  }

  if (fetchError) {
    return (
      <div className="p-6">
        <div className="bg-white rounded-xl border border-gray-100 p-10 flex flex-col items-center gap-3">
          <p className="text-[13px]" style={{ color: '#6B7280' }}>Failed to load invoices.</p>
          <button
            onClick={fetchInvoices}
            className="h-9 px-4 rounded-md text-[13px] font-medium text-white transition-opacity hover:opacity-90"
            style={{ backgroundColor: '#1F3148' }}
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  const STAT_CARDS = [
    {
      label: 'Open invoices',
      value: String(unpaid.length),
      chipBg: '#DBEAFE',
      chipColor: '#1E40AF',
      Icon: FileText,
    },
    {
      label: 'Total due',
      value: formatCurrency(totalDue),
      chipBg: '#FEF3C7',
      chipColor: '#D97706',
      Icon: DollarSign,
    },
    {
      label: 'Paid this year',
      value: formatCurrency(totalPaidThisYear),
      chipBg: '#D1FAE5',
      chipColor: '#059669',
      Icon: CheckCircle2,
    },
    {
      label: 'Total invoices',
      value: String(totalCount),
      chipBg: '#F3F4F6',
      chipColor: '#6B7280',
      Icon: Receipt,
    },
  ]

  return (
    <div className="p-6 flex flex-col gap-5">
      {/* Page heading */}
      <div>
        <h1 className="text-[20px] font-bold" style={{ color: '#1F3148' }}>Invoices</h1>
        <p className="text-[13px] mt-0.5" style={{ color: '#6B7280' }}>
          View and pay your invoices, and keep track of your payment history.
        </p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-4 gap-4">
        {STAT_CARDS.map((card) => (
          <div key={card.label} className="bg-white rounded-xl border border-gray-100 px-5 py-4 flex items-center gap-4">
            <div
              className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
              style={{ backgroundColor: card.chipBg }}
            >
              <card.Icon size={18} style={{ color: card.chipColor }} />
            </div>
            <div className="flex flex-col min-w-0">
              <p className="text-[11px] font-medium mb-1" style={{ color: '#9CA3AF' }}>{card.label}</p>
              <p className="text-[24px] font-semibold leading-none mb-1" style={{ color: '#1F3148' }}>
                {card.value}
              </p>
              <button
                onClick={() => setStatusFilter('all')}
                className="mt-1.5 text-left text-[11px] font-medium transition-opacity hover:opacity-70 self-start"
                style={{ color: '#3A6A94' }}
              >
                View all
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Filter row + table */}
      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <p className="text-[14px] font-semibold" style={{ color: '#1F3148' }}>All invoices</p>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
            className="h-8 px-3 rounded-md text-[12px] border border-gray-200 bg-white focus:outline-none focus:border-[#1F3148] transition-colors cursor-pointer"
            style={{ color: '#1F3148' }}
          >
            <option value="all">All statuses</option>
            <option value="sent">Due</option>
            <option value="overdue">Overdue</option>
            <option value="paid">Paid</option>
            <option value="draft">Draft</option>
            <option value="void">Void</option>
          </select>
        </div>

        {filtered.length === 0 ? (
          <div className="bg-white rounded-xl border border-gray-100 p-10 text-center">
            <p className="text-[13px]" style={{ color: '#6B7280' }}>
              {invoices.length === 0
                ? 'Invoices from your accountant will appear here.'
                : 'No invoices match the selected filter.'}
            </p>
          </div>
        ) : (
          <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
            {/* Table header */}
            <div className="grid grid-cols-[1fr_2fr_1fr_1fr_120px_140px] gap-0 border-b border-gray-100 px-4 py-2.5">
              {['Invoice #', 'Description', 'Amount', 'Due date', 'Status', 'Action'].map((h) => (
                <p key={h} className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: '#9CA3AF' }}>
                  {h}
                </p>
              ))}
            </div>

            {/* Table rows */}
            {filtered.map((inv) => (
              <div key={inv.id}>
                <div className="grid grid-cols-[1fr_2fr_1fr_1fr_120px_140px] items-center gap-0 px-4 py-3.5 border-b border-gray-100 last:border-b-0 hover:bg-gray-50 transition-colors">
                  {/* Invoice # */}
                  <p className="text-[13px] font-medium" style={{ color: '#1F3148' }}>
                    {inv.invoice_number}
                  </p>

                  {/* Description */}
                  <p className="text-[13px] truncate pr-4" style={{ color: '#6B7280' }}>
                    {getDescription(inv)}
                  </p>

                  {/* Amount */}
                  <p className="text-[13px] font-medium" style={{ color: '#1F3148' }}>
                    {formatCurrency(Number(inv.total_amount))}
                  </p>

                  {/* Due date */}
                  <p className="text-[13px]" style={{ color: '#6B7280' }}>
                    {formatDate(inv.due_date)}
                  </p>

                  {/* Status */}
                  <div>
                    <StatusBadge status={inv.status} />
                  </div>

                  {/* Action */}
                  <div className="flex items-center gap-2 relative" ref={openMenuId === inv.id ? menuRef : null}>
                    {inv.status === 'sent' || inv.status === 'overdue' ? (
                      <button
                        onClick={() => handlePayNow(inv.id)}
                        disabled={payLoading === inv.id}
                        className="h-8 px-3 rounded-md text-[12px] font-medium text-white flex items-center gap-1.5 disabled:opacity-60 transition-opacity hover:opacity-90"
                        style={{ backgroundColor: '#1F3148' }}
                      >
                        {payLoading === inv.id ? (
                          <Loader2 className="w-3 h-3 animate-spin" />
                        ) : (
                          'Pay now'
                        )}
                      </button>
                    ) : inv.status === 'paid' ? (
                      <button
                        onClick={() => handleDownloadPdf(inv)}
                        className="h-8 px-3 rounded-md text-[12px] font-medium border border-gray-200 transition-colors hover:bg-gray-50"
                        style={{ color: '#6B7280' }}
                      >
                        View
                      </button>
                    ) : null}

                    {/* Three-dot menu button */}
                    <button
                      onClick={() => setOpenMenuId(openMenuId === inv.id ? null : inv.id)}
                      className="w-7 h-7 rounded-md flex items-center justify-center transition-colors hover:bg-gray-100"
                      style={{ color: '#9CA3AF' }}
                      aria-label="More options"
                    >
                      <MoreHorizontal size={15} />
                    </button>

                    {/* Three-dot dropdown menu */}
                    {openMenuId === inv.id && (
                      <div
                        className="absolute right-0 top-full mt-1 w-44 bg-white rounded-xl border border-gray-100 shadow-lg z-20 overflow-hidden"
                        ref={menuRef}
                      >
                        {/* Download PDF -- real */}
                        <button
                          onClick={() => handleDownloadPdf(inv)}
                          className="w-full flex items-center gap-2.5 px-3 py-2.5 text-[13px] transition-colors hover:bg-gray-50 text-left"
                          style={{ color: '#1F3148' }}
                        >
                          <Download size={13} style={{ color: '#6B7280' }} />
                          Download PDF
                        </button>

                        {/* Email a copy -- disabled, no portal endpoint exists */}
                        <div
                          className="flex items-start gap-2.5 px-3 py-2.5 border-t border-gray-100"
                          title="Email delivery coming soon"
                        >
                          <Mail size={13} className="mt-0.5 flex-shrink-0" style={{ color: '#C4C9D1' }} />
                          <div>
                            <p className="text-[13px]" style={{ color: '#C4C9D1' }}>Email a copy</p>
                            <p className="text-[10px]" style={{ color: '#C4C9D1' }}>Coming soon</p>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* Stripe payment form, shown inline below the row */}
                {activePayId === inv.id && clientSecrets[inv.id] && (
                  <div className="px-4 pb-4">
                    <PaymentForm
                      clientSecret={clientSecrets[inv.id]}
                      onSuccess={() => handlePaymentSuccess(inv.id)}
                      onCancel={() => setActivePayId(null)}
                    />
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
