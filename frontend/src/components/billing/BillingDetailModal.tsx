// frontend/src/components/billing/BillingDetailModal.tsx
'use client'

import { useState, useEffect, useCallback } from 'react'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { Modal } from '@/components/ui/Modal'
import api from '@/lib/api'
import { engagementsApi } from '@/lib/api'
import type { Engagement } from '@/lib/api'

interface BillingDetailEntry {
  date: string
  staff_name: string
  engagement_name: string
  activity_type: string | null
  description: string
  hours: number
  hourly_rate: number
  amount: number
  is_billable: boolean
}

interface BillingDetailData {
  client_name: string
  firm_name: string
  date_from: string | null
  date_to: string | null
  entries: BillingDetailEntry[]
  total_hours: number
  total_amount: number
}

interface BillingDetailModalProps {
  open: boolean
  onClose: () => void
  clientId: string
  clientName: string
}

export function BillingDetailModal({ open, onClose, clientId, clientName }: BillingDetailModalProps) {
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [engagementId, setEngagementId] = useState('')
  const [engagements, setEngagements] = useState<Engagement[]>([])
  const [preview, setPreview] = useState<BillingDetailData | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [sending, setSending] = useState(false)

  useEffect(() => {
    if (!open) return
    engagementsApi.list(0, 100, clientId)
      .then((res) => setEngagements(res.items))
      .catch(() => {})
  }, [open, clientId])

  const fetchPreview = useCallback(() => {
    const params = new URLSearchParams({ client_id: clientId, format: 'json' })
    if (dateFrom) params.set('date_from', dateFrom)
    if (dateTo) params.set('date_to', dateTo)
    if (engagementId) params.set('engagement_id', engagementId)

    setPreviewLoading(true)
    api.get<BillingDetailData>(`/reports/billing-detail?${params.toString()}`)
      .then((res) => setPreview(res.data))
      .catch(() => setPreview(null))
      .finally(() => setPreviewLoading(false))
  }, [clientId, dateFrom, dateTo, engagementId])

  useEffect(() => {
    if (!open) return
    fetchPreview()
  }, [open, fetchPreview])

  async function handleDownload() {
    setDownloading(true)
    try {
      const params = new URLSearchParams({ client_id: clientId, format: 'pdf' })
      if (dateFrom) params.set('date_from', dateFrom)
      if (dateTo) params.set('date_to', dateTo)
      if (engagementId) params.set('engagement_id', engagementId)

      const res = await api.get(`/reports/billing-detail?${params.toString()}`, {
        responseType: 'blob',
      })
      const url = URL.createObjectURL(res.data as Blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `billing-detail-${clientName.replace(/\s+/g, '-')}.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      toast.error('Failed to generate PDF')
    } finally {
      setDownloading(false)
    }
  }

  async function handleSendToPortal() {
    setSending(true)
    try {
      await api.post('/reports/billing-detail/send-to-portal', {
        client_id: clientId,
        date_from: dateFrom || null,
        date_to: dateTo || null,
        engagement_id: engagementId || null,
      })
      toast.success('Billing detail sent to client portal')
      onClose()
    } catch {
      toast.error('Failed to send billing detail')
    } finally {
      setSending(false)
    }
  }

  const formatCurrency = (n: number) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(n)

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Billing Detail"
      size="lg"
      footer={
        <>
          <button
            onClick={handleDownload}
            disabled={downloading || previewLoading}
            className="h-9 px-3 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border bg-transparent text-brand dark:text-[#EDEEF0] text-[13px] font-medium hover:bg-surface-page dark:hover:bg-dark-page transition-colors disabled:opacity-60 flex items-center gap-1.5"
          >
            {downloading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
            Download PDF
          </button>
          <button
            onClick={handleSendToPortal}
            disabled={sending || previewLoading}
            className="h-9 px-4 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[13px] font-medium hover:opacity-90 transition-opacity disabled:opacity-60 flex items-center gap-1.5"
          >
            {sending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
            Send to Portal
          </button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {/* Filters */}
        <div className="grid grid-cols-3 gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em]">
              Date From
            </label>
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="h-8 px-2 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[13px] text-brand dark:text-[#EDEEF0] focus:outline-none focus:ring-1 focus:ring-brand"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em]">
              Date To
            </label>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="h-8 px-2 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[13px] text-brand dark:text-[#EDEEF0] focus:outline-none focus:ring-1 focus:ring-brand"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em]">
              Engagement
            </label>
            <select
              value={engagementId}
              onChange={(e) => setEngagementId(e.target.value)}
              className="h-8 px-2 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[13px] text-brand dark:text-[#EDEEF0] focus:outline-none focus:ring-1 focus:ring-brand"
            >
              <option value="">All engagements</option>
              {engagements.map((eng) => (
                <option key={eng.id} value={eng.id}>{eng.name}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Preview table */}
        <div className="rounded-modal border border-[0.5px] border-surface-border dark:border-dark-border overflow-hidden">
          {previewLoading ? (
            <div className="flex flex-col gap-2 p-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-8 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
              ))}
            </div>
          ) : !preview || preview.entries.length === 0 ? (
            <div className="py-10 text-center text-[12px] text-[#6B7280]">
              No time entries for the selected filters.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse min-w-[600px]">
                <thead>
                  <tr className="bg-surface-card dark:bg-[#252525]">
                    {['Date', 'Staff', 'Engagement', 'Activity', 'Hours', 'Amount'].map((col) => (
                      <th
                        key={col}
                        className="px-3 py-2 text-left text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] whitespace-nowrap"
                      >
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {preview.entries.map((entry, i) => (
                    <tr
                      key={i}
                      className="border-t border-[0.5px] border-[#D5D8DE] dark:border-dark-card bg-surface-page dark:bg-dark-page"
                    >
                      <td className="px-3 py-2 text-[12px] text-brand dark:text-[#EDEEF0] whitespace-nowrap">{entry.date}</td>
                      <td className="px-3 py-2 text-[12px] text-[#374151] dark:text-[#9CA3AF]">{entry.staff_name}</td>
                      <td className="px-3 py-2 text-[12px] text-[#374151] dark:text-[#9CA3AF]">{entry.engagement_name}</td>
                      <td className="px-3 py-2 text-[12px] text-[#374151] dark:text-[#9CA3AF]">{entry.activity_type ?? '—'}</td>
                      <td className="px-3 py-2 text-[12px] text-brand dark:text-[#EDEEF0] text-right">{entry.hours.toFixed(2)}</td>
                      <td className="px-3 py-2 text-[12px] text-brand dark:text-[#EDEEF0] text-right">{formatCurrency(entry.amount)}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="border-t-2 border-surface-border dark:border-dark-border bg-surface-card dark:bg-[#252525]">
                    <td colSpan={4} className="px-3 py-2 text-[12px] font-semibold text-brand dark:text-[#EDEEF0]">Total</td>
                    <td className="px-3 py-2 text-[12px] font-semibold text-brand dark:text-[#EDEEF0] text-right">{preview.total_hours.toFixed(2)}</td>
                    <td className="px-3 py-2 text-[12px] font-semibold text-brand dark:text-[#EDEEF0] text-right">{formatCurrency(preview.total_amount)}</td>
                  </tr>
                </tfoot>
              </table>
            </div>
          )}
        </div>
      </div>
    </Modal>
  )
}
