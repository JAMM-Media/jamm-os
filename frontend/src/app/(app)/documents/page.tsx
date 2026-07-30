// path: frontend/src/app/documents/page.tsx
'use client'

import { useState, useRef } from 'react'
import { ViewToggle } from '@/components/ui/ViewToggle'
import { DocumentTable } from '@/components/documents/DocumentTable'
import { DocumentCard } from '@/components/documents/DocumentCard'
import { DocumentEmptyState } from '@/components/documents/DocumentEmptyState'
import api, { documentsApi, clientsApi } from '@/lib/api'
import { useFetch } from '@/lib/hooks/useFetch'
import { ContextualBanner } from '@/components/concierge-inline/ContextualBanner'
import { emitConciergeAction } from '@/lib/events/conciergeEvents'
import { Search } from 'lucide-react'

type ViewMode = 'table' | 'card'

export default function DocumentsPage() {
  const [view, setView] = useState<ViewMode>('table')
  const [search, setSearch] = useState('')
  const [clientFilter, setClientFilter] = useState<string>('all')
  const [engagementFilter, setEngagementFilter] = useState<string>('all')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [uploading, setUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const { data, isLoading, error } = useFetch(() => documentsApi.list(), [])
  const { data: clientsData } = useFetch(() => clientsApi.list(0, 100), [])
  const { data: outstandingData } = useFetch(() => api.get('/document-requests/outstanding-summary').then((r) => r.data as { outstanding_count: number }), [])
  const documents = data?.items ?? []
  const uniqueEngagements = Array.from(
    new Set(documents.map((d) => d.engagementTitle).filter(Boolean))
  ).sort()

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      await documentsApi.upload(file)
      window.location.reload()
    } catch {
      alert('Upload failed — please try again.')
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const filtered = documents.filter((d) => {
    if (
      search &&
      !d.name.toLowerCase().includes(search.toLowerCase()) &&
      !d.clientName.toLowerCase().includes(search.toLowerCase()) &&
      !d.engagementTitle.toLowerCase().includes(search.toLowerCase())
    ) return false
    if (clientFilter !== 'all' && d.clientId !== clientFilter) return false
    if (engagementFilter !== 'all' && d.engagementTitle !== engagementFilter) return false
    if (statusFilter !== 'all' && d.status !== statusFilter) return false
    return true
  })

  if (error) {
    return (
        <div className="flex flex-col h-full p-6 items-center justify-center">
          <p className="text-sm text-[#DC2626]">Failed to load documents.</p>
        </div>
    )
  }

  return (
      <div className="flex flex-col p-6 gap-4">

        <h1 className="text-2xl font-medium text-brand dark:text-[#EDEEF0]">
          Documents
        </h1>

        {(outstandingData?.outstanding_count ?? 0) > 0 && (
          <ContextualBanner
            tone="amber"
            count={outstandingData!.outstanding_count}
            message={`document request${outstandingData!.outstanding_count === 1 ? '' : 's'} still outstanding.`}
            actionLabel="Ask Concierge"
            onAction={() => {
              emitConciergeAction({ type: 'open-panel' })
              emitConciergeAction({ type: 'prefill-panel-input', prefillMessage: 'What document requests are still outstanding?' })
            }}
          />
        )}

        {/* Toolbar */}
        <div className="flex items-center gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-[#6B7280]" />
            <input
              type="text"
              placeholder="Search documents..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full h-9 pl-8 pr-3 rounded-[6px] bg-surface-input dark:bg-dark-card border border-[0.5px] border-surface-border dark:border-dark-border text-[13px] text-brand dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-brand-light transition-colors"
            />
          </div>
          <ViewToggle value={view} onChange={setView} />
          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            onChange={handleFileChange}
            accept=".pdf,.doc,.docx,.xlsx,.xls,.csv,.png,.jpg,.jpeg"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="h-9 px-3 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[13px] font-medium hover:opacity-90 transition-opacity whitespace-nowrap flex-shrink-0 disabled:opacity-60"
          >
            {uploading ? 'Uploading...' : 'Upload Document'}
          </button>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <select
            value={clientFilter}
            onChange={(e) => { setClientFilter(e.target.value); setEngagementFilter('all') }}
            className="text-[12px] h-8 px-2 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-brand dark:text-[#EDEEF0] cursor-pointer"
          >
            <option value="all">All Clients</option>
            {(clientsData?.items ?? [])
              .slice()
              .sort((a, b) => a.name.localeCompare(b.name))
              .map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
          </select>

          <select
            value={engagementFilter}
            onChange={(e) => setEngagementFilter(e.target.value)}
            className="text-[12px] h-8 px-2 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-brand dark:text-[#EDEEF0] cursor-pointer"
          >
            <option value="all">All Engagements</option>
            {uniqueEngagements.map((title) => (
              <option key={title} value={title}>{title}</option>
            ))}
          </select>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="text-[12px] h-8 px-2 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-brand dark:text-[#EDEEF0] cursor-pointer"
          >
            <option value="all">All Statuses</option>
            <option value="uploaded">Uploaded</option>
            <option value="pending">Pending</option>
            <option value="pending_signature">Pending Signature</option>
            <option value="signed">Signed</option>
            <option value="rejected">Rejected</option>
          </select>

          {(clientFilter !== 'all' || engagementFilter !== 'all' || statusFilter !== 'all') && (
            <button
              onClick={() => { setClientFilter('all'); setEngagementFilter('all'); setStatusFilter('all') }}
              className="text-[11px] text-[#6B7280] hover:text-brand underline"
            >
              Clear filters
            </button>
          )}

          {(clientFilter !== 'all' || engagementFilter !== 'all' || statusFilter !== 'all') && (
            <span className="text-[11px] text-[#6B7280]">
              Showing {filtered.length} of {documents.length} documents
            </span>
          )}
        </div>

        {/* Content */}
        {isLoading ? (
          <div className="rounded-modal border border-[0.5px] border-surface-border dark:border-dark-border overflow-hidden">
            {Array.from({ length: 5 }).map((_, i) => (
              <div
                key={i}
                className="flex gap-4 px-4 py-3 border-b border-[0.5px] border-[#D5D8DE] dark:border-dark-card last:border-0"
              >
                {Array.from({ length: 6 }).map((_, j) => (
                  <div key={j} className="h-4 flex-1 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                ))}
              </div>
            ))}
          </div>
        ) : filtered.length === 0 && search === '' && clientFilter === 'all' && engagementFilter === 'all' && statusFilter === 'all' ? (
          <DocumentEmptyState onUpload={() => fileInputRef.current?.click()} />
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center flex-1 py-24 gap-2">
            <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">
              No results for &ldquo;{search}&rdquo;
            </p>
            <p className="text-[12px] text-[#6B7280]">
              Try a different document name or client.
            </p>
          </div>
        ) : view === 'table' ? (
          <DocumentTable
            documents={filtered}
          />
        ) : (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
            {filtered.map((doc) => (
              <DocumentCard key={doc.id} document={doc} />
            ))}
          </div>
        )}

      </div>
  )
}
