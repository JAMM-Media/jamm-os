// frontend/src/components/portal/PortalInvoices.tsx
'use client'

import { useState, useEffect, useCallback } from 'react'
import { useTheme } from 'next-themes'
import {
  CardNumberElement,
  CardExpiryElement,
  CardCvcElement,
  useStripe,
  useElements,
} from '@stripe/react-stripe-js'
import type { StripeCardNumberElementOptions } from '@stripe/stripe-js'
import { toast } from 'sonner'
import { Loader2 } from 'lucide-react'

interface PortalInvoiceItem {
  id: string
  invoice_number: string
  total_amount: number
  status: 'draft' | 'sent' | 'paid' | 'overdue' | 'void'
  due_date: string | null
  sent_at: string | null
  created_at: string
}

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount)
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '—'
  return new Date(dateStr).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

function StatusBadge({ status }: { status: PortalInvoiceItem['status'] }) {
  const classMap: Record<string, string> = {
    sent: 'bg-[#1E3A5F] text-[#7DA3C4]',
    overdue: 'bg-[#7F1D1D] text-[#FCA5A5]',
    paid: 'bg-[#14532D] text-[#86EFAC]',
    draft: 'bg-[#292524] text-[#78716C]',
    void: 'bg-[#292524] text-[#78716C]',
  }
  const labelMap: Record<string, string> = {
    sent: 'Due',
    overdue: 'Overdue',
    paid: 'Paid',
    draft: 'Draft',
    void: 'Void',
  }
  return (
    <span
      className={`text-[10px] font-medium px-1.5 py-0.5 rounded-[4px] ${classMap[status] ?? ''}`}
    >
      {labelMap[status] ?? status}
    </span>
  )
}

interface PaymentFormProps {
  clientSecret: string
  onSuccess: () => void
  onCancel: () => void
}

function PaymentForm({ clientSecret, onSuccess, onCancel }: PaymentFormProps) {
  const stripe = useStripe()
  const elements = useElements()
  const { resolvedTheme } = useTheme()
  const isDark = resolvedTheme !== 'light'
  const [loading, setLoading] = useState(false)
  const [stripeError, setStripeError] = useState<string | null>(null)

  const elementStyle: StripeCardNumberElementOptions['style'] = {
    base: {
      color: isDark ? '#EDEEF0' : '#1F3148',
      fontSize: '13px',
      fontFamily: 'Inter, sans-serif',
      '::placeholder': { color: isDark ? '#6B7280' : '#9CA3AF' },
    },
    invalid: { color: '#991B1B' },
  }

  const fieldBg = isDark ? '#383838' : '#F7F7F8'
  const fieldBorder = isDark ? '#484848' : '#C8CDD6'
  const fieldStyle: React.CSSProperties = {
    background: fieldBg,
    border: `0.5px solid ${fieldBorder}`,
    borderRadius: 6,
    height: 32,
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
      toast.success('Payment received — thank you.')
      onSuccess()
    }
  }

  const wrapperBg = isDark ? '#2A2A2A' : '#F0F1F3'
  const wrapperBorder = isDark ? '#484848' : '#C8CDD6'
  const confirmBg = isDark ? '#3A6A94' : '#1F3148'
  const cancelText = isDark ? '#EDEEF0' : '#1F3148'

  return (
    <div
      style={{
        background: wrapperBg,
        border: `0.5px solid ${wrapperBorder}`,
        borderRadius: 8,
        padding: '12px',
        marginTop: 8,
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
      }}
    >
      <div style={fieldStyle}>
        <CardNumberElement
          options={{
            style: elementStyle,
            classes: { base: 'w-full' },
          }}
        />
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <div style={{ ...fieldStyle, flex: 1 }}>
          <CardExpiryElement
            options={{
              style: elementStyle,
              classes: { base: 'w-full' },
            }}
          />
        </div>
        <div style={{ ...fieldStyle, flex: 1 }}>
          <CardCvcElement
            options={{
              style: elementStyle,
              classes: { base: 'w-full' },
            }}
          />
        </div>
      </div>

      {stripeError && (
        <p style={{ fontSize: 12, color: '#991B1B', margin: 0 }}>{stripeError}</p>
      )}

      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
        <button
          onClick={handleConfirm}
          disabled={loading || !stripe}
          style={{
            height: 32,
            padding: '0 16px',
            borderRadius: 6,
            background: confirmBg,
            color: '#FFFFFF',
            fontSize: 12,
            fontWeight: 500,
            border: 'none',
            cursor: loading || !stripe ? 'not-allowed' : 'pointer',
            opacity: loading || !stripe ? 0.7 : 1,
            display: 'flex',
            alignItems: 'center',
            gap: 6,
          }}
        >
          {loading ? (
            <>
              <Loader2 style={{ width: 12, height: 12 }} className="animate-spin" />
              Processing...
            </>
          ) : (
            'Confirm Payment'
          )}
        </button>
        <button
          onClick={onCancel}
          disabled={loading}
          style={{
            height: 32,
            padding: '0 12px',
            borderRadius: 6,
            background: 'transparent',
            color: cancelText,
            fontSize: 12,
            fontWeight: 500,
            border: `0.5px solid ${fieldBorder}`,
            cursor: loading ? 'not-allowed' : 'pointer',
            opacity: loading ? 0.6 : 1,
          }}
        >
          Cancel
        </button>
      </div>
    </div>
  )
}

export function PortalInvoices() {
  const [invoices, setInvoices] = useState<PortalInvoiceItem[]>([])
  const [loading, setLoading] = useState(true)
  const [fetchError, setFetchError] = useState(false)
  const [activePayId, setActivePayId] = useState<string | null>(null)
  const [clientSecrets, setClientSecrets] = useState<Record<string, string>>({})
  const [payLoading, setPayLoading] = useState<string | null>(null)

  const fetchInvoices = useCallback(async () => {
    setLoading(true)
    setFetchError(false)
    try {
      const token = localStorage.getItem('portal_access_token')
      const res = await fetch('/api/backend/portal/invoices?limit=100', {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (!res.ok) throw new Error('fetch failed')
      const data = await res.json()
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

  const unpaid = invoices.filter((i) => i.status === 'sent' || i.status === 'overdue')
  const paid = invoices.filter((i) => i.status === 'paid')
  const totalOutstanding = unpaid.reduce((sum, i) => sum + Number(i.total_amount), 0)

  if (loading) {
    return (
      <div className="p-5 flex flex-col gap-3 max-w-2xl mx-auto">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-14 rounded-[8px] bg-[#383838] animate-pulse" />
        ))}
      </div>
    )
  }

  if (fetchError) {
    return (
      <div className="p-5 max-w-2xl mx-auto">
        <div className="bg-[#383838] rounded-[8px] px-4 py-6 flex flex-col items-center gap-3">
          <p className="text-[13px] text-[#9CA3AF]">Failed to load invoices.</p>
          <button
            onClick={fetchInvoices}
            className="h-8 px-4 rounded-[6px] bg-[#3A6A94] text-[#EDEEF0] text-[12px] font-medium hover:opacity-90 transition-opacity"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  if (invoices.length === 0) {
    return (
      <div className="p-5 max-w-2xl mx-auto">
        <div className="flex flex-col items-center gap-1 py-12">
          <p className="text-[13px] font-medium text-[#EDEEF0]">No invoices yet.</p>
          <p className="text-[12px] text-[#9CA3AF]">
            Invoices from your accountant will appear here.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="p-5 flex flex-col gap-4 max-w-2xl mx-auto">
      {/* Outstanding balance summary */}
      {unpaid.length > 0 && (
        <div className="bg-[#383838] rounded-[8px] px-4 py-3">
          <p className="text-[11px] text-[#9CA3AF] uppercase tracking-[0.05em]">
            Outstanding balance
          </p>
          <p className="text-[20px] font-medium text-[#EDEEF0] mt-0.5">
            {formatCurrency(totalOutstanding)}
          </p>
        </div>
      )}

      {/* All-paid message */}
      {unpaid.length === 0 && paid.length > 0 && (
        <p className="text-[12px] text-[#9CA3AF] text-center py-4">
          You&apos;re all caught up — no outstanding invoices.
        </p>
      )}

      {/* Unpaid invoices */}
      {unpaid.length > 0 && (
        <div>
          <p className="text-[10px] font-medium text-[#9CA3AF] uppercase tracking-[0.05em] mb-2">
            Due
          </p>
          <div className="flex flex-col gap-2">
            {unpaid.map((inv) => (
              <div key={inv.id}>
                <div className="flex items-center justify-between bg-[#383838] rounded-[8px] px-4 py-3">
                  <div className="flex flex-col gap-0.5">
                    <p className="text-[12px] font-medium text-[#EDEEF0]">
                      {inv.invoice_number}
                    </p>
                    <div className="flex items-center gap-2">
                      <StatusBadge status={inv.status} />
                      <p className="text-[11px] text-[#9CA3AF]">
                        Due {formatDate(inv.due_date)}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-[13px] font-medium text-[#EDEEF0]">
                      {formatCurrency(Number(inv.total_amount))}
                    </span>
                    <button
                      onClick={() => handlePayNow(inv.id)}
                      disabled={payLoading === inv.id}
                      className="h-8 px-3 rounded-[6px] bg-[#3A6A94] text-[#EDEEF0] text-[12px] font-medium hover:opacity-90 transition-opacity flex items-center justify-center gap-1.5 disabled:opacity-60"
                    >
                      {payLoading === inv.id ? (
                        <Loader2 className="w-3 h-3 animate-spin" />
                      ) : (
                        'Pay Now'
                      )}
                    </button>
                  </div>
                </div>
                {activePayId === inv.id && clientSecrets[inv.id] && (
                  <PaymentForm
                    clientSecret={clientSecrets[inv.id]}
                    onSuccess={() => handlePaymentSuccess(inv.id)}
                    onCancel={() => setActivePayId(null)}
                  />
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Paid invoices */}
      {paid.length > 0 && (
        <div>
          <p className="text-[10px] font-medium text-[#9CA3AF] uppercase tracking-[0.05em] mb-2">
            Paid
          </p>
          <div className="flex flex-col gap-2">
            {paid.map((inv) => (
              <div
                key={inv.id}
                className="flex items-center justify-between bg-[#383838] rounded-[8px] px-4 py-3 opacity-70"
              >
                <div className="flex flex-col gap-0.5">
                  <p className="text-[12px] font-medium text-[#EDEEF0]">
                    {inv.invoice_number}
                  </p>
                  <p className="text-[11px] text-[#9CA3AF]">
                    Paid · {formatDate(inv.due_date)}
                  </p>
                </div>
                <span className="text-[13px] font-medium text-[#10B981]">
                  {formatCurrency(Number(inv.total_amount))}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
