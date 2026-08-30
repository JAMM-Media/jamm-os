// frontend/src/components/portal/PortalBillingDetail.tsx
'use client'

import { useState, useEffect } from 'react'
import { ChevronRight, ChevronDown, Receipt, TrendingUp, Clock } from 'lucide-react'
import {
  getPortalBillingDetail,
  type BillingDetailData,
  type BillingDetailGroup,
  type BillingDetailInvoiceEntry,
} from '@/lib/portal-api'

interface Props {
  cardColor: string
  accentColor: string
  portalMode: 'light' | 'dark'
  textPrimary: string
  textMuted: string
}

function formatCurrency(n: number): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(n)
}

function formatDate(iso: string | null): string {
  if (!iso) return 'N/A'
  const d = new Date(iso + 'T00:00:00')
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

const STAT_CARDS = [
  {
    key: 'billed',
    label: 'Total billed this year',
    chipBg: '#D1FAE5',
    chipColor: '#059669',
    Icon: Receipt,
    format: (d: BillingDetailData) => formatCurrency(d.total_billed_this_year),
  },
  {
    key: 'avg',
    label: 'Average per engagement',
    chipBg: '#DBEAFE',
    chipColor: '#1E40AF',
    Icon: TrendingUp,
    format: (d: BillingDetailData) => formatCurrency(d.average_per_engagement),
  },
  {
    key: 'hours',
    label: 'Total hours this year',
    chipBg: '#EDE9FE',
    chipColor: '#7C3AED',
    Icon: Clock,
    format: (d: BillingDetailData) => d.total_hours_this_year.toFixed(2),
  },
] as const

// Column grid: engagement | description | line-total
const GRID = 'grid grid-cols-[2fr_3fr_148px]'

export function PortalBillingDetail({ cardColor: _c, accentColor: _a, portalMode: _p, textPrimary: _tp, textMuted: _tm }: Props) {
  const [data, setData] = useState<BillingDetailData | null>(null)
  const [loading, setLoading] = useState(true)
  const [fetchError, setFetchError] = useState(false)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  useEffect(() => {
    getPortalBillingDetail()
      .then(setData)
      .catch(() => setFetchError(true))
      .finally(() => setLoading(false))
  }, [])

  function toggleExpand(engagementKey: string) {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(engagementKey)) {
        next.delete(engagementKey)
      } else {
        next.add(engagementKey)
      }
      return next
    })
  }

  if (loading) {
    return (
      <div className="p-5 max-w-4xl w-full flex flex-col gap-6">
        <div>
          <div className="h-5 w-40 bg-gray-200 rounded animate-pulse mb-1.5" />
          <div className="h-3.5 w-72 bg-gray-100 rounded animate-pulse" />
        </div>
        <div className="grid grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="bg-white rounded-xl border border-gray-100 px-5 py-4 flex items-center gap-4">
              <div className="w-10 h-10 rounded-lg bg-gray-100 animate-pulse flex-shrink-0" />
              <div className="flex flex-col gap-2 flex-1">
                <div className="h-2.5 w-24 bg-gray-100 rounded animate-pulse" />
                <div className="h-5 w-20 bg-gray-200 rounded animate-pulse" />
              </div>
            </div>
          ))}
        </div>
        <div className="bg-white rounded-xl border border-gray-100 h-48 animate-pulse" />
      </div>
    )
  }

  if (fetchError || !data) {
    return (
      <div className="p-8 flex flex-col items-center justify-center gap-2 text-center">
        <p className="text-[14px] font-medium" style={{ color: '#1F3148' }}>
          Could not load billing detail.
        </p>
        <p className="text-[13px]" style={{ color: '#6B7280' }}>
          Please try refreshing the page.
        </p>
      </div>
    )
  }

  const { groups } = data
  const grandTotal = groups.reduce((sum, g) => sum + g.combined_subtotal, 0)

  return (
    <div className="p-5 max-w-4xl w-full flex flex-col gap-6">

      {/* Page header */}
      <div>
        <h1 className="text-[20px] font-bold" style={{ color: '#1F3148' }}>Billing Detail</h1>
        <p className="text-[13px] mt-0.5" style={{ color: '#6B7280' }}>
          A breakdown of the services and charges billed to you.
        </p>
      </div>

      {/* Stat cards -- static summaries, no links or arrows */}
      {/* Average per engagement is suppressed when only 1 engagement billed this year */}
      <div className={`grid gap-4 ${data.engagements_this_year_count > 1 ? 'grid-cols-3' : 'grid-cols-2'}`}>
        {STAT_CARDS.filter((card) => card.key !== 'avg' || data.engagements_this_year_count > 1).map((card) => (
          <div key={card.key} className="bg-white rounded-xl border border-gray-100 px-5 py-4 flex items-center gap-4">
            <div
              className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
              style={{ backgroundColor: card.chipBg }}
            >
              <card.Icon size={18} style={{ color: card.chipColor }} />
            </div>
            <div className="flex flex-col min-w-0">
              <p className="text-[11px] font-medium mb-1" style={{ color: '#9CA3AF' }}>{card.label}</p>
              <p className="text-[24px] font-semibold leading-none mb-1" style={{ color: '#1F3148' }}>
                {card.format(data)}
              </p>
            </div>
          </div>
        ))}
      </div>

      {/* Billing table */}
      {groups.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-100 p-8 flex flex-col items-center justify-center gap-2 text-center">
          <p className="text-[14px] font-medium" style={{ color: '#1F3148' }}>No billing history yet.</p>
          <p className="text-[13px]" style={{ color: '#6B7280' }}>Your firm will share billing summaries here.</p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">

          {/* Column headers */}
          <div className={`${GRID} items-center px-4 py-2.5 bg-gray-50 border-b border-gray-100`}>
            <span className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: '#9CA3AF' }}>Engagement</span>
            <span className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: '#9CA3AF' }}>Description</span>
            <span className="text-right text-[11px] font-semibold uppercase tracking-wide" style={{ color: '#9CA3AF' }}>Line total</span>
          </div>

          {/* Engagement groups -- one row per distinct engagement */}
          {groups.map((group: BillingDetailGroup) => {
            const isOpen = expanded.has(group.engagement_key)
            return (
              <div key={group.engagement_key} className="border-b border-gray-100 last:border-b-0">

                {/* Engagement header row */}
                <button
                  type="button"
                  onClick={() => toggleExpand(group.engagement_key)}
                  className={`${GRID} w-full items-center px-4 py-3 bg-[#F9FAFB] text-left hover:bg-gray-100 transition-colors`}
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    {isOpen
                      ? <ChevronDown size={14} className="flex-shrink-0" style={{ color: '#9CA3AF' }} />
                      : <ChevronRight size={14} className="flex-shrink-0" style={{ color: '#9CA3AF' }} />
                    }
                    <div className="text-[13px] font-medium truncate" style={{ color: '#1F3148' }}>
                      {group.engagement_name}
                    </div>
                  </div>

                  <div />

                  <div className="text-right">
                    {group.combined_hours > 0 && (
                      <div className="text-[11px]" style={{ color: '#6B7280' }}>
                        {group.combined_hours.toFixed(2)} hrs
                      </div>
                    )}
                    <div className="text-[13px] font-medium" style={{ color: '#1F3148' }}>
                      Subtotal {formatCurrency(group.combined_subtotal)}
                    </div>
                  </div>
                </button>

                {/* Invoices within this engagement (when expanded) */}
                {isOpen && group.invoices.map((invoice: BillingDetailInvoiceEntry, invIdx: number) => (
                  <div key={invoice.invoice_id}>

                    {/* Invoice sub-header: section label, date + supporting metadata */}
                    <div className={`${GRID} items-center px-4 py-2 bg-gray-50/50 ${invIdx > 0 ? 'border-t border-gray-100' : ''}`}>
                      <div className="pl-6 text-[11px] font-semibold uppercase tracking-wide" style={{ color: '#9CA3AF' }}>
                        Billed on {formatDate(invoice.billed_on)}
                      </div>
                      <div />
                      <div className="text-right">
                        {invoice.aggregate_hours > 0 && (
                          <div className="text-[11px]" style={{ color: '#9CA3AF' }}>
                            {invoice.aggregate_hours.toFixed(2)} hrs
                          </div>
                        )}
                        <div className="text-[11px]" style={{ color: '#9CA3AF' }}>
                          {formatCurrency(invoice.subtotal)}
                        </div>
                      </div>
                    </div>

                    {/* Invoice line items */}
                    {invoice.line_items.length === 0 ? (
                      <div className={`${GRID} items-center px-4 py-2 border-t border-gray-50`}>
                        <div />
                        <div className="text-[13px] italic" style={{ color: '#9CA3AF' }}>No line items</div>
                        <div />
                      </div>
                    ) : (
                      invoice.line_items.map((item, i) => (
                        <div
                          key={i}
                          className={`${GRID} items-center px-4 py-2 border-t border-gray-50`}
                        >
                          <div className="text-[13px] font-medium pl-6" style={{ color: '#1F3148' }}>{item.name}</div>
                          <div className="text-[13px]" style={{ color: '#6B7280' }}>{item.description}</div>
                          <div className="text-right text-[13px]" style={{ color: '#1F3148' }}>
                            {formatCurrency(item.amount)}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                ))}
              </div>
            )
          })}

          {/* Grand total row */}
          <div className={`${GRID} items-center px-4 py-3 border-t-2 border-gray-200`}>
            <div className="text-[13px] font-semibold" style={{ color: '#1F3148' }}>
              Grand total ({data.distinct_engagement_count} engagement{data.distinct_engagement_count !== 1 ? 's' : ''})
            </div>
            <div />
            <div className="text-right text-[13px] font-semibold" style={{ color: '#1F3148' }}>
              {formatCurrency(grandTotal)}
            </div>
          </div>

        </div>
      )}

    </div>
  )
}