// path: frontend/src/app/documents/page.tsx
'use client'

import { useState, useRef } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { ViewToggle } from '@/components/ui/ViewToggle'
import { DocumentTable } from '@/components/documents/DocumentTable'
import { DocumentCard } from '@/components/documents/DocumentCard'
import { DocumentEmptyState } from '@/components/documents/DocumentEmptyState'
import { documentsApi } from '@/lib/api'
import { useFetch } from '@/lib/hooks/useFetch'
import { Search } from 'lucide-react'

type ViewMode = 'table' | 'card'

export default function DocumentsPage() {
  const [view, setView] = useState<ViewMode>('table')
  const [search, setSearch] = useState('')
  const [uploading, setUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const { data, isLoading, error } = useFetch(() => documentsApi.list(), [])
  const documents = data?.items ?? []

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

  const filtered = documents.filter((d) =>
    d.name.toLowerCase().includes(search.toLowerCase()) ||
    d.clientName.toLowerCase().includes(search.toLowerCase()) ||
    d.engagementTitle.toLowerCase().includes(search.toLowerCase())
  )

  if (error) {
    return (
      <AppShell>
        <div className="flex flex-col h-full p-6 items-center justify-center">
          <p className="text-sm text-[#DC2626]">Failed to load documents.</p>
        </div>
      </AppShell>
    )
  }

  return (
    <AppShell>
      <div className="flex flex-col h-full p-6 gap-4">

        <h1 className="text-2xl font-medium text-brand dark:text-[#EDEEF0]">
          Documents
        </h1>

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
        ) : filtered.length === 0 && search === '' ? (
          <DocumentEmptyState onUpload={() => {}} />
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
    </AppShell>
  )
}
