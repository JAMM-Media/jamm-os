// frontend/src/app/documents/[id]/page.tsx
'use client'

import { useState } from 'react'
import { useParams } from 'next/navigation'
import { AppShell } from '@/components/layout/AppShell'
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
      <AppShell>
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
      </AppShell>
    )
  }

  if (!doc) {
    return (
      <AppShell>
        <div className="flex items-center justify-center h-full p-6">
          <p className="text-[13px] text-[#6B7280]">Document not found.</p>
        </div>
      </AppShell>
    )
  }

  return (
    <AppShell>
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
          <button
            onClick={handleDownload}
            className="h-9 px-3 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[13px] font-medium hover:opacity-90 transition-opacity flex-shrink-0"
          >
            Download
          </button>
        </div>
        <div className="bg-surface-card dark:bg-dark-card rounded-card p-4">
          <p className="text-[12px] text-[#6B7280]">
            Document preview and version history coming in a future phase.
          </p>
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
    </AppShell>
  )
}
