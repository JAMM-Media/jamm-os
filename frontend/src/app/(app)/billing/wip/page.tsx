// path: frontend/src/app/billing/wip/page.tsx
'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useQuery } from '@tanstack/react-query'
import { reportsApi, type WIPSummary } from '@/lib/api'
import { Download, RefreshCw } from 'lucide-react'

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value)
}

function exportCsv(data: WIPSummary) {
  const rows = [
    ['Client', 'Engagement', 'Hours', 'Value'],
    ...(data.topEngagements ?? []).map((e) => [
      e.clientName,
      e.engagementName,
      e.totalHours.toFixed(1),
      e.wipValue.toFixed(2),
    ]),
    ['', '', '', ''],
    ['Total', '', data.totalHours.toFixed(1), data.totalWipValue.toFixed(2)],
  ]
  const csv = rows.map((r) => r.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(',')).join('\n')
  const blob = new Blob([csv], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'wip-report.csv'
  a.click()
  URL.revokeObjectURL(url)
}

function WipTableSkeleton() {
  return (
    <div className="rounded-modal border border-[0.5px] border-surface-border dark:border-dark-border overflow-hidden">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 px-4 py-3 border-b border-[0.5px] border-[#D5D8DE] dark:border-dark-card last:border-0">
          <div className="h-4 w-28  bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded flex-shrink-0" />
          <div className="h-4 w-40 flex-1 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded flex-shrink-0" />
          <div className="h-4 w-16  bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded flex-shrink-0" />
          <div className="h-4 w-20  bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded flex-shrink-0" />
        </div>
      ))}
    </div>
  )
}

export default function WIPReportPage() {
  const { data, isLoading, isError, refetch } = useQuery<WIPSummary>({
    queryKey: ['wip-report'],
    queryFn: reportsApi.getWip,
    staleTime: 2 * 60 * 1000,
  })

  const engagements = data?.topEngagements ?? []

  return (
      <div className="flex flex-col p-6 gap-4">

        {/* Breadcrumb */}
        <nav className="flex items-center gap-1.5 text-[12px] text-[#6B7280]">
          <Link href="/billing" className="hover:text-brand-light transition-colors">Billing</Link>
          <span>/</span>
          <span className="text-[#374151] dark:text-[#D1D5DB]">WIP Report</span>
        </nav>

        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-[24px] font-[500] text-brand dark:text-[#EDEEF0]">
              Work in Progress
            </h1>
            <p className="text-[12px] text-[#6B7280] mt-0.5">
              Unbilled time across all active engagements
            </p>
          </div>
          <button
            onClick={() => data && exportCsv(data)}
            disabled={!data || isLoading}
            className="flex items-center gap-1.5 h-9 px-3 rounded-[6px] border border-surface-border dark:border-dark-border text-[13px] text-[#374151] dark:text-[#D1D5DB] hover:bg-[#F9FAFB] dark:hover:bg-[#2A2A2A] disabled:opacity-50 transition-colors"
          >
            <Download className="h-4 w-4" />
            Export CSV
          </button>
        </div>

        {/* Content */}
        {isLoading ? (
          <WipTableSkeleton />
        ) : isError ? (
          <div className="flex flex-col items-center justify-center py-24 gap-3">
            <p className="text-[13px] text-[#DC2626]">Failed to load WIP data.</p>
            <button
              onClick={() => refetch()}
              className="flex items-center gap-1.5 text-[13px] font-medium px-4 py-2 rounded-[6px] bg-brand text-white hover:opacity-90"
            >
              <RefreshCw className="h-4 w-4" /> Retry
            </button>
          </div>
        ) : engagements.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 gap-2">
            <p className="text-[14px] font-medium text-brand dark:text-[#EDEEF0]">No unbilled time entries</p>
            <p className="text-[12px] text-[#6B7280]">All time has been billed or no time has been logged yet.</p>
          </div>
        ) : (
          <div className="rounded-modal border border-[0.5px] border-surface-border dark:border-dark-border overflow-hidden">
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-surface-card dark:bg-[#252525]">
                  {['Client', 'Engagement', 'Hours', 'Value'].map((col, i) => (
                    <th
                      key={col}
                      className={[
                        'px-4 py-2.5 text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] whitespace-nowrap',
                        i >= 2 ? 'text-right' : 'text-left',
                      ].join(' ')}
                    >
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {engagements.map((eng, i) => (
                  <tr
                    key={eng.engagementId}
                    className={[
                      'bg-surface-page dark:bg-dark-page',
                      i !== engagements.length - 1
                        ? 'border-b border-[0.5px] border-[#D5D8DE] dark:border-dark-card'
                        : '',
                    ].join(' ')}
                  >
                    <td className="px-4 py-3">
                      <span className="text-[12px] font-[500] text-brand-light hover:underline cursor-pointer">
                        {eng.clientName}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-[12px] font-[400] text-[#374151] dark:text-[#D1D5DB]">
                        {eng.engagementName}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span className="text-[12px] font-[500] text-brand dark:text-[#EDEEF0]">
                        {eng.totalHours.toFixed(1)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span className="text-[12px] font-[500] text-brand-light">
                        {formatCurrency(eng.wipValue)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t border-[#D5D8DE] dark:border-dark-border bg-surface-card dark:bg-[#252525]">
                  <td colSpan={2} className="px-4 py-3" />
                  <td colSpan={2} className="px-4 py-3 text-right">
                    <span className="text-[13px] font-[500] text-brand-light">
                      Total unbilled value: {formatCurrency(data?.totalWipValue ?? 0)} across {engagements.length} engagement{engagements.length !== 1 ? 's' : ''}
                    </span>
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}

      </div>
  )
}
