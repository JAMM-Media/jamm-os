// frontend/src/components/portal/PortalBillingDetail.tsx
'use client'

import { useState, useEffect } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'
import { getPortalBillingDetail, type BillingDetailReport } from '@/lib/portal-api'

interface Props {
  cardColor: string
  accentColor: string
  portalMode: 'light' | 'dark'
  textPrimary: string
  textMuted: string
}

export function PortalBillingDetail({ cardColor, accentColor, portalMode, textPrimary, textMuted }: Props) {
  const [reports, setReports] = useState<BillingDetailReport[]>([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  const borderColor = portalMode === 'light' ? '#e5e7eb' : '#383838'

  useEffect(() => {
    getPortalBillingDetail()
      .then(setReports)
      .catch(() => setReports([]))
      .finally(() => setLoading(false))
  }, [])

  function toggleExpand(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  function formatDateRange(report: BillingDetailReport): string {
    if (!report.date_from && !report.date_to) return 'All dates'
    const parts: string[] = []
    if (report.date_from) parts.push(report.date_from)
    if (report.date_to) parts.push(report.date_to)
    return parts.join(' – ')
  }

  function formatCurrency(n: number): string {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(n)
  }

  if (loading) {
    return (
      <div className="p-5 flex flex-col gap-3 max-w-3xl mx-auto w-full">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-16 rounded-[8px] animate-pulse" style={{ backgroundColor: cardColor }} />
        ))}
      </div>
    )
  }

  if (reports.length === 0) {
    return (
      <div className="p-8 flex flex-col items-center justify-center gap-2 text-center">
        <p className="text-[14px] font-medium" style={{ color: textPrimary }}>
          No billing details shared yet.
        </p>
        <p className="text-[13px]" style={{ color: textMuted }}>
          Your firm will share billing summaries here.
        </p>
      </div>
    )
  }

  return (
    <div className="p-5 flex flex-col gap-3 max-w-3xl mx-auto w-full">
      {reports.map((report) => {
        const isOpen = expanded.has(report.id)
        return (
          <div
            key={report.id}
            className="rounded-[8px] overflow-hidden border"
            style={{ backgroundColor: cardColor, borderColor }}
          >
            <button
              type="button"
              onClick={() => toggleExpand(report.id)}
              className="w-full flex items-center justify-between px-4 py-3 text-left"
            >
              <div className="flex flex-col gap-0.5">
                <span className="text-[13px] font-medium" style={{ color: textPrimary }}>
                  {formatDateRange(report)}
                </span>
                <span className="text-[12px]" style={{ color: textMuted }}>
                  {report.total_hours.toFixed(2)} hrs · {formatCurrency(report.total_amount)}
                </span>
                <span className="text-[11px]" style={{ color: textMuted }}>
                  Shared {new Date(report.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                </span>
              </div>
              {isOpen ? (
                <ChevronUp className="h-4 w-4 flex-shrink-0" style={{ color: textMuted }} />
              ) : (
                <ChevronDown className="h-4 w-4 flex-shrink-0" style={{ color: textMuted }} />
              )}
            </button>

            {isOpen && report.entries.length > 0 && (
              <div className="border-t overflow-x-auto" style={{ borderColor }}>
                <table className="w-full border-collapse min-w-[600px]">
                  <thead>
                    <tr style={{ backgroundColor: accentColor + '20' }}>
                      {['Date', 'Staff', 'Engagement', 'Activity', 'Hours', 'Amount'].map((col) => (
                        <th
                          key={col}
                          className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wide"
                          style={{ color: textMuted }}
                        >
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {report.entries.map((entry, i) => (
                      <tr
                        key={i}
                        className="border-t"
                        style={{ borderColor }}
                      >
                        <td className="px-3 py-2 text-[12px]" style={{ color: textPrimary }}>{entry.date}</td>
                        <td className="px-3 py-2 text-[12px]" style={{ color: textPrimary }}>{entry.staff_name}</td>
                        <td className="px-3 py-2 text-[12px]" style={{ color: textPrimary }}>{entry.engagement_name}</td>
                        <td className="px-3 py-2 text-[12px]" style={{ color: textMuted }}>{entry.activity_type ?? '—'}</td>
                        <td className="px-3 py-2 text-[12px]" style={{ color: textPrimary }}>{entry.hours.toFixed(2)}</td>
                        <td className="px-3 py-2 text-[12px]" style={{ color: textPrimary }}>{formatCurrency(entry.amount)}</td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="border-t" style={{ borderColor }}>
                      <td colSpan={4} className="px-3 py-2 text-[12px] font-semibold" style={{ color: textPrimary }}>Total</td>
                      <td className="px-3 py-2 text-[12px] font-semibold" style={{ color: textPrimary }}>{report.total_hours.toFixed(2)}</td>
                      <td className="px-3 py-2 text-[12px] font-semibold" style={{ color: textPrimary }}>{formatCurrency(report.total_amount)}</td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
