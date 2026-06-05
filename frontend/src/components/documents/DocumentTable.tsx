// frontend/src/components/documents/DocumentTable.tsx
'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { toast } from 'sonner'
import { Document } from '@/lib/api/documents'
import { formatFileSize } from '@/lib/utils'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { FileText } from 'lucide-react'
import { useAuth } from '@/lib/hooks/useAuth'
import { documentsApi } from '@/lib/api/documents'

interface DocumentTableProps {
  documents: Document[]
}

export function DocumentTable({ documents }: DocumentTableProps) {
  const router = useRouter()
  const { user } = useAuth()
  const isStaff = user && user.role !== 'client_portal_user'

  // Local optimistic overrides: doc.id -> is_superseded
  const [supersededOverrides, setSupersededOverrides] = useState<Record<string, boolean>>({})

  function getIsSuperseded(doc: Document): boolean {
    if (doc.id in supersededOverrides) return supersededOverrides[doc.id]
    return doc.is_superseded ?? false
  }

  async function handleToggleSuperseded(e: React.MouseEvent, doc: Document) {
    e.stopPropagation()
    const next = !getIsSuperseded(doc)
    setSupersededOverrides((prev) => ({ ...prev, [doc.id]: next }))
    try {
      await documentsApi.patchSuperseded(doc.id, next)
      toast.success(next ? 'Document marked as superseded' : 'Document marked as current')
    } catch {
      setSupersededOverrides((prev) => ({ ...prev, [doc.id]: !next }))
      toast.error('Could not update document — please try again')
    }
  }

  return (
    <div className="rounded-modal border border-[0.5px] border-surface-border dark:border-dark-border overflow-hidden">
      <table className="w-full border-collapse">
        <thead>
          <tr className="bg-surface-card dark:bg-[#252525]">
            {['Document', 'Client', 'Engagement', 'Uploaded By', 'Date', 'Size', 'Status'].map((col) => (
              <th
                key={col}
                className="px-4 py-2.5 text-left text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] whitespace-nowrap"
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {documents.map((doc, i) => {
            const superseded = getIsSuperseded(doc)
            return (
              <tr
                key={doc.id}
                onClick={() => router.push(`/documents/${doc.id}`)}
                className={[
                  'group cursor-pointer transition-colors',
                  'bg-surface-page dark:bg-dark-page',
                  'hover:bg-[#DDDFE3] dark:hover:bg-[#323232]',
                  superseded ? 'opacity-50' : '',
                  i !== documents.length - 1
                    ? 'border-b border-[0.5px] border-[#D5D8DE] dark:border-dark-card'
                    : '',
                ].join(' ')}
              >
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <FileText className="h-4 w-4 text-[#6B7280] flex-shrink-0" />
                    <span
                      className={[
                        'text-[12px] font-medium text-brand dark:text-[#EDEEF0]',
                        superseded ? 'line-through' : '',
                      ].join(' ')}
                    >
                      {doc.name}
                    </span>
                    {superseded && (
                      <span
                        className="inline-flex items-center px-1.5 py-0.5 rounded-full text-[11px] font-medium"
                        style={{ backgroundColor: '#E5E7EB', color: '#6B7280' }}
                      >
                        Superseded
                      </span>
                    )}
                    {isStaff && (
                      <button
                        onClick={(e) => handleToggleSuperseded(e, doc)}
                        className="opacity-0 group-hover:opacity-100 transition-opacity text-[11px] text-[#6B7280] bg-transparent border-none cursor-pointer ml-1"
                      >
                        {superseded ? 'Mark as current' : 'Mark as superseded'}
                      </button>
                    )}
                  </div>
                </td>
                <td className="px-4 py-3">
                  <span
                    onClick={(e) => { e.stopPropagation(); router.push(`/clients/${doc.clientId}`) }}
                    className="text-[12px] text-brand-light hover:underline cursor-pointer"
                  >
                    {doc.clientName}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className="text-[12px] text-[#374151] dark:text-[#9CA3AF]">
                    {doc.engagementTitle}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className="text-[12px] text-[#374151] dark:text-[#9CA3AF]">
                    {doc.uploadedBy}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className="text-[12px] text-[#374151] dark:text-[#9CA3AF]">
                    {doc.uploadedAt}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className="text-[12px] text-[#374151] dark:text-[#9CA3AF]">
                    {formatFileSize(doc.fileSizeKb)}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <StatusBadge variant={doc.status} />
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
