// frontend/src/app/documents/[id]/page.tsx
'use client'

import { useState } from 'react'
import { useParams } from 'next/navigation'
import { Breadcrumb } from '@/components/layout/Breadcrumb'
import { StatusBadge, BadgeVariant } from '@/components/ui/StatusBadge'
import { documentsApi } from '@/lib/api'
import { useFetch } from '@/lib/hooks/useFetch'
import { FileText } from 'lucide-react'
import { NotesTab, NotesPanel, useNotes } from '@/components/notes'

function formatFileSize(kb: number): string {
  if (kb < 1024) return `${kb} KB`
  return `${(kb / 1024).toFixed(1)} MB`
}

function DocumentDetailBodySkeleton() {
  return (
    <div className="p-6 pt-0 flex flex-col gap-3">
      {/* Document Details card */}
      <div className="bg-surface-card dark:bg-dark-card rounded-[8px] border border-[0.5px] border-surface-border dark:border-dark-border overflow-hidden">
        <div className="px-4 py-2.5 border-b border-[0.5px] border-surface-border dark:border-dark-border bg-[#EDEEF0] dark:bg-[#252525]">
          <div className="h-2.5 w-28 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
        </div>
        <div className="grid grid-cols-2 gap-0">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className={`px-4 py-3 flex flex-col gap-1 ${i < 4 ? 'border-b border-[0.5px] border-surface-border dark:border-dark-border' : ''}`}
            >
              <div className="h-2.5 w-12 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
              <div className="h-3.5 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" style={{ width: i % 2 === 0 ? '65%' : '48%' }} />
            </div>
          ))}
        </div>
      </div>
      {/* Download CTA card */}
      <div className="bg-surface-card dark:bg-dark-card rounded-[8px] border border-[0.5px] border-surface-border dark:border-dark-border p-4 flex items-center justify-between">
        <div className="flex flex-col gap-1.5">
          <div className="h-3.5 w-32 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
          <div className="h-2.5 w-48 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
        </div>
        <div className="h-9 w-24 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded-[6px]" />
      </div>
    </div>
  )
}

export default function DocumentDetailPage() {
  const params = useParams()
  const docId = params.id as string
  const { data: doc, isLoading } = useFetch(() => documentsApi.get(docId), [docId])
  const [notesOpen, setNotesOpen] = useState(false)
  const { unreadCount } = useNotes({ entityType: 'document', entityId: docId })

  async function handleDownload() {
    if (!doc) return
    const url = await documentsApi.getSignedUrl(doc.id)
    window.open(url, '_blank')
  }

  if (isLoading) {
    return (
      <>
        <div className="p-6 flex flex-col gap-4">
          <div className="h-4 w-32 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-lg bg-[#D5D8DE] dark:bg-[#444444] animate-pulse" />
            <div className="flex flex-col gap-2 flex-1">
              <div className="h-6 w-64 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
              <div className="h-4 w-48 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
            </div>
          </div>
        </div>
        <DocumentDetailBodySkeleton />
      </>
    )
  }

  if (!doc) {
    return (
        <div className="flex items-center justify-center h-full p-6">
          <p className="text-[13px] text-[#6B7280]">Document not found.</p>
        </div>
    )
  }

  return (<>
      <div className="p-6">
        <Breadcrumb
          items={[
            { label: 'Documents', href: '/documents' },
            { label: doc.name },
          ]}
        />
        <div className="flex items-start justify-between mb-6">
          <div className="flex items-start gap-3">
            <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-surface-card dark:bg-dark-card border border-[0.5px] border-surface-border dark:border-dark-border flex-shrink-0">
              <FileText className="h-5 w-5 text-[#6B7280]" />
            </div>
            <div>
              <h1 className="text-2xl font-medium text-brand dark:text-[#EDEEF0] mb-1">
                {doc.name}
              </h1>
              <div className="flex items-center gap-2">
                <StatusBadge variant={doc.status as BadgeVariant} />
                <span className="text-[12px] text-[#6B7280]">
                  {doc.clientName} · {doc.fileType} · {formatFileSize(doc.fileSizeKb)} · Uploaded {doc.uploadedAt}
                </span>
              </div>
            </div>
          </div>
        </div>
        <div className="flex flex-col gap-3">
          {/* Document info card */}
          <div className="bg-surface-card dark:bg-dark-card rounded-[8px] border border-[0.5px] border-surface-border dark:border-dark-border overflow-hidden">
            <div className="px-4 py-2.5 border-b border-[0.5px] border-surface-border dark:border-dark-border bg-[#EDEEF0] dark:bg-[#252525]">
              <p className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em]">Document Details</p>
            </div>
            <div className="grid grid-cols-2 gap-0">
              {[
                { label: 'Client', value: doc.clientName || '—' },
                { label: 'Engagement', value: doc.engagementTitle || '—' },
                { label: 'File Type', value: doc.fileType || '—' },
                { label: 'File Size', value: doc.fileSizeKb > 0 ? `${doc.fileSizeKb.toFixed(0)} KB` : '—' },
                { label: 'Uploaded', value: doc.uploadedAt || '—' },
                { label: 'Uploaded By', value: doc.uploadedBy || 'System' },
              ].map((row, i) => (
                <div
                  key={row.label}
                  className={`px-4 py-3 flex flex-col gap-0.5 ${
                    i < 4 ? 'border-b border-[0.5px] border-surface-border dark:border-dark-border' : ''
                  }`}
                >
                  <p className="text-[11px] text-[#6B7280]">{row.label}</p>
                  <p className="text-[12px] font-medium text-brand dark:text-[#EDEEF0]">{row.value}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Download CTA */}
          <div className="bg-surface-card dark:bg-dark-card rounded-[8px] border border-[0.5px] border-surface-border dark:border-dark-border p-4 flex items-center justify-between">
            <div>
              <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">Download Document</p>
              <p className="text-[11px] text-[#6B7280] mt-0.5">Opens a secure link valid for 1 hour</p>
            </div>
            <button
              onClick={handleDownload}
              className="h-9 px-4 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[13px] font-medium hover:opacity-90 transition-opacity"
            >
              Download
            </button>
          </div>
        </div>
      </div>

      <NotesTab unreadCount={unreadCount} onClick={() => setNotesOpen(true)} />
      <NotesPanel
        isOpen={notesOpen}
        onClose={() => setNotesOpen(false)}
        entityType="document"
        entityId={docId}
        contextLabel={doc.name}
      />
  </>)
}
